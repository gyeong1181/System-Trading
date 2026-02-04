import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "app.log"


def parse_errors_last_24h():
    if not LOG_FILE.exists():
        print("app.log not found")
        return

    cutoff = datetime.now() - timedelta(days=1)
    counts = Counter()

    with LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if ts < cutoff:
                continue
            if "ERROR" in line or "WARNING" in line:
                m = re.search(r"status=(\d{3})", line)
                key = f"HTTP_{m.group(1)}" if m else "GENERAL"
                counts[key] += 1

    print("Error stats (last 24h)")
    for k, v in counts.most_common():
        print(f"{k}: {v}")


if __name__ == "__main__":
    parse_errors_last_24h()
