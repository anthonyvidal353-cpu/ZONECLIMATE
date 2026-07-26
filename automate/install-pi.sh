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

# 5) Démarrage de l'application ---------------------------------------------
say "Construction et démarrage des conteneurs (Docker)…"
sudo docker compose -f docker-compose.yml -f docker-compose.pi.yml up -d --build

echo
ok "============================================================"
ok " ClimaZone est installé et démarré sur l'automate."
ok " Ouvrez le navigateur du Pi sur :  http://localhost:3000"
ok " Connectez-vous avec le compte administrateur défini plus haut."
ok "============================================================"
echo
echo "Prochaines étapes :"
echo "  • Brancher le gainable au module RS485 (A→A, B→B, GND→GND)."
echo "  • Onglet Zones → « Gainable Modbus » → Activer → Détecter → Tester."
echo "  • Écran tactile : lancer  sudo bash automate/kiosk-setup.sh \"http://localhost:3000/ecran/<ID_INSTALLATION>\""
echo "  • Point d'accès Wi-Fi « ZONING VALSON » (nécessite une clé USB Wi-Fi) :"
echo "       sudo bash automate/wifi-ap-setup.sh"
