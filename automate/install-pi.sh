#!/usr/bin/env bash
# ============================================================================
# ClimaZone — Installation de l'automate sur Raspberry Pi 5 (Étape 1)
# ----------------------------------------------------------------------------
# Installe Docker, récupère le code, génère la configuration (.env),
# détecte le convertisseur USB-RS485 (gainable) et démarre l'application.
#
# Utilisation (sur le Raspberry, dans un terminal) :
#   bash install-pi.sh <URL_DEPOT_GITHUB>
#
# Exemple :
#   bash install-pi.sh https://github.com/mon-compte/zoneclimate.git
# ============================================================================
set -euo pipefail

REPO_URL="${1:-}"
APP_DIR="${HOME}/zoneclimate"

say() { echo -e "\n\033[1;36m▶ $*\033[0m"; }
ok()  { echo -e "\033[1;32m✓ $*\033[0m"; }
warn(){ echo -e "\033[1;33m! $*\033[0m"; }

if [ -z "${REPO_URL}" ] && [ ! -d "${APP_DIR}/.git" ]; then
  echo "Usage : bash install-pi.sh <URL_DEPOT_GITHUB>"
  echo "Exemple : bash install-pi.sh https://github.com/mon-compte/zoneclimate.git"
  exit 1
fi

# 1) Docker ------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  say "Installation de Docker (cela peut prendre quelques minutes)…"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "${USER}"
  ok "Docker installé. (Un redémarrage de session sera nécessaire pour l'usage sans sudo.)"
else
  ok "Docker déjà présent."
fi

# git
if ! command -v git >/dev/null 2>&1; then
  say "Installation de git…"
  sudo apt-get update -y && sudo apt-get install -y git
fi

# 2) Récupération du code ----------------------------------------------------
if [ -d "${APP_DIR}/.git" ]; then
  say "Mise à jour du code existant…"
  git -C "${APP_DIR}" pull
else
  say "Clonage du dépôt…"
  git clone "${REPO_URL}" "${APP_DIR}"
fi
cd "${APP_DIR}"
ok "Code prêt dans ${APP_DIR}"

# 3) Détection du convertisseur USB-RS485 (gainable) -------------------------
say "Détection du convertisseur USB-RS485…"
RS485_DEVICE=""
for d in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 /dev/ttyACM1; do
  if [ -e "$d" ]; then RS485_DEVICE="$d"; break; fi
done
if [ -n "${RS485_DEVICE}" ]; then
  ok "Convertisseur RS485 détecté sur ${RS485_DEVICE}"
else
  warn "Aucun convertisseur RS485 détecté. Branchez le module USB-RS485 puis relancez ce script."
  warn "L'app démarrera quand même ; le gainable ne sera pilotable qu'une fois le module branché."
  RS485_DEVICE="/dev/ttyUSB0"
fi

# 4) Configuration .env ------------------------------------------------------
if [ ! -f "${APP_DIR}/.env" ]; then
  say "Création de la configuration (.env)…"
  read -rp "  Email administrateur [admin@climazone.fr] : " ADMIN_EMAIL
  ADMIN_EMAIL="${ADMIN_EMAIL:-admin@climazone.fr}"
  read -rsp "  Mot de passe administrateur (min 8 car.) : " ADMIN_PASSWORD; echo
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin1234!}"
  JWT_SECRET="$(openssl rand -hex 32)"
  TUYA_ENC_KEY="$(head -c 32 /dev/urandom | base64 | tr '+/' '-_')"
  cat > "${APP_DIR}/.env" <<EOF
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
JWT_SECRET=${JWT_SECRET}
TUYA_ENC_KEY=${TUYA_ENC_KEY}
RS485_DEVICE=${RS485_DEVICE}
INAPP_UPDATE_ENABLED=true
EOF
  ok "Configuration écrite dans ${APP_DIR}/.env"
else
  # Met à jour uniquement le port RS485 détecté
  if grep -q '^RS485_DEVICE=' "${APP_DIR}/.env"; then
    sed -i "s#^RS485_DEVICE=.*#RS485_DEVICE=${RS485_DEVICE}#" "${APP_DIR}/.env"
  else
    echo "RS485_DEVICE=${RS485_DEVICE}" >> "${APP_DIR}/.env"
  fi
  ok "Configuration .env existante conservée (port RS485 mis à jour : ${RS485_DEVICE})."
fi

# 4b) Nom réseau fixe : http://<nom>.local (mDNS / avahi) ------------------
DEFAULT_HOST="zoneclimate"
read -rp "Nom réseau de cet automate [${DEFAULT_HOST}] (unique si plusieurs Pi) : " AUTOMATE_NAME
AUTOMATE_NAME="$(echo "${AUTOMATE_NAME:-$DEFAULT_HOST}" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')"
[ -z "${AUTOMATE_NAME}" ] && AUTOMATE_NAME="${DEFAULT_HOST}"
say "Configuration du nom réseau « ${AUTOMATE_NAME}.local »…"
sudo hostnamectl set-hostname "${AUTOMATE_NAME}" 2>/dev/null || true
sudo sed -i "s/^127.0.1.1.*/127.0.1.1\t${AUTOMATE_NAME}/" /etc/hosts 2>/dev/null || \
  echo "127.0.1.1	${AUTOMATE_NAME}" | sudo tee -a /etc/hosts >/dev/null || true
sudo apt-get install -y avahi-daemon >/dev/null 2>&1 || true
sudo systemctl enable --now avahi-daemon 2>/dev/null || true
sudo systemctl restart avahi-daemon 2>/dev/null || true
ok "Nom réseau : http://${AUTOMATE_NAME}.local"

# 5) Démarrage de l'application (téléchargement des images pré-construites) --
say "Téléchargement et démarrage des conteneurs (aucune compilation)…"
sudo docker compose -f docker-compose.pi.yml up -d

# 5b) Service systemd : auto-démarrage + auto-réparation au boot (HORS-LIGNE) -
# Recrée les conteneurs manquants à chaque démarrage SANS Internet
# (pull_policy: missing → utilise les images déjà téléchargées).
say "Installation du démarrage automatique (auto-réparation au boot)…"
sudo tee /etc/systemd/system/zoneclimate.service >/dev/null <<UNIT
[Unit]
Description=ClimaZone (automate gainable) — démarrage auto
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/docker compose -f docker-compose.pi.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.pi.yml stop
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable zoneclimate.service 2>/dev/null || true
ok "Démarrage automatique activé : l'app remonte seule à chaque redémarrage, même sans Internet."

# 5c) Firmware Pi 5 : démarrage automatique après une coupure de courant --------
if [ -f "${APP_DIR}/automate/enable-autoboot.sh" ]; then
  say "Réglage du démarrage auto après coupure de courant (firmware Pi 5)…"
  sudo bash "${APP_DIR}/automate/enable-autoboot.sh" || true
fi

echo
PI_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
ok "============================================================"
ok " ClimaZone est installé et démarré sur l'automate."
ok " Nom fixe (recommandé)  :  http://${AUTOMATE_NAME}.local"
ok " Sur le Pi              :  http://localhost"
if [ -n "${PI_IP}" ]; then
  ok " Depuis un téléphone/PC :  http://${PI_IP}"
fi
ok " Connectez-vous avec le compte administrateur défini plus haut."
ok "============================================================"
echo
echo "Prochaines étapes :"
echo "  • Brancher le gainable au module RS485 (A→A, B→B, GND→GND)."
echo "  • Onglet Zones → « Gainable Modbus » → Activer → Détecter → Tester."
echo "  • Écran tactile : lancer  sudo bash automate/kiosk-setup.sh \"http://localhost:3000/ecran/<ID_INSTALLATION>\""
echo "  • Point d'accès Wi-Fi « ZONING VALSON » (nécessite une clé USB Wi-Fi) :"
echo "       sudo bash automate/wifi-ap-setup.sh"
