FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

COPY services/market-data-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/market-data-service/src/ /app/

EXPOSE 9877 8000

CMD ["python", "main.py"]
