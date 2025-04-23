#!/usr/bin/env python
import os
import time
import subprocess
import logging
import sys
from datetime import datetime
import argparse
import pandas as pd

# Add the current directory to the path to import modules from scripts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scraper_manager")

def run_script(script_name, n_scrape=None):
    """Run a Python script and log the output."""
    logger.info(f"Starting {script_name}")
    try:
        # Get the full path to the script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
        
        # Prepare command with optional argument
        command = ["python", script_path]
        if n_scrape is not None:
            command.extend(["-n", str(n_scrape)])
        
        # Run the script
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        process = subprocess.Popen(
            command, 
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Stream the output
        for line in process.stdout:
            print(line, end='')
            
        process.wait()
        
        if process.returncode == 0:
            logger.info(f"Successfully completed {script_name}")
            return True
        else:
            logger.error(f"Failed to run {script_name} with return code {process.returncode}")
            return False
            
    except Exception as e:
        logger.error(f"Error running {script_name}: {e}")
        return False

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
    
    # Save the combined DataFrame to a new Excel file
    if not combined_df.empty:
        combined_df.to_excel(output_file, index=False)
        logger.info(f"Saved {len(combined_df)} rows to {output_file}")
        return output_file
    else:
        logger.warning("No data to combine")
        return None

def main():
    """Run all scrapers and send email with combined results."""
    start_time = datetime.now()
    logger.info(f"Starting scraping job at {start_time}")
    
    # Get the number of scrapes from command line arguments
    parser = argparse.ArgumentParser(description='Run all scrapers')
    parser.add_argument('-n', type=int, help='Number of items to scrape (for testing)', default=None)
    parser.add_argument('-c', '--combined', type=str, help='Name of the combined output file', 
                       default="Combined_Trade_In_Values.xlsx")
    parser.add_argument('--no-combine', action='store_true', help='Do not combine results into a single file')
    args = parser.parse_args()
    
    # Run each scraper with the specified limit
    samsung_result = run_script("samsung_scrape.py", args.n)
    compasia_result = run_script("scrape_and_save.py", args.n)
    starhub_result = run_script("starhub_scrape.py", args.n)
    singtel_result = run_script("singtel_scrape.py", args.n)
    
    # Collect individual files
    files_to_send = []
    individual_files = []
    
    if samsung_result and os.path.exists("Samsung_Trade_In_Values.xlsx"):
        individual_files.append("Samsung_Trade_In_Values.xlsx")
    
    if compasia_result and os.path.exists("tradein_values.xlsx"):
        individual_files.append("tradein_values.xlsx")
    
    if starhub_result and os.path.exists("starhub_tradein_values.xlsx"):
        individual_files.append("starhub_tradein_values.xlsx")
        
    if singtel_result and os.path.exists("singtel_tradein_values.xlsx"):
        individual_files.append("singtel_tradein_values.xlsx")
    
    # Combine files if requested
    combined_file = None
    if not args.no_combine and individual_files:
        combined_file = combine_excel_files(individual_files, args.combined)
        if combined_file:
            files_to_send.append(combined_file)
    else:
        # If not combining, send the individual files
        files_to_send.extend(individual_files)
    
    # Send email if we have files
    if files_to_send:
        logger.info(f"Sending email with {len(files_to_send)} files: {files_to_send}")
        try:
            # Import the send_email function from the same directory
            from send_email import send_email
            
            # Build email subject and text
            subject = f"Trade-In Values Update - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Create message body based on what we're sending
            if combined_file and not args.no_combine:
                text = (f"Scraping completed at {datetime.now()}. All trade-in values have been combined into "
                       f"a single file: {combined_file}.")
            else:
                text = (f"Scraping completed at {datetime.now()}. Attached are the following files: "
                       f"{', '.join(files_to_send)}")
            
            # Send the email
            send_email(
                subject=subject,
                text=text,
                files=files_to_send
            )
            logger.info("Email sent successfully")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    else:
        logger.warning("No files were generated. Not sending email.")
    
    end_time = datetime.now()
    logger.info(f"Completed scraping job at {end_time}. Total runtime: {end_time - start_time}")

if __name__ == "__main__":
    main()