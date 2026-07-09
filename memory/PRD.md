# ClimaZone — Pilotage Gainable SMARTLIFE (multi-utilisateurs)

## Problème initial
Application qui récupère les produits SMARTLIFE (Tuya) pour créer un zoning gainable :
gérer la température zone par zone avec un thermostat maître (choix du mode chaud/froid),
sur une base de données simulées (mock) puis API Tuya réelle plus tard.

## Architecture
- Backend : FastAPI + MongoDB (motor), routes /api. Auth JWT (bcrypt + PyJWT), token en cookie httpOnly + body/Bearer.
- Frontend : React 19 + Tailwind + shadcn/ui + framer-motion + @phosphor-icons/react. Thème sombre.
- Multi-tenant : chaque « installation » (gainable + zones + thermostats) est isolée par installation_id.

## Rôles & permissions
- SUPER ADMIN : tout (voit tous les utilisateurs + installations, gère rôles, supprime).
- MODÉRATEUR : lecture globale (tous utilisateurs + installations), pas de modification.
- INSTALLATEUR : voit ses installations si installer_access=true ; crée des installations ; invite un client à devenir maître.
- CLIENT : propriétaire/maître de son installation ; contrôle complet ; invite des invités ; active/révoque l'accès installateur.
- INVITÉ : lecture seule.

## Implémenté (dates)
- 2026-07-09 : MVP zoning (thermostat maître = zone du gainable, mode chaud/froid, ventilation, arrêt total + arrêt zone, codes défauts + diagnostic, renommage zones, maître réassignable, appareils SmartLife mock, planning horaire par zone). Tests 100%.
- 2026-07-09 : Auth JWT + 5 rôles + multi-installations + invitations par code in-app + gestion utilisateurs (admin) + membres/accès installateur. Tests backend 31/31, frontend ~95% (2 correctifs LOW appliqués).

## Comptes de démo
Voir /app/memory/test_credentials.md (admin/moderateur/installateur/client/invite).

## Backlog / prochaines étapes
- P0 : Brancher l'API Tuya Cloud réelle (Access ID/Secret) à la place du mock (produits, températures, vrais codes défauts DP).
- P1 : Application automatique des plages horaires (scheduler backend) sur les consignes.
- P1 : Confirmation avant l'arrêt total ; bannière d'alerte pour défauts critiques.
- P2 : Édition des créneaux ; historique/graphiques de température (recharts) ; alertes batterie/hors-ligne.
- P2 : Découpage server.py en modules (auth/installations/climate/invitations) ; migration lifespan FastAPI ; brute-force lockout login.

## Notes
- TOUTES LES DONNÉES SMARTLIFE/TUYA (appareils, températures, codes défauts) SONT SIMULÉES (mock).
