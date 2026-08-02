#!/usr/bin/env bash
# =============================================================================
#  Démarrage AUTOMATIQUE du Raspberry Pi 5 après une coupure de courant.
#  À lancer UNE seule fois, en une ligne :
#      sudo bash automate/enable-autoboot.sh
#  (aucun éditeur à ouvrir, aucune manipulation)
# =============================================================================
set -e

if ! command -v rpi-eeprom-config >/dev/null 2>&1; then
  echo "→ rpi-eeprom-config introuvable (pas un Raspberry Pi ?). Rien à faire."
  exit 0
fi

echo "=============================================="
echo "  Réglage : démarrage auto après coupure"
echo "=============================================="

echo "→ 1/3 Mise à jour du firmware (bootloader)…"
rpi-eeprom-update -a || true

echo "→ 2/3 Application des réglages d'allumage…"
CONF="$(rpi-eeprom-config)"
NEW="$CONF"

upsert() {
  local key="$1" val="$2"
  if printf '%s\n' "$NEW" | grep -q "^${key}="; then
    NEW="$(printf '%s\n' "$NEW" | sed "s/^${key}=.*/${key}=${val}/")"
  else
    NEW="$(printf '%s\n%s=%s\n' "$NEW" "$key" "$val")"
  fi
}

# WAIT_FOR_POWER_BUTTON=0  -> le Pi démarre dès que le courant revient
# POWER_OFF_ON_HALT=0      -> comportement d'arrêt standard
upsert WAIT_FOR_POWER_BUTTON 0
upsert POWER_OFF_ON_HALT 0

TMP="$(mktemp)"
printf '%s\n' "$NEW" > "$TMP"
rpi-eeprom-config --apply "$TMP"
rm -f "$TMP"

echo "→ 3/3 Terminé."
echo
echo "=============================================="
echo "  ✅ Démarrage auto activé."
echo "  Redémarrez le Pi pour finaliser :  sudo reboot"
echo "  Puis testez : débranchez/rebranchez le courant,"
echo "  le Pi doit repartir seul (sans toucher au bouton)."
echo "=============================================="
