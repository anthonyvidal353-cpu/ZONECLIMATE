# ClimaZone — Pilotage Gainable SMARTLIFE

## Problème initial
Application qui récupère les produits SMARTLIFE (Tuya) pour créer un zoning gainable.
Le gainable et les thermostats sans fil disposent de SMARTLIFE. L'utilisateur centralise
tout pour gérer la température zone par zone avec un thermostat maître (mode chaud/froid).

## Choix utilisateur (V1)
- Données SIMULÉES (mock) d'abord, API Tuya réelle plus tard
- Fonctionnalités : tableau de bord des zones + thermostat maître + consigne par zone + planning horaire
- Pas d'authentification
- Interface Français uniquement

## Architecture
- Backend : FastAPI + MongoDB (motor). Routes préfixées /api.
  - System (singleton), Zone, Device, ScheduleSlot
  - Seed au démarrage : 1 système, 6 zones, 7 appareils (1 gainable + 6 thermostats)
  - Simulation : POST /api/simulate/tick fait dériver les températures vers la consigne
- Frontend : React 19 + Tailwind + shadcn/ui + framer-motion + @phosphor-icons/react
  - Thème sombre "Command Center" (Cabinet Grotesk / IBM Plex Sans), orange=chaud, bleu=froid
  - App.js orchestre l'état, polling tick toutes les 4s

## Implémenté (2026-07-09)
- Thermostat maître : mode chaud/froid, allumer/éteindre, consigne générale +/-, vitesse ventilation
- Tableau de bord zones : temp actuelle, consigne +/- par zone, état registre, activation
- Appareils SmartLife (mock) : liste, batterie/signal/statut, bouton Synchroniser
- Planning : plages horaires par zone et par jour (ajout/suppression)
- Simulation temps réel des températures
- Tests : 100% backend (12 tests pytest), 100% frontend (Playwright)

## Backlog / prochaines étapes
- P0 : Brancher l'API réelle Tuya Cloud (Access ID/Secret) en remplacement du mock
- P1 : Application automatique des plages horaires (scheduler côté backend) sur les consignes
- P1 : Édition des créneaux existants, copie d'un jour à l'autre
- P2 : Association manuelle zone ↔ appareil, ajout/suppression de zones depuis l'UI
- P2 : Historique/graphiques de température (recharts), alertes hors ligne / batterie faible
