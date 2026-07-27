#!/usr/bin/env bash
# ============================================================================
# ClimaZone — Mise à jour de l'automate (méthode fiable, à lancer sur le Pi)
#   Usage :  cd zoneclimate && sudo bash automate/update.sh
# ============================================================================
set -e

# Se placer à la racine du dépôt (le dossier parent de ce script)
cd "$(dirname "$0")/.."
REPO="$(pwd)"
COMPOSE="docker-compose.pi.yml"

echo "=========================================="
echo "  ClimaZone — Mise a jour de l'automate"
echo "=========================================="
echo "Depot : ${REPO}"
echo ""

echo "→ 1/4 Recuperation de la derniere version..."
git config --global --add safe.directory "${REPO}" 2>/dev/null || true
git fetch --all --prune
git reset --hard "@{u}" 2>/dev/null || git reset --hard origin/main
echo "   Version : $(git rev-parse --short HEAD)"
echo ""

echo "→ 2/4 Telechargement des images (peut prendre 15-20 min)..."
docker compose -f "${COMPOSE}" pull
echo ""

echo "→ 3/4 Redemarrage de l'application..."
docker compose -f "${COMPOSE}" up -d
echo ""

echo "→ 4/4 Rechargement du proxy (portail captif)..."
docker compose -f "${COMPOSE}" restart proxy || true
echo ""

echo "=========================================="
echo "  ✅ Mise a jour terminee !"
echo "  Rechargez l'application dans le navigateur."
echo "=========================================="
