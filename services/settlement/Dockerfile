FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

COPY services/settlement/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/settlement/src/ /app/

EXPOSE 8004

CMD ["python", "main.py"]
