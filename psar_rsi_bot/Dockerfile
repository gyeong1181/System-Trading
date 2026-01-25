FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Default: live paper mode on 1h. Override with docker-compose or docker run args.
CMD ["python", "psar_rsi_strategy.py", "--live", "--paper", "--symbol", "BTCUSDT", "--interval", "1h"]
