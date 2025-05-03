# Trade-In & Sell-Off Value Scraper

This project collects and consolidates trade-in and sell-off values for electronic devices across four Southeast Asian countries: Singapore, Malaysia, Thailand, and Taiwan. It automates the data collection process from multiple sources to provide comprehensive pricing insights.

## Project Structure

```
├── Singapore/
│   ├── SG_RV_Source1.py - SG_RV_Source8.py   # Trade-in value scrapers
│   ├── SG_SO_Source1.py - SG_SO_Source3.py   # Sell-off value scrapers
│   ├── run_all_scrapers_parallel.py          # Parallel execution script
│   └── output/                               # Results directory
├── Malaysia/
│   ├── MY_RV_Source1.py - MY_RV_Source5.py   # Trade-in value scrapers
│   ├── MY_SO_Source1.py - MY_SO_Source3.py   # Sell-off value scrapers
│   ├── run_all_my_scrapers_parallel.py       # Parallel execution script
│   └── output/                               # Results directory
├── Thailand/
│   ├── TH_RV_Source*.py                      # Trade-in value scrapers
│   ├── TH_SO_Source*.py                      # Sell-off value scrapers
│   ├── run_all_th_scrapers_parallel.py       # Parallel execution script
│   └── output/                               # Results directory
├── Taiwan/
│   ├── TW_RV_Source*.py                      # Trade-in value scrapers
│   ├── TW_SO_Source*.py                      # Sell-off value scrapers
│   ├── run_all_tw_scrapers_parallel.py       # Parallel execution script
│   └── output/                               # Results directory
├── send_email.py                             # Email notification utility
└── requirements.txt                          # Python dependencies
```

## Naming Convention

- **Country Codes**: SG (Singapore), MY (Malaysia), TH (Thailand), TW (Taiwan)
- **Value Types**: RV (Resale Value/Trade-in), SO (Sell-Off)
- **Sources**: Source1, Source2, etc. (Different websites for each country)

## Features

- **Parallel Scraping**: Optimized multi-process execution
- **Automatic Consolidation**: Combines data from multiple sources
- **Periodic Saving**: Saves intermediate results during execution
- **Email Notifications**: Sends results upon completion
- **Detailed Logging**: Tracks execution time and errors
- **Flexible Configuration**: Command-line options for customization

## Usage

Each country has its own parallel execution script:

```bash
# Singapore
python Singapore/run_all_scrapers_parallel.py

# Malaysia
python Malaysia/run_all_my_scrapers_parallel.py

# Thailand
python Thailand/run_all_th_scrapers_parallel.py

# Taiwan
python Taiwan/run_all_tw_scrapers_parallel.py
```

### Command-Line Options

- `-n NUMBER`: Limit number of items to scrape per source (testing mode)
- `-c FILENAME`: Custom name for combined output file
- `--no-combine`: Skip combining results into a single file
- `-i MINUTES`: Interval for periodic file combination (default: 10)

## Output Format

All scrapers produce Excel files with a standardized format:

- Country
- Device Type
- Brand
- Model
- Capacity
- Color
- Launch RRP
- Condition
- Value Type
- Currency
- Value
- Source
- Updated on
- Updated by
- Comments

## Dependencies

Install required packages:
```bash
pip install -r requirements.txt
```

Key dependencies include:
- selenium
- pandas
- openpyxl
- webdriver_manager
- undetected_chromedriver (for sites with anti-bot protection)

## Email Configuration

Set the `EMAIL_PASSWORD` environment variable to enable email notifications:
```bash
export EMAIL_PASSWORD=your_email_password
```

## Troubleshooting

- Check the log files in each country's output directory
- Review script-specific error messages
- For sites with Cloudflare protection, use scripts with undetected_chromedriver