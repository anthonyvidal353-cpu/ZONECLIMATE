FROM python:3.11-slim

WORKDIR /app/backend

# Dépendances système : build (cryptography) + nmcli (Wi-Fi) + rtl_433/rtl-sdr (capture RF 868 MHz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    network-manager \
    git \
    rtl-433 \
    rtl-sdr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
