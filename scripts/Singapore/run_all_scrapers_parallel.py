#!/usr/bin/env python
import os
import time
import subprocess
import logging
import sys
from datetime import datetime
import argparse
import pandas as pd
from multiprocessing import Process, Queue, Manager
import threading
import glob

# Add the current directory to the path to import modules from scripts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
log_filename = f"scraper_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
runtime_log_filename = f"scraper_runtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# Define output directory - now inside the Singapore folder
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(output_dir, exist_ok=True)

# Create runtime log file with header
with open(os.path.join(output_dir, runtime_log_filename), 'w') as f:
    f.write("script_name,start_time,end_time,runtime\n")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(output_dir, log_filename)),  # Save logs to output folder
        logging.StreamHandler()  # Also output to console
    ]
)
logger = logging.getLogger("scraper_manager")

# Global flag to control the periodic combination thread
stop_combining = False

def run_script(script_name, n_scrape=None, result_queue=None):
    """Run a Python script and log the output."""
    logger.info(f"Starting {script_name}")
    
    # Record start time for this scraper
    start_time = datetime.now()
    
    try:
        # Get the full path to the script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
        
        # Map script names to their output file names
        output_files = {
            "SG_RV_Source2.py": "SG_RV_Source2.xlsx",
            "SG_RV_Source1.py": "SG_RV_Source1.xlsx",
            "SG_RV_Source3.py": "SG_RV_Source3.xlsx",
            "SG_RV_Source4.py": "SG_RV_Source4.xlsx",
            "SG_SO_Source2.py": "SG_SO_Source2.xlsx",
            "SG_RV_Source5.py": "SG_RV_Source5.xlsx",
            "SG_RV_Source8.py": "SG_RV_Source8.xlsx",
            "SG_RV_Source6.py": "SG_RV_Source6.xlsx",
            "SG_SO_Source3.py": "SG_SO_Source3.xlsx",
        }
        
        # Set the output path for each script
        output_file = os.path.join(output_dir, output_files.get(script_name, f"{script_name}_output.xlsx"))
        
        # Prepare command with appropriate arguments based on script
        command = ["python", script_path]
        
        # Add number of items to scrape argument if provided
        if n_scrape is not None:
            if script_name == "SG_RV_Source6.py":
                # This script uses --num_devices instead of -n
                command.extend(["--num_devices", str(n_scrape)])
            elif script_name == "SG_SO_Source1.py":
                # This script uses --num_devices instead of -n
                command.extend(["--num_devices", str(n_scrape)])
            else:
                command.extend(["-n", str(n_scrape)])
        
        # Add output path argument to scripts that support it
        # Some scripts rely on environment variables instead
        if script_name in ["SG_RV_Source2.py", "SG_SO_Source2.py", "SG_RV_Source4.py", "SG_RV_Source8.py"]:
            command.extend(["-o", output_file])
        
        # Run the script
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["OUTPUT_DIR"] = output_dir  # Add environment variable for output directory
        
        # For scripts that don't accept output file as parameter, set it as env var
        if script_name in ["SG_SO_Source1.py", "SG_RV_Source6.py", "SG_RV_Source1.py", 
                          "SG_RV_Source3.py", "SG_RV_Source5.py"]:
            env["OUTPUT_FILE"] = output_file
        
        logger.info(f"Running command: {' '.join(command)}")
        
        process = subprocess.Popen(
            command, 
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Stream the output
        for line in process.stdout:
            print(f"[{script_name}] {line}", end='')
            logger.info(f"[{script_name}] {line.strip()}")  # Also log to file
            
        process.wait()
        
        # Calculate runtime for this scraper
        end_time = datetime.now()
        runtime = end_time - start_time
        runtime_str = f"{runtime.total_seconds():.2f} seconds"
        if runtime.total_seconds() >= 60:
            runtime_str = f"{runtime.total_seconds() / 60:.2f} minutes"
            
        # Log runtime to the performance log
        with open(os.path.join(output_dir, runtime_log_filename), 'a') as f:
            f.write(f"{script_name},{start_time.strftime('%Y-%m-%d %H:%M:%S')},{end_time.strftime('%Y-%m-%d %H:%M:%S')},{runtime_str}\n")
        
        logger.info(f"Runtime for {script_name}: {runtime_str}")
        
        success = process.returncode == 0
        if success:
            logger.info(f"Successfully completed {script_name}")
        else:
            logger.error(f"Failed to run {script_name} with return code {process.returncode}")
        
        # Add result to queue if provided
        if result_queue is not None:
            result_queue.put((script_name, success, runtime_str))
            
        return success
            
    except Exception as e:
        logger.error(f"Error running {script_name}: {e}")
        if result_queue is not None:
            result_queue.put((script_name, False, "N/A"))
        return False

def find_excel_files(directory):
    """Find all Excel files in a directory and return their full paths."""
    excel_files = []
    for file in os.listdir(directory):
        if file.endswith('.xlsx') and not file.startswith('Combined_'):
            excel_files.append(os.path.join(directory, file))
    return excel_files

def cleanup_intermediate_files(output_dir, keep_file=None):
    """Remove old intermediate combined files."""
    pattern = os.path.join(output_dir, "Combined_*_*.xlsx")
    for file in glob.glob(pattern):
        # Skip the file we want to keep
        if keep_file and os.path.basename(file) == os.path.basename(keep_file):
            continue
        try:
            os.remove(file)
            logger.info(f"Removed old intermediate file: {file}")
        except Exception as e:
            logger.error(f"Failed to remove intermediate file {file}: {e}")

def combine_excel_files(excel_files, output_file="Combined_Trade_In_Values.xlsx"):
    """Combine multiple Excel files into a single file."""
    logger.info(f"Combining {len(excel_files)} Excel files into {output_file}")
    
    # Create an empty DataFrame to store the combined data
    combined_df = pd.DataFrame()
    
    # Read each Excel file and append to the combined DataFrame
    for file in excel_files:
        if os.path.exists(file):
            try:
                df = pd.read_excel(file)
                logger.info(f"Read {len(df)} rows from {file}")
                combined_df = pd.concat([combined_df, df], ignore_index=True)
            except Exception as e:
                logger.error(f"Error reading {file}: {e}")
        else:
            logger.warning(f"File not found: {file}")
    
    # Save the combined DataFrame to a new Excel file
    if not combined_df.empty:
        combined_df.to_excel(output_file, index=False)
        logger.info(f"Saved {len(combined_df)} rows to {output_file}")
        return output_file
    else:
        logger.warning("No data to combine")
        return None

def periodic_combine(interval_minutes, output_dir, output_file):
    """Periodically combine Excel files at the specified interval."""
    global stop_combining
    
    logger.info(f"Starting periodic file combination every {interval_minutes} minutes")
    
    while not stop_combining:
        # Sleep for the specified interval
        time.sleep(interval_minutes * 60)
        
        if stop_combining:
            break
            
        try:
            # Find all Excel files in the output directory
            excel_files = find_excel_files(output_dir)
            if excel_files:
                logger.info(f"Periodic update: Found {len(excel_files)} Excel files to combine")
                
                # Combine files with timestamp in filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                combined_filename = f"Combined_{timestamp}_{output_file}"
                combined_path = os.path.join(output_dir, combined_filename)
                
                # Also save to the main combined file
                main_combined_path = os.path.join(output_dir, output_file)
                
                # Combine and save to both files
                combined_df = pd.DataFrame()
                
                # Read each Excel file and append to the combined DataFrame
                for file in excel_files:
                    if os.path.exists(file):
                        try:
                            df = pd.read_excel(file)
                            logger.info(f"Periodic update: Read {len(df)} rows from {file}")
                            combined_df = pd.concat([combined_df, df], ignore_index=True)
                        except Exception as e:
                            logger.error(f"Periodic update: Error reading {file}: {e}")
                
                # Save the combined DataFrame to both files
                if not combined_df.empty:
                    combined_df.to_excel(combined_path, index=False)
                    combined_df.to_excel(main_combined_path, index=False)
                    logger.info(f"Periodic update: Saved {len(combined_df)} rows to {combined_path} and {main_combined_path}")
                    
                    # Clean up older intermediate files, keeping only the latest
                    cleanup_intermediate_files(output_dir, combined_filename)
            else:
                logger.info("Periodic update: No Excel files found to combine")
        except Exception as e:
            logger.error(f"Error in periodic file combination: {e}")

def run_batch(scripts, args, result_queue, batch_num):
    """Run a batch of scraper scripts in parallel."""
    logger.info(f"Starting batch {batch_num} of scrapers")
    batch_processes = []
    
    for script in scripts:
        p = Process(
            target=run_script, 
            args=(script, args.n, result_queue)
        )
        batch_processes.append(p)
        p.start()
        logger.info(f"Started process for {script} in batch {batch_num}")
    
    # Wait for all processes in this batch to complete
    for p in batch_processes:
        p.join()
    
    # Collect results from this batch
    batch_results = {}
    batch_runtimes = {}
    while not result_queue.empty():
        script, success, runtime = result_queue.get()
        batch_results[script] = success
        batch_runtimes[script] = runtime
    
    logger.info(f"All batch {batch_num} scraper processes completed")
    logger.info(f"Batch {batch_num} runtimes: {batch_runtimes}")
    return batch_results

def main():
    """Run all scrapers in 2 batches, with 5 in the first batch and 4 in the second batch."""
    global stop_combining
    
    start_time = datetime.now()
    logger.info(f"Starting batch scraping job at {start_time}")
    
    # Get the number of scrapes from command line arguments
    parser = argparse.ArgumentParser(description='Run scrapers in 2 batches, with 5 in the first batch and 4 in the second batch')
    parser.add_argument('-n', type=int, help='Number of items to scrape (for testing)', default=None)
    parser.add_argument('-c', '--combined', type=str, help='Name of the combined output file', 
                       default="Combined_Trade_In_Values.xlsx")
    parser.add_argument('--no-combine', action='store_true', help='Do not combine results into a single file')
    parser.add_argument('-i', '--interval', type=int, help='Interval in minutes for periodic file combination', 
                       default=10)
    args = parser.parse_args()
    
    # Setup multiprocessing manager for sharing results
    manager = Manager()
    result_queue = manager.Queue()
    
    # Start periodic file combination thread
    combine_thread = None
    if not args.no_combine:
        stop_combining = False
        combine_thread = threading.Thread(
            target=periodic_combine, 
            args=(args.interval, output_dir, args.combined)
        )
        combine_thread.daemon = True
        combine_thread.start()
        logger.info(f"Started periodic file combination thread with interval {args.interval} minutes")
    
    # Define 2 batches: 5 scripts in first batch, 4 in second batch
    batches = [
        # Batch 1 (5 scrapers)
        ["SG_RV_Source1.py", "SG_RV_Source2.py", "SG_RV_Source3.py", "SG_RV_Source4.py", "SG_RV_Source5.py"],
        # Batch 2 (4 scrapers)
        ["SG_RV_Source6.py", "SG_SO_Source2.py", "SG_RV_Source8.py", "SG_SO_Source3.py"]
    ]
    
    # Run each batch sequentially and collect results
    all_results = {}
    for i, batch in enumerate(batches):
        batch_results = run_batch(batch, args, result_queue, i+1)
        all_results.update(batch_results)
    
    # Stop the periodic file combination thread
    if combine_thread is not None:
        stop_combining = True
        combine_thread.join(timeout=5)  # Wait for at most 5 seconds
        logger.info("Stopped periodic file combination thread")
    
    # Find all Excel files in the output directory
    excel_files = find_excel_files(output_dir)
    logger.info(f"Found {len(excel_files)} Excel files in output directory")
    
    # Final combination of files 
    combined_file = None
    if not args.no_combine and excel_files:
        combined_path = os.path.join(output_dir, args.combined)
        combined_file = combine_excel_files(excel_files, combined_path)

        # Cleanup only intermediate combined files, NOT the final combined file
        # Modified: Only clean up files with timestamp patterns in the name
        pattern = os.path.join(output_dir, "Combined_*_*.xlsx")
        for file in glob.glob(pattern):
            # Don't delete the final combined file
            if os.path.basename(file) != args.combined:
                try:
                    os.remove(file)
                    logger.info(f"Removed old intermediate file: {file}")
                except Exception as e:
                    logger.error(f"Failed to remove intermediate file {file}: {e}")
        
        files_to_send = [combined_file] if combined_file else []
    else:
        # If not combining, send the individual files
        files_to_send = excel_files
    
    # Add log file to files_to_send
    log_file_path = os.path.join(output_dir, log_filename)
    if os.path.exists(log_file_path):
        files_to_send.append(log_file_path)
    
    # Add runtime log file to files_to_send
    runtime_log_path = os.path.join(output_dir, runtime_log_filename)
    if os.path.exists(runtime_log_path):
        files_to_send.append(runtime_log_path)
        logger.info(f"Adding runtime log file to email attachments: {runtime_log_path}")
    
    # Send emails if we have files
    if files_to_send:
        logger.info(f"Sending email with {len(files_to_send)} files: {files_to_send}")
        try:
            # Import the send_email function from the same directory
            from send_email import send_email
            
            # Calculate runtime
            end_time = datetime.now()
            total_time = end_time - start_time
            runtime_str = f"{int(total_time.total_seconds() // 60)} minutes" if total_time.total_seconds() >= 60 else f"{int(total_time.total_seconds())} seconds"
            
            # Build email subject
            subject = f"Trade-In Values Update - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Create message body based on what we're sending
            if combined_file and not args.no_combine:
                text = (f"I finished collecting trade-in values on {datetime.now().strftime('%Y-%m-%d')}. "
                       f"All values are combined into a single file: {os.path.basename(combined_file)}.")
            else:
                text = (f"I finished collecting trade-in values on {datetime.now().strftime('%Y-%m-%d')}. "
                       f"Attached are the following files: {', '.join([os.path.basename(f) for f in files_to_send])}")
            
            # Define primary recipient (with log file)
            primary_recipient = 'ashutoshmitra7@gmail.com'
            
            # Send the email with all files including log to the primary recipient
            send_email(
                subject=subject,
                text=text,
                send_to=primary_recipient,
                files=files_to_send,
                runtime=runtime_str
            )
            logger.info(f"Email with logs sent to {primary_recipient}")
            
            # Define secondary recipient (no log file)
            secondary_recipient = 'ashmitra0000007@gmail.com'
            
            # Create a list without the log files for the secondary recipient
            files_without_logs = [f for f in files_to_send 
                                if f != log_file_path and f != runtime_log_path]
            
            # Send simplified email without log file to the secondary recipient
            if files_without_logs:
                simple_subject = "Excel file"
                simple_text = "Please find the attached Excel file."
                send_email(
                    subject=simple_subject,
                    text=simple_text,
                    send_to=secondary_recipient,
                    files=files_without_logs,
                    runtime=None  # No runtime info for secondary recipient
                )
                logger.info(f"Email without logs sent to {secondary_recipient}")
                
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    else:
        logger.warning("No files were generated. Not sending email.")
    
    end_time = datetime.now()
    total_time = end_time - start_time
    logger.info(f"Completed batch scraping job at {end_time}. Total runtime: {total_time}")

if __name__ == "__main__":
    main()