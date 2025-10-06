FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY project ./project
COPY tests ./tests
COPY config.yaml ./config.yaml

RUN pip install --upgrade pip && \
    if [ -f project/requirements.txt ]; then pip install -r project/requirements.txt; fi && \
    pip install --no-cache-dir "pytest"

CMD ["python", "-m", "project.main"]
