# Trade-In Value Scraper

This repository contains a script that scrapes smartphone trade-in values from compasiatradeinsg.com and several other websites and saves them to an Excel file.

## Features

- Automatically scrapes trade-in values for different smartphone brands, models, and conditions
- Runs every 7 days via GitHub Actions
- Saves results to an Excel file and commits it to the repository
- Emails the Excel file after each run

## Files

- `scrape_and_save.py`: The main scraping script
- `send_email.py`: Script to send the Excel file via email
- `.github/workflows/scrape-tradein.yml`: GitHub Actions workflow configuration

## Setup

1. Fork or clone this repository
2. Add your email password as a GitHub secret with the name `EMAIL_PASSWORD`
3. If needed, update the email configuration in `send_email.py`
4. The scraper will run automatically every 7 days, or you can manually trigger it from the Actions tab

## Email Configuration

This project uses Gmail SMTP to send emails. You need to:

1. Use an app password if you have 2FA enabled on your Gmail account
2. Store this password in GitHub Secrets as `EMAIL_PASSWORD`

## Manual Execution

You can manually trigger the workflow from the GitHub Actions tab in your repository.