#!/usr/bin/env bash
# ============================================================================
# ClimaZone — Réseau Wi-Fi « ZONECLIMATE » + portail captif
# ----------------------------------------------------------------------------
# L'automate diffuse son propre Wi-Fi « ZONECLIMATE » (via la clé USB).
# En s'y connectant, le téléphone ouvre AUTOMATIQUEMENT la page de connexion.
# L'internet de la maison reste sur l'antenne interne et est PARTAGÉ, pour que
# les appareils Tuya connectés à « ZONECLIMATE » puissent s'appairer.
#
# Prérequis : 2 antennes Wi-Fi (interne = internet maison, clé USB = AP).
# Utilisation : sudo bash wifi-ap-setup.sh
# Testé sur Raspberry Pi OS Bookworm (NetworkManager).
# ============================================================================
set -euo pipefail

AP_SSID="ZONECLIMATE"
CON_NAME="zoneclimate-ap"
GW="10.42.0.1"   # passerelle par défaut du mode partagé NetworkManager
DNSMASQ_DIR="/etc/NetworkManager/dnsmasq-shared.d"
DNSMASQ_FILE="${DNSMASQ_DIR}/zoneclimate-captive.conf"

if [ "$(id -u)" -ne 0 ]; then echo "Lancez avec sudo : sudo bash wifi-ap-setup.sh"; exit 1; fi
if ! command -v nmcli >/dev/null 2>&1; then
  echo "NetworkManager (nmcli) introuvable (activez-le via raspi-config)."; exit 1
fi

# Interface qui porte l'internet (route par défaut) → on garde celle-là pour internet
INTERNET_IFACE="$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
echo "Interface internet détectée : ${INTERNET_IFACE:-inconnue}"

echo "Interfaces Wi-Fi disponibles :"
mapfile -t WIFI_IFACES < <(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1}')
for i in "${WIFI_IFACES[@]}"; do echo "  - $i"; done

# Candidate AP = une interface Wi-Fi différente de celle qui porte l'internet
AP_DEFAULT=""
for i in "${WIFI_IFACES[@]}"; do
  if [ "$i" != "${INTERNET_IFACE}" ]; then AP_DEFAULT="$i"; break; fi
done
[ -z "${AP_DEFAULT}" ] && AP_DEFAULT="${WIFI_IFACES[0]:-wlan1}"

read -rp "Interface pour le réseau « ${AP_SSID} » [${AP_DEFAULT}] : " AP_IFACE
AP_IFACE="${AP_IFACE:-$AP_DEFAULT}"
read -rsp "Mot de passe du réseau « ${AP_SSID} » (min 8 caractères) : " AP_PASS; echo
if [ "${#AP_PASS}" -lt 8 ]; then echo "Mot de passe trop court (min 8)."; exit 1; fi

# 1) Portail captif : SEULES les URL de détection pointent vers l'automate.
#    (Le reste du DNS est forwardé normalement → Tuya garde internet.)
echo "→ Configuration du portail captif…"
mkdir -p "${DNSMASQ_DIR}"
cat > "${DNSMASQ_FILE}" <<EOF
# Redirige uniquement les vérifications de connectivité vers l'automate (${GW})
address=/connectivitycheck.gstatic.com/${GW}
address=/connectivitycheck.android.com/${GW}
address=/clients3.google.com/${GW}
address=/clients.l.google.com/${GW}
address=/captive.apple.com/${GW}
address=/www.msftconnecttest.com/${GW}
address=/msftconnecttest.com/${GW}
address=/www.msftncsi.com/${GW}
address=/connect.rom.miui.com/${GW}
address=/detectportal.firefox.com/${GW}
address=/connectivity-check.ubuntu.com/${GW}
address=/nmcheck.gnome.org/${GW}
EOF

# 2) Création du point d'accès « ZONECLIMATE » (avec partage internet)
echo "→ Création du réseau « ${AP_SSID} » sur ${AP_IFACE}…"
# Liaison par ADRESSE MAC (et non par nom wlanX) : indispensable car le Pi
# inverse parfois wlan0/wlan1 au redémarrage. Ainsi l'AP retrouve TOUJOURS la
# bonne antenne, quel que soit l'ordre d'énumération.
AP_MAC=$(cat /sys/class/net/${AP_IFACE}/address 2>/dev/null)
nmcli connection delete "${CON_NAME}" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "${AP_IFACE}" con-name "${CON_NAME}" autoconnect yes ssid "${AP_SSID}"
nmcli connection modify "${CON_NAME}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  ipv4.method shared \
  connection.autoconnect yes \
  connection.autoconnect-priority 10 \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "${AP_PASS}"
# Épingler par MAC (stable au reboot) et NE PAS figer le nom d'interface.
if [ -n "${AP_MAC}" ]; then
  nmcli connection modify "${CON_NAME}" 802-11-wireless.mac-address "${AP_MAC}" connection.interface-name ""
fi
nmcli connection up "${CON_NAME}"

# NB : le mode « shared » fournit un DHCP + DNS LOCAUX même SANS Internet.
# Le zoning reste donc pilotable box éteinte, sur http://10.42.0.1

echo
echo "✅ Réseau « ${AP_SSID} » actif sur ${AP_IFACE}."
echo "   • Connectez votre téléphone au Wi-Fi « ${AP_SSID} » → la page de connexion"
echo "     ClimaZone devrait s'ouvrir automatiquement."
echo "   • Si elle ne s'ouvre pas, ouvrez le navigateur sur : http://${GW}"
echo "   • Appairez aussi vos appareils Tuya sur ce réseau (ils gardent internet)."
echo "   • Arrêter  : sudo nmcli connection down ${CON_NAME}"
echo "   • Supprimer: sudo nmcli connection delete ${CON_NAME} && sudo rm -f ${DNSMASQ_FILE}"
