import requests
import datetime
import time
import json
import os
import random
from pathlib import Path

# Configuration
API_KEY = os.getenv("AIRNOW_API_KEY")
ZIP_CODE = "94720"
BASE_URL = "https://www.airnowapi.org/aq/observation/zipCode/historical/"
DATA_DIR = Path("data/airnow")
OUTPUT_FILE = DATA_DIR / "airnow_94720_400days.json"
TEMP_FILE = DATA_DIR / "airnow_94720_temp.json"
START_DATE = datetime.date(2024, 5, 5)
DAYS = 400
DISTANCE = 25
RATE_LIMIT_DELAY = 3  # Seconds between requests (more conservative)
MAX_RETRIES = 3

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Load existing data if available (for resuming)
all_results = []
last_processed_day = -1
if os.path.exists(TEMP_FILE):
    try:
        with open(TEMP_FILE, "r") as f:
            temp_data = json.load(f)
            all_results = temp_data.get("results", [])
            last_processed_day = temp_data.get("last_day", -1)
            print(f"Resuming from day {last_processed_day+1}, with {len(all_results)} records already collected.")
    except Exception as e:
        print(f"Error loading temp file: {e}")

# Process each day
for i in range(DAYS):
    # Skip already processed days if resuming
    if i <= last_processed_day:
        continue
        
    date = START_DATE - datetime.timedelta(days=i)
    date_str = date.strftime("%Y-%m-%dT00-0000")
    params = {
        "format": "application/json",
        "zipCode": ZIP_CODE,
        "date": date_str,
        "distance": DISTANCE,
        "API_KEY": API_KEY
    }
    
    # Try with retries
    success = False
    retries = 0
    while not success and retries < MAX_RETRIES:
        try:
            print(f"Fetching data for {date_str} (attempt {retries+1})...")
            response = requests.get(BASE_URL, params=params)
            
            # Handle rate limiting specifically
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RATE_LIMIT_DELAY * 2))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                retries += 1
                continue
                
            response.raise_for_status()
            data = response.json()
            if data:
                all_results.extend(data)
            print(f"Fetched data for {date_str}: {len(data)} records.")
            success = True
            
            # Save progress after each successful day
            with open(TEMP_FILE, "w") as f:
                json.dump({"results": all_results, "last_day": i}, f)
                
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error for {date_str}: {e}")
            retries += 1
            time.sleep(RATE_LIMIT_DELAY * 2)  # Wait longer on HTTP errors
            
        except Exception as e:
            print(f"Error fetching data for {date_str}: {e}")
            retries += 1
            time.sleep(RATE_LIMIT_DELAY)
    
    if not success:
        print(f"Failed to fetch data for {date_str} after {MAX_RETRIES} attempts. Continuing...")
    
    # Add jitter to avoid hitting rate limits
    sleep_time = RATE_LIMIT_DELAY + random.uniform(0.5, 1.5)
    print(f"Waiting {sleep_time:.2f} seconds before next request...")
    time.sleep(sleep_time)

# Save final results
with open(OUTPUT_FILE, "w") as f:
    json.dump(all_results, f, indent=2)

# Clean up temp file if successful
if os.path.exists(TEMP_FILE):
    os.remove(TEMP_FILE)

print(f"Done! Compiled {len(all_results)} records into {OUTPUT_FILE}.")
