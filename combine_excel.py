import os
import pandas as pd
import glob

def combine_excel_files(input_dir, output_file):
    """Combine all Excel files in the input directory into a single output file."""
    print(f"Looking for Excel files in: {input_dir}")
    
    # Find all Excel files in the directory
    excel_files = glob.glob(os.path.join(input_dir, "MY_*.xlsx"))
    print(f"Found {len(excel_files)} Excel files to combine.")
    
    # Create an empty DataFrame to store the combined data
    combined_df = pd.DataFrame()
    
    # Read each Excel file and append to the combined DataFrame
    for file in excel_files:
        try:
            print(f"Processing file: {os.path.basename(file)}")
            df = pd.read_excel(file)
            print(f"  - Read {len(df)} rows")
            combined_df = pd.concat([combined_df, df], ignore_index=True)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    # Save the combined DataFrame to a new Excel file
    if not combined_df.empty:
        print(f"Saving {len(combined_df)} total rows to {output_file}")
        combined_df.to_excel(output_file, index=False)
        print(f"Successfully saved combined file to: {output_file}")
    else:
        print("No data to combine.")

if __name__ == "__main__":
    # Set the input and output paths
    # This assumes the script is run from the same directory as the output folder
    input_dir = "/Users/ashutoshmitra/Downloads/asurion/tradeinselloffcloud/scripts/Malaysia/output"
    output_file = os.path.join(input_dir, "/Users/ashutoshmitra/Downloads/asurion/tradeinselloffcloud/scripts/Malaysia/output/Combined_Trade_In_Values.xlsx")
    
    # Run the combination function
    combine_excel_files(input_dir, output_file)