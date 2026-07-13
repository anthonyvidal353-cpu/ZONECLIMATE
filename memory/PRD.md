# ClimaZone — PRD

## Problème / Objectif
Application Web/Mobile pour centraliser le pilotage d'une climatisation gainable et de thermostats sans fil (Wi-Fi) Tuya/SmartLife. Gestion des zones, vue Plénum visuelle, génération de QR codes pour l'appairage installateur, algorithme de régulation backend modulant le gainable selon la demande des zones. Cible : hébergement local sur un boîtier "automate" (Raspberry Pi) chez le client, isolé du Cloud Tuya (contrôle LAN via `tinytuya`).

⚠️ Ne JAMAIS utiliser le mot "Raspberry" dans l'UI — utiliser "automate".
⚠️ Répondre en FRANÇAIS.
⚠️ L'utilisateur exécute l'app localement sous Docker (Windows) et met à jour via `maj-zoneclimate.bat` (git pull + rebuild). Rappeler "Save to GitHub" après chaque jalon.

## Stack
FastAPI + React (TailwindCSS/Shadcn) + MongoDB (Motor). `tinytuya` pour contrôle LAN. Docker / docker-compose. Auth JWT (RBAC).

## Comptes de test
Voir /app/memory/test_credentials.md. Admin : admin@climazone.fr / Admin1234! (token = champ `access_token`).

## Fait
- Algo de régulation (consigne proportionnelle, sync registres, purge 30s) — calcule uniquement (envoi physique MOCKÉ)
- Vue Plénum (PlenumView.jsx)
- Extraction/chiffrement des clés locales Tuya (tuya_local.py)
- Docker Compose + updater Windows (maj-zoneclimate.bat)
- Toggle inclure/ignorer appareils personnels vs HVAC
- Vue Installateur/Client restreinte au scan QR
- Bannière OTA (masquée sous Windows via .env)
- Dashboard responsive mobile ; "Raspberry" → "automate"
- ✅ [2026-06] Correctif Catalogue QR Code : seuls les appareils inclus (local_devices.included=True) ont un QR code — VALIDÉ testing_agent iteration_20 (100% backend)
- ✅ [2026-06] Impression individuelle par QR (bouton "Imprimer ce QR" par carte, catalog-print-one-{code}) + impression groupée conservée
- ✅ [2026-06] Nombre de vannes par thermostat (1-4) : réglable à la création (CreateInstallationDialog) ET modifiable ensuite (ZoneCard + MasterZoneCard). Champ Zone.valves borné 1-4. Plénum dessine N vannes + badge ×N (ValveCluster). Algo de régulation pondéré : fan_level = max(demande thermique, débit lié au nb de vannes ouvertes) — VALIDÉ testing_agent iteration_21 (100% backend + frontend)
- ✅ [2026-06] Plénum : indicateur temps réel "X/Y vannes ouvertes · Z%" (charge du gainable) dans l'en-tête.
- ✅ [2026-06] Suppression d'appareil avec confirmation irréversible (AlertDialog) — DELETE /api/installations/{iid}/devices/{device_id} (détache la zone associée). Testé curl + smoke UI.
- ✅ [2026-06] Contrôle Tuya local RÉEL : algo tick branché sur tinytuya (apply_local_control, tâche de fond) actif en control_mode='local' ; envoie power/consigne/mode/ventilation au gainable + consigne/power aux thermostats selon dps_map. Outil Diagnostic DPS (lecture état brut + éditeur de correspondance) : PUT /admin/tuya/local/devices/{id}/dps-map. Toggle Cloud/Local sur le dashboard. NB : pilotage physique testable uniquement en déploiement local (matériel sur le LAN).
- ✅ [2026-06] Statut LAN en ligne/hors-ligne : poller backend 30s (periodic_local_status), POST /admin/tuya/local/refresh-status, badges + rafraîchissement auto 30s + bouton Rafraîchir dans LocalManager.
- ✅ [2026-06] Mode écran / kiosque tactile 800×480 (route /ecran/{iid}, KioskDisplay.jsx) pour l'écran de l'automate ; app toujours pilotable PC/tablette/mobile. Bouton 'Mode écran' sur le dashboard.
- ✅ [2026-06] Mode écran adaptatif PORTRAIT 480×800 (en-tête flex-wrap + grille auto-fill) + bouton "Scanner" (caméra) réutilisant QrAssociateDialog pour appairer un appareil depuis l'écran tactile. Smoke test OK (bouton + lecteur caméra + zones).
- ✅ [2026-06] Borne tactile : bouton plein écran (⤢) + anti-veille Wake Lock dans le kiosque. Script de démarrage auto du Raspberry Pi (/app/automate/kiosk-setup.sh + README-ecran.md) : Chromium kiosque plein écran au boot, auto-login bureau, anti-veille xset, session persistante (7 j). NB : carte ESP32-P4 NON compatible (microcontrôleur sans navigateur) — utiliser un écran compatible Raspberry Pi.
- ✅ [2026-06] Ajout manuel d'appareil depuis la borne (écran SANS caméra) : bouton "Ajouter" ouvre QrAssociateDialog en mode saisie manuelle (prop startManual) → champ de code sous le QR + choix de zone → association. Smoke test OK (CZ-TEST1234 → étape zone).
- ✅ [2026-06] Suppression de ZONE (onglet Zones) : bouton corbeille sur les zones non-maître + confirmation irréversible. DELETE /api/installations/{iid}/zones/{zone_id} : refuse la zone maître (400), supprime la zone + son thermostat associé + ses créneaux de planning. Corrige le pb « zone orpheline persistante après suppression du thermostat » (zone ≠ appareil). Testé curl (master 400, orpheline supprimée) + smoke UI.
- ✅ [2026-06] Vannes modulantes (degré d'ouverture 0–100 %) — MODÈLE + ALGO préparés (matériel à brancher plus tard) : Zone.damper_opening (0–100) + Zone.proportional. Algo tick calcule l'ouverture proportionnelle à la demande (_opening_for_demand : demande 1°→50 %, ≥2°→100 %, mini 30 %) ; les vannes non modulantes restent tout-ou-rien (0/100). Pilotage local prêt (dps_map thermostat : damper position 0–100 % ou damper_switch tout-ou-rien). UI : toggle « Vanne modulante » + affichage ouverture % par zone ; Plénum affiche « OUVERT N% ». Testé curl (50 %/100 %) + smoke UI. Choix user : Tuya Wi-Fi, vannes tout-ou-rien probables, brancher plus tard.
- ✅ [2026-06] Sécurisation JWT_SECRET : validation fail-fast au démarrage (server.py) → message clair en français si JWT_SECRET vide/<16 car. (au lieu de `InvalidKeyError: HMAC key must not be empty` + 401). Corrige le blocage du déploiement Docker local de l'utilisateur (secret vide dans le .env racine). Auth régression VALIDÉE testing_agent iteration_23 (100% backend).

## Piste matériel en cours (P1)
- ✅ [2026-06] Pilotage du GAINABLE en Modbus RTU (RS485) via l'automate — CODE PRÊT (validable sur matériel) : module `modbus_gainable.py` (pymodbus 3.14, 9600/N/8/1, FC03/06/10). Registres : 0x0201 marche, 0x0202 mode (1=froid,4=chaud,5=auto), 0x0203 consigne ×0,1°C (160-310), 0x0204 ventilation (2/4/6/auto=1). Capteurs lus : 0x0318 ambiance, 0xA647 reprise d'air, 0xA616 extérieur (formule (val-1000)/10). System.modbus_enabled/port/slave + relevés gainable_room/return/outdoor_temp. Endpoints : POST /gainable/modbus/test (renvoie les 3 temps, dégradation gracieuse). Branché dans apply_local_control (écriture commandes + lecture capteurs chaque tick). UI : GainableModbusDialog (activer/port/slave/test) + bandeau relevés (ambiance/reprise/extérieur) sur l'onglet Zones. Architecture : thermostats zones+vannes = Tuya Wi-Fi, gainable = Modbus, mode imposé par thermostat maître. VALIDÉ testing_agent iteration_24 (100% backend) + UI vérifiée. NON testé sur matériel réel.
- Tout VALIDÉ testing_agent iteration_22 (100% backend + frontend).

## Backlog priorisé
### P1
- Contrôle Tuya local RÉEL : brancher l'algo `tick` sur `tinytuya` pour envoyer les commandes physiques (gainable + thermostats) via LAN. Actuellement MOCKÉ (calcul DB seulement).
- Statut en ligne/hors-ligne temps réel des appareils LAN via `tinytuya`.
- UI de provisionnement central : mapper appareils du pool local vers une installation client.
### P2
- Architecture déploiement "automate" (double Wi-Fi : AP "ZONING VALSON" pour Tuya + dongle USB Wi-Fi internet client).
- Refactoring server.py (>1600 lignes) → routers (/routes/tuya.py, auth.py, installations.py).

## Bug ouvert connu (hors périmètre)
- POST /api/installations/{iid}/discover renvoie 502 quand un projet bidon échoue et le vrai projet a 0 device (iteration 18).

## Architecture fichiers
backend/{tuya.py (cloud), tuya_local.py (LAN), server.py (~1695 lignes)}, frontend/src/{components,pages,lib}, docker-compose.yml, docker-compose.pi.yml, maj-zoneclimate.bat, VERSION (1.0.0).
