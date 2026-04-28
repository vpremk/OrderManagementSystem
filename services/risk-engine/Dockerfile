FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

COPY services/risk-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/risk-engine/src/ /app/

EXPOSE 8000

CMD ["python", "main.py"]
