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

# Define output directory - now inside the Thailand folder
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
            "TH_SO_Source1.py": "TH_SO_Source1.xlsx",
            "TH_RV_Source1.py": "TH_RV_Source1.xlsx",
            "TH_RV_Source2.py": "TH_RV_Source2.xlsx",
            "TH_RV_Source3.py": "TH_RV_Source3.xlsx",
            "TH_RV_Source4.py": "TH_RV_Source4.xlsx"
        }
        
        # Set the output path for each script
        output_file = os.path.join(output_dir, output_files.get(script_name, f"{script_name}_output.xlsx"))
        
        # Prepare command with appropriate arguments based on script
        command = ["python", script_path]
        
        # Add number of items to scrape argument if provided
        if n_scrape is not None:
            command.extend(["-n", str(n_scrape)])
        
        # Add output path argument to scripts that support it
        if script_name in ["TH_RV_Source1.py", "TH_RV_Source2.py", "TH_RV_Source3.py", "TH_RV_Source4.py"]:
            command.extend(["-o", output_file])
        
        # Run the script
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["OUTPUT_DIR"] = output_dir  # Add environment variable for output directory
        
        # For scripts that don't accept output file as parameter, set it as env var
        if script_name == "TH_SO_Source1.py":
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
    
    processes = []
    for script in scripts:
        p = Process(target=run_script, args=(script, args.n, result_queue))
        processes.append(p)
        p.start()
    
    for p in processes:
        p.join()

def main():
    """Main function to run all Thailand scripts in parallel."""
    parser = argparse.ArgumentParser(description='Run Thailand scraper scripts in parallel')
    parser.add_argument('-n', type=int, help='Number of items to scrape per script')
    parser.add_argument('--combine-interval', type=int, default=5, help='Interval in minutes for combining Excel files')
    args = parser.parse_args()
    
    # Define the scripts to run
    scripts = [
        "TH_SO_Source1.py",
        "TH_RV_Source1.py",
        "TH_RV_Source2.py",  # This one runs in head mode
        "TH_RV_Source3.py",
        "TH_RV_Source4.py"
    ]
    
    # Create a queue for results
    result_queue = Queue()
    
    # Start the periodic combination thread
    combine_thread = threading.Thread(
        target=periodic_combine,
        args=(args.combine_interval, output_dir, "Combined_Trade_In_Values.xlsx")
    )
    combine_thread.daemon = True
    combine_thread.start()
    
    try:
        # Run all scripts in parallel
        run_batch(scripts, args, result_queue, 1)
        
        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        # Print summary
        logger.info("\nScript Execution Summary:")
        for script_name, success, runtime in results:
            status = "Success" if success else "Failed"
            logger.info(f"{script_name}: {status} (Runtime: {runtime})")
        
        # Final combination of files
        excel_files = find_excel_files(output_dir)
        if excel_files:
            combine_excel_files(excel_files, os.path.join(output_dir, "Combined_Trade_In_Values.xlsx"))
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping...")
    finally:
        # Stop the periodic combination thread
        global stop_combining
        stop_combining = True
        combine_thread.join(timeout=1)
        
        logger.info("Script execution completed")

if __name__ == "__main__":
    main() 