FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared package first (layer cache)
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

COPY services/fix-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy QuickFIX data dictionary
RUN python -c "import quickfix; import os; src=os.path.join(os.path.dirname(quickfix.__file__), 'spec', 'FIX44.xml'); \
    import shutil; shutil.copy(src, '/app/config/FIX44.xml')" 2>/dev/null || true

COPY services/fix-gateway/src/ /app/

EXPOSE 9876 8000

CMD ["python", "main.py"]
