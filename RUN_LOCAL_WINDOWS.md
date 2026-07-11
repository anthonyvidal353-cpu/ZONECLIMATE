# 🖥️ Lancer ZoneClimate sur votre PC (Windows + Docker) — en 5 minutes

Ce guide vous permet de tester ZoneClimate **en local, sur le même réseau que vos
appareils Tuya**, avant d'investir dans un Raspberry Pi. Votre PC joue le rôle du Pi.

> ⚠️ Important : pour piloter vos appareils en local, votre **PC doit être connecté
> au même Wi-Fi** que le gainable et les thermostats.

---

## 1) Prérequis (une seule fois)
1. Installez **Docker Desktop pour Windows** : https://www.docker.com/products/docker-desktop/
2. Ouvrez Docker Desktop et attendez qu'il affiche **« Engine running »**.
3. Récupérez le dossier du projet ZoneClimate sur votre PC (bouton **« Save to GitHub »**
   dans Emergent, puis `git clone`, ou téléchargez le code).

## 2) Configurer les clés (fichier `.env`)
1. À la racine du projet, copiez `.env.example` en **`.env`**.
2. Générez une **clé de chiffrement Fernet**. Dans un terminal PowerShell :
   ```powershell
   docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Copiez la valeur affichée dans `TUYA_ENC_KEY=` du fichier `.env`.
3. Mettez un `JWT_SECRET` (n'importe quelle longue chaîne) et, si vous voulez,
   changez `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## 3) Démarrer l'application
Dans un terminal, placez-vous dans le dossier du projet puis :
```powershell
docker compose up -d --build
```
Le premier lancement compile les images (quelques minutes). Ensuite :
- **Application** : http://localhost:3000
- **API** : http://localhost:8001/api

Connectez-vous avec `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## 4) Récupérer les appareils et les clés locales
1. Allez dans **Paramètres** (super admin) → **Projets API** → ajoutez votre projet Tuya
   (Access ID + Secret depuis https://iot.tuya.com).
2. Toujours dans **Paramètres** → carte **« Pilotage local »** → cliquez sur
   **« Récupérer les clés »**. ZoneClimate télécharge (une seule fois via le cloud) les
   `local_key` de vos appareils et les **chiffre**.
3. Cliquez sur **« Scanner le LAN »** pour trouver l'IP de chaque appareil, puis
   **« Tester en local »** sur un appareil pour vérifier la communication directe.

---

## ⚠️ Limite connue sous Windows/Docker Desktop
Le **scan LAN (broadcast UDP)** peut ne rien trouver depuis un conteneur Docker sous
Windows (le réseau est isolé). Deux solutions :
- La récupération des clés via le cloud renvoie souvent déjà l'IP → le test local
  fonctionne alors directement.
- Pour un scan LAN **100 % fiable**, utilisez le **Raspberry Pi (Linux)** en mode réseau hôte :
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.pi.yml up -d --build
  ```

## 🌍 Accès à distance (plus tard, sur le Pi)
Installez **Tailscale** (gratuit) sur le Pi : vous pilotez ZoneClimate depuis n'importe où,
sans ouvrir de port sur votre box. Guide : https://tailscale.com/kb/

## 🛠️ Commandes utiles
```powershell
docker compose logs -f backend     # voir les logs backend
docker compose logs -f frontend    # voir les logs frontend
docker compose down                # arrêter
docker compose up -d --build       # redémarrer après mise à jour
```
