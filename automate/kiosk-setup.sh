#!/usr/bin/env bash
# ============================================================================
# ClimaZone — Mode borne tactile (kiosque) pour l'automate (Raspberry Pi)
# ----------------------------------------------------------------------------
# Configure le Raspberry Pi pour démarrer AUTOMATIQUEMENT en plein écran sur
# l'application dès la mise sous tension (Chromium en mode kiosque).
#
# Utilisation :
#   sudo bash kiosk-setup.sh "http://localhost:3000/ecran/<ID_INSTALLATION>"
#
# Exemple :
#   sudo bash kiosk-setup.sh "http://localhost:3000/ecran/8dd6f7e4-9919-4c5b-8f0c-8c395a389896"
#
# Testé sur Raspberry Pi OS (Bookworm, X11/LXDE). Pour Wayland (labwc/wayfire),
# voir README-ecran.md.
# ============================================================================
set -euo pipefail

KIOSK_URL="${1:-http://localhost:3000}"
KIOSK_USER="${SUDO_USER:-pi}"
AUTOSTART_DIR="/home/${KIOSK_USER}/.config/lxsession/LXDE-pi"
CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium || echo /usr/bin/chromium-browser)"

echo "→ URL kiosque : ${KIOSK_URL}"
echo "→ Utilisateur : ${KIOSK_USER}"

# 1) Dépendances (navigateur + masquage du curseur + gestion écran)
apt-get update -y
apt-get install -y chromium-browser unclutter x11-xserver-utils || \
  apt-get install -y chromium unclutter x11-xserver-utils

# 2) Fichier d'autostart LXDE
mkdir -p "${AUTOSTART_DIR}"
cat > "${AUTOSTART_DIR}/autostart" <<EOF
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 0.5 -root
@${CHROMIUM_BIN} --noerrdialogs --disable-infobars --kiosk --check-for-update-interval=31536000 --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required "${KIOSK_URL}"
EOF
chown -R "${KIOSK_USER}:${KIOSK_USER}" "/home/${KIOSK_USER}/.config"

echo "→ Autostart écrit dans ${AUTOSTART_DIR}/autostart"

# 3) Connexion automatique au bureau (raspi-config non interactif)
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_boot_behaviour B4 || true   # B4 = bureau + auto-login
fi

echo ""
echo "✅ Terminé. Redémarrez l'automate : sudo reboot"
echo "   Au démarrage, l'écran affichera directement ClimaZone en plein écran."
echo "   (Anti-veille écran activé + curseur masqué. Le mode borne masque aussi"
echo "    la barre du navigateur ; l'anti-veille logiciel Wake Lock est géré par l'app.)"
