#!/usr/bin/env bash
# ============================================================================
# ClimaZone — Point d'accès Wi-Fi « ZONING VALSON » (Étape 2 — double Wi-Fi)
# ----------------------------------------------------------------------------
# Crée un réseau Wi-Fi « ZONING VALSON » diffusé par l'automate, réservé aux
# appareils Tuya (gainable/thermostats/vannes), pendant que l'automate reste
# connecté au Wi-Fi de la maison (internet) via l'AUTRE antenne.
#
# ⚠️ PRÉREQUIS : DEUX antennes Wi-Fi.
#   - Le Pi 5 n'a qu'une puce Wi-Fi interne (wlan0).
#   - Il faut donc une CLÉ USB Wi-Fi (wlan1) pour faire les deux en même temps.
#   Recommandé : point d'accès sur l'antenne INTERNE (wlan0, la plus stable),
#   et internet maison sur la CLÉ USB (wlan1). Ce script suit cette logique.
#
# Utilisation :
#   sudo bash wifi-ap-setup.sh
#
# Testé sur Raspberry Pi OS Bookworm (NetworkManager).
# ============================================================================
set -euo pipefail

AP_SSID="ZONING VALSON"
AP_IFACE_DEFAULT="wlan0"     # antenne interne pour l'AP (recommandé)
CON_NAME="zoning-valson"

if [ "$(id -u)" -ne 0 ]; then echo "Lancez avec sudo : sudo bash wifi-ap-setup.sh"; exit 1; fi
if ! command -v nmcli >/dev/null 2>&1; then
  echo "NetworkManager (nmcli) introuvable. Sur Bookworm il est présent par défaut."
  echo "Activez-le : sudo raspi-config → Advanced → Network Config → NetworkManager."
  exit 1
fi

echo "Interfaces Wi-Fi détectées :"
nmcli -t -f DEVICE,TYPE device | grep ':wifi' | cut -d: -f1 | sed 's/^/  - /'
echo
echo "Connexions Wi-Fi actives (qui porte internet ?) :"
nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device | grep ':wifi:' | \
  awk -F: '{printf "  - %s : %s (%s)\n", $1, $4, $3}'
echo
echo "→ Conseil : mettez le Wi-Fi de la MAISON (internet) sur la CLÉ USB,"
echo "  et gardez l'antenne INTERNE (wlan0) pour le point d'accès."

read -rp "Interface pour le POINT D'ACCÈS « ZONING VALSON » [${AP_IFACE_DEFAULT}] : " AP_IFACE
AP_IFACE="${AP_IFACE:-$AP_IFACE_DEFAULT}"
read -rsp "Mot de passe du réseau « ZONING VALSON » (min 8 caractères) : " AP_PASS; echo
if [ "${#AP_PASS}" -lt 8 ]; then echo "Mot de passe trop court (min 8)."; exit 1; fi

echo "→ Création du point d'accès « ${AP_SSID} » sur ${AP_IFACE}…"
nmcli connection delete "${CON_NAME}" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "${AP_IFACE}" con-name "${CON_NAME}" autoconnect yes ssid "${AP_SSID}"
nmcli connection modify "${CON_NAME}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  ipv4.method shared \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "${AP_PASS}"
nmcli connection up "${CON_NAME}"

echo
echo "✅ Point d'accès « ${AP_SSID} » actif sur ${AP_IFACE} (DHCP + partage internet automatiques)."
echo "   • Connectez vos appareils Tuya (SmartLife) à ce réseau lors de l'appairage."
echo "   • Gardez l'internet de la maison sur l'AUTRE antenne (clé USB Wi-Fi)."
echo "   • Pour arrêter :  sudo nmcli connection down ${CON_NAME}"
echo "   • Pour supprimer : sudo nmcli connection delete ${CON_NAME}"
