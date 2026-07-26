FROM python:3.11-slim

WORKDIR /app/backend

# Dépendances système : build (cryptography) + nmcli (gestion Wi-Fi de l'automate)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    network-manager \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
