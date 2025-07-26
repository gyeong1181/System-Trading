import requests
import os

base_url = "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1h/"
save_dir = "D:/코딩/자동매매/EMA+RSI/binance_data"
start_date = "2024-01-01"
end_date = "2025-05-01"

from datetime import datetime, timedelta

def daterange(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)

start = datetime.strptime(start_date, "%Y-%m-%d")
end = datetime.strptime(end_date, "%Y-%m-%d")

for date in daterange(start, end):
    date_str = date.strftime("%Y-%m-%d")
    filename = f"BTCUSDT-1h-{date_str}.zip" 
    url = base_url + filename
    save_path = os.path.join(save_dir, filename)

    if not os.path.exists(save_path):
        r = requests.get(url)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            print(f"Downloaded {filename}")
        else:
            print(f"Failed to download: {filename}")
    else:
        print(f"Already exists: {filename}")
