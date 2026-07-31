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
- ✅ [2026-06] Sécurité reprise d'air (Modbus) : gainable coupé si reprise ≥ 35°C en chaud (surchauffe) ou ≤ 8°C en froid (anti-gel) — System.safety_note + bandeau rouge dashboard. Actif seulement si modbus_enabled + reprise mesurée. Testé curl (38°C chaud→coupé) + UI + non-régression.
- ℹ️ [2026-06] Décision user : pour l'instant, gainable piloté UNIQUEMENT en filaire Modbus (Pi), pas via Tuya. Déjà supporté nativement (pilotage Tuya du gainable ignoré si aucun appareil Tuya gainable). Thermostats Tuya (zones/vannes) ajoutés plus tard.
- Tout VALIDÉ testing_agent iteration_22 (100% backend + frontend).
- ✅ [2026-07] Détection auto de l'adresse esclave Modbus ("Détecter") : POST /gainable/modbus/scan (balaie 1..32, dégradation gracieuse) + bouton UI dans GainableModbusDialog. VALIDÉ testing_agent iteration_25 (100% backend).
- ✅ [2026-07] Gainable relié à Tuya par l'utilisateur → choix user (1/c) : MODBUS = pilote principal, TUYA = INFO en lecture seule. apply_local_control : si modbus_enabled, la voie Tuya du gainable devient LECTURE seule (stocke gainable_tuya_dps/at, plus d'écriture Tuya vers le gainable). Nouveau GET /installations/{iid}/gainable/tuya/status (lit l'état DPS du gainable via LAN, dégradation gracieuse). UI : panneau "Infos gainable (Tuya) — lecture seule" (GainableTuyaInfo.jsx) sur l'onglet Zones, bouton "Lire" (interprète power/mode/consigne/ventilation via dps_map + DPS bruts). VALIDÉ testing_agent iteration_25 (100% backend). NON testé sur matériel réel (à valider sur le LAN de l'utilisateur sous Docker Windows).
- ✅ [2026-07] RÉGULATION AUTONOME + TEMPÉRATURE RÉELLE (pour l'automate branché A-B-GND + thermostats) — 3 correctifs :
  (A) Boucle backend AUTONOME `periodic_regulation()` (REG_INTERVAL_SEC=30, enregistrée au startup) : régule 24/7 chaque installation en control_mode='local', INDÉPENDAMMENT de tout navigateur ouvert (avant : le tick n'était déclenché que par le Dashboard/Mode écran côté frontend → régulation stoppée si aucun écran ouvert).
  (B) Lecture de la TEMPÉRATURE RÉELLE des thermostats Tuya en mode local : `_run_regulation(iid, real)` appelle `_read_real_temps` (lit le DP current_temp de chaque thermostat via LAN, /échelle) et injecte la vraie temp AVANT le calcul de demande ; en mode local la simulation d'évolution (étape 5) est désactivée. Mode démo/cloud : simulation conservée.
  (C) Mapping DPS thermostat : ajout des champs `current_temp` + `current_temp_scale` (LocalManager.jsx, éditeur Diagnostic DPS) pour identifier le DP de température mesurée sur le matériel.
  simulate_tick refactoré en endpoint fin délégant à `_run_regulation`. Dégradation gracieuse totale sans matériel. VALIDÉ testing_agent iteration_26 (100% backend, 10/10). NON testé sur matériel réel.
- ✅ [2026-07] JOURNAL DE RÉGULATION (7 jours glissants, réservé super_admin + moderator, filtrable par compte utilisateur/email) : collection `reg_logs` (index TTL 7 j + index owner_email/installation). Helper `log_reg_event` rattache chaque événement au compte propriétaire de l'installation. Événements journalisés : démarrage/purge/arrêt gainable, coupures sécurité, codes défauts, instantané périodique (5 min, throttlé en mémoire) avec temp réelle + demande par zone, changements mode/power/consigne/pilotage (avec l'utilisateur acteur), passages en/hors ligne des appareils LAN. Endpoints : GET /admin/reg-logs (filtres owner_email/installation_id/etype/limit) + GET /admin/reg-logs/accounts (comptes pour le filtre) — require_roles(super_admin, moderator). UI : onglet "Journal" (Home.jsx) → RegulationJournal.jsx (frise chronologique typée par couleur + sélecteur de compte + Actualiser). VALIDÉ testing_agent iteration_27 (100% backend, 24/24 : RBAC 403 client, génération d'événements, filtrage, tri desc, régression).

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

## Déploiement automate (Raspberry Pi 5) — [2026-07]
- Dépôt GitHub utilisateur : `github.com/anthonyvidal353-cpu/ZONECLIMATE` (branche main).
- `docker-compose.pi.yml` : réseau host + passage du port série RS485 au backend (`devices: ${RS485_DEVICE:-/dev/ttyUSB0}` + group_add dialout).
- `automate/install-pi.sh` : installateur tout-en-un (Docker + clone/pull + génération .env avec JWT_SECRET/TUYA_ENC_KEY aléatoires + détection auto RS485 /dev/ttyUSB*|ACM* + build & up). Clone dans ~/zoneclimate.
- `automate/wifi-ap-setup.sh` : point d'accès « ZONING VALSON » via nmcli (mode ap + ipv4 shared). ÉTAPE 2 — nécessite une 2ᵉ antenne (clé USB Wi-Fi) car le Pi 5 n'a qu'une puce Wi-Fi interne.
- `automate/README-automate.md` : guide pas à pas (Étape 1 Wi-Fi maison + RS485 + écran ; Étape 2 double Wi-Fi).
- `automate/kiosk-setup.sh` + `README-ecran.md` : mode borne écran tactile (déjà existant).
- Mise en route en 2 étapes : (1) Wi-Fi maison + Docker + app + RS485 + tests régulation ; (2) plus tard, AP « ZONING VALSON » avec clé USB Wi-Fi.
- EN ATTENTE : modèle/branchement de l'écran tactile du client (photo demandée).

## Déploiement automate v2 — [2026-07] (images cloud + accès réseau + AP)
- ⚠️ Le Raspberry NE COMPILE PLUS (OOM/gel constatés). Images pré-construites arm64 via GitHub Actions → GHCR, le Pi ne fait que `pull`.
  - `.github/workflows/build-pi-images.yml` : build+push arm64 backend+frontend vers ghcr.io/anthonyvidal353-cpu/zoneclimate-{backend,frontend}:latest. Frontend buildé avec `REACT_APP_BACKEND_URL=` (vide → API relative `/api`). Packages GHCR à passer en PUBLIC (1 fois).
  - `docker-compose.pi.yml` : fichier AUTONOME, réseau host, images GHCR (pull_policy always), passage RS485, + service `proxy` nginx.
  - Bug corrigé : `network_mode: host` + `networks` = incompatible (compose invalide) → fichier rendu autonome.
  - `frontend/Dockerfile` : `--platform=$BUILDPLATFORM` (build natif runner), `GENERATE_SOURCEMAP=false`, `NODE_OPTIONS=--max-old-space-size=2048`, `yarn install --network-timeout 600000`.
  - `frontend/src/lib/api.js` : `BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ""` → API relative si vide.
- Accès réseau : reverse proxy nginx (`automate/nginx-pi.conf`, port 80, host) → app + `/api` sur une seule adresse. Accès depuis n'importe quel appareil : `http://<IP_PI>` (téléphone/PC) ou `http://localhost` (Pi). Plus de `:3000`.
- Wi-Fi « ZONECLIMATE » + portail captif : `automate/wifi-ap-setup.sh` (nmcli AP mode + ipv4 shared, SSID ZONECLIMATE, sur la clé USB ; internet maison sur l'antenne interne, partagé pour Tuya). Portail captif = dnsmasq-shared redirige SEULEMENT les URL de détection vers 10.42.0.1 (Tuya garde internet) + nginx renvoie 302 sur ces chemins. Un seul réseau pour utilisateurs + Tuya.
- Accès distant (PHASE 2) : Cloudflare Tunnel — CHOIX RETENU par l'utilisateur (chaque client se connecte avec ses propres identifiants via une URL, sans app à installer). Service `cloudflared` ajouté à docker-compose.pi.yml (profil "remote", token via CLOUDFLARE_TUNNEL_TOKEN dans .env). Guide : `automate/README-acces-distant.md`. Un tunnel + sous-domaine par automate → localhost:80. Utilisateur doit prendre un nom de domaine.
- `install-pi.sh` : affiche l'IP du Pi en fin d'install ; démarre via `up -d` (pull, pas de build).

## Gestion Wi-Fi in-app — [2026-07]
- Objectif : installateur configure via l'AP « ZONECLIMATE » (sans IP) ; le client saisit le Wi-Fi maison DANS l'app → le Pi rejoint le réseau → accès depuis le réseau du client (et distant en phase 2 via Cloudflare).
- Backend : `wifi_manager.py` (nmcli via subprocess, dégradation gracieuse si nmcli absent). Endpoints `GET /api/system/wifi/status`, `GET /api/system/wifi/scan`, `POST /api/system/wifi/connect` (auth requise, tous rôles). Interface maison = env `HOME_WIFI_IFACE` (défaut wlan0).
- Backend image : `network-manager` installé dans le Dockerfile ; compose Pi monte `/var/run/dbus/system_bus_socket` + `DBUS_SYSTEM_BUS_ADDRESS` pour piloter le NetworkManager de l'hôte.
- Frontend : `WifiManager.jsx` (dialog scan/connexion/statut) ouvert depuis le menu utilisateur (AppShell) → accessible à tous les rôles connectés.
- VALIDÉ en cloud : endpoints dégradent proprement (nmcli absent), auth 401, UI rendue. NON testé sur matériel réel (nécessite le Raspberry).


## Correctif OTA + AP Wi-Fi hors-ligne — [2026-06]
- ✅ Bug OTA (P0) corrigé : après install d'une MAJ, l'UI restait sur « mise à jour disponible » et la version ne changeait pas. Cause : `git pull` dans le conteneur updater échoue si l'arborescence /repo a la moindre modif locale → HEAD n'avance jamais → comparaison HEAD vs @{u} toujours "en retard". Correctif (`server.py` apply_update, POST /api/system/update) : `set -e; git fetch --all --prune; git reset --hard @{u}` (au lieu de `git pull`) avant `docker compose pull` + `up -d` → force le dépôt à rejoindre EXACTEMENT la version distante quel que soit l'état local. Logique git validée par simulation shell (dépôt sale v1 → v2, update_available→false). VALIDÉ testing_agent iteration_28 (13/13 backend, 100% : structure /system/update-info, RBAC super_admin+moderator / 403 autres, POST /system/update super_admin only, dégradation 502 gracieuse en cloud). NON exécutable en cloud (docker/git absents) — à confirmer sur le Pi.
- ✅ AP Wi-Fi « ZONECLIMATE » hors-ligne (choix user C : clé USB Wi-Fi, accès SANS Internet) : `wifi-ap-setup.sh` ajusté (`connection.autoconnect yes` + `autoconnect-priority 10` → l'AP se relance au boot ; mode `ipv4.method shared` fournit DHCP+DNS LOCAUX même box éteinte → zoning pilotable sur http://10.42.0.1 sans Internet). README-automate.md Étape 2 clarifiée : Internet devient OPTIONNEL (seulement utile pour l'appairage cloud Tuya), accès local garanti. SSID unifié « ZONECLIMATE » (ancienne mention « ZONING VALSON » corrigée). NON testé matériel (script Pi).
- ✅ Indicateur « Dernière mise à jour appliquée le… » sous la bannière OTA : POST /system/update enregistre `last_update_at` dans db.app_meta (_id:'ota'), GET /system/update-info le renvoie, UpdateBanner.jsx l'affiche (data-testid update-last-applied, format fr-FR). Vérifié en cloud (endpoint + rendu UI screenshot).
- ✅ Portail captif fiabilisé (nginx-pi.conf) : les URL de détection de connectivité renvoient désormais une petite page HTML 200 (meta-refresh + JS `location.replace` + bouton « Se connecter ») au lieu d'un 302 cross-domaine → ouverture plus fiable de la page de connexion dans les mini-navigateurs captifs (iOS/Android/Windows/Firefox/Ubuntu/GNOME). Domaines de détection ajoutés au dnsmasq-shared (detectportal.firefox.com, connectivity-check.ubuntu.com, nmcheck.gnome.org). NON testé matériel (nécessite l'AP sur le Pi).

## Panneau tactile ESP32-S3 — Phase 1 backend — [2026-06]
- Objectif : écran tactile Waveshare ESP32-S3-Touch-LCD-4.3 (800×480, GT911, RS485+CAN, PAS de caméra) installé DE SÉRIE sur l'automate pour faire les associations de zones SANS smartphone. Choix user : jeton FIXE (option b) → l'écran marche dès la mise en service.
- ✅ Auth panneau : dépendance `require_panel_token` (en-tête `X-Panel-Token`, `hmac.compare_digest`, env `PANEL_TOKEN` défaut `ZONECLIMATE-PANEL-2026`). N'interfère pas avec l'auth JWT existante.
- ✅ API panneau (sans login) : GET /api/panel/installations ; GET /api/panel/installations/{iid}/zones ; GET /api/panel/installations/{iid}/catalog/unassigned ; POST /api/panel/installations/{iid}/associate {code, zone_id?|new_zone_name?, new_zone_icon?}.
- ✅ Refactor : logique d'association extraite dans `_associate_device_by_code`, partagée par associate-qr (JWT web) et panel_associate (jeton). Aucune régression.
- ✅ PANEL_TOKEN ajouté à backend/.env + docker-compose.pi.yml (env). VALIDÉ testing_agent iteration_29 (13/13, 100% backend : auth 401, 3 branches d'association, 404/400, régression associate-qr).
- ⏭️ Phase 2 (À FAIRE) : firmware LVGL ESP32-S3 (projet PlatformIO/Arduino, pilote RGB + GT911) consommant ces API — NON testable en cloud, à flasher/valider sur la carte.

## Panneau tactile ESP32-S3 — Phase 2 firmware — [2026-06]
- ✅ Projet firmware complet créé : `/app/firmware/esp32s3-panel/` (PlatformIO, cible Waveshare ESP32-S3-Touch-LCD-4.3, 800×480, GT911, CH422G).
  - `platformio.ini` : espressif32@6.5.0 (core Arduino 2.x), LVGL 8.4, Arduino_GFX, bb_captouch, ArduinoJson, ESP32_IO_Expander ; PSRAM OPI, flash 8MB.
  - `src/board.cpp` : bring-up écran RGB (brochage Waveshare) + tactile GT911 (bb_captouch, SDA8/SCL9/INT4) + reset & rétroéclairage via CH422G + glue LVGL.
  - `src/api.cpp` : client HTTP `/api/panel/*` avec en-tête `X-Panel-Token`.
  - `src/ui.cpp` : écrans LVGL — choix du zoning (si plusieurs) + appairage (liste appareils non associés avec statut en ligne ✓, liste zones, « nouvelle zone », saisie manuelle du code au clavier tactile, bouton ASSOCIER).
  - `src/config.h` : réglages installateur (WIFI_SSID/PASSWORD, BACKEND_URL, PANEL_TOKEN).
  - `src/lv_conf.h`, `src/main.cpp`, `README.md` (build/flash + repli init Waveshare si écran noir).
- Amélioration livrée : statut « en ligne ✓ / ⚠ » affiché par appareil dans la liste avant association (issu du champ catalog.online).
- ⚠️ NON compilé/flashé par l'assistant (embarqué non exécutable en cloud). À valider sur la carte. La partie board.cpp (CH422G/pins) peut nécessiter l'init du démo Waveshare selon la révision ; api.cpp + ui.cpp restent réutilisables tels quels.

## Accès hors-ligne + UX mobile + OTA progression — [2026-06]
- ✅ Frontend rendu 100% hors-ligne : `public/index.html` — polices Google/Fontshare passées en NON bloquant (media=print + onload) et script `emergent-main.js` en `defer`. Cause du bug « page blanche sur 10.42.0.1 sans Internet » (les ressources externes bloquaient le rendu). Confirmé par l'utilisateur : l'app s'affiche maintenant hors-ligne via l'AP.
- ✅ Portail captif (nginx-pi.conf) : page 200 STATIQUE (logo + bouton « Ouvrir ClimaZone » + instruction 10.42.0.1) au lieu de rediriger vers la SPA (que la mini-fenêtre captive ne sait pas exécuter → blanc). Sans auto-redirect JS.
- ✅ OTA : `apply_update` ajoute `docker compose restart proxy` (recharge le nginx/portail captif à chaque mise à jour via le bouton, sans terminal).
- ✅ Menu admin responsive (Home.jsx) : `flex-wrap` + largeur pleine + paddings réduits sur mobile → les 6 onglets passent sur 2 lignes (fini le scroll horizontal).
- ✅ UpdateBanner.jsx : barre de progression réelle lors de « Installer la mise à jour ». Interroge /system/update-info en boucle (téléchargement → redémarrage détecté par échec de requête → terminé quand backend revient avec nouvelle version/update_available=false). 100% = « vous pouvez tester ». Note « ne testez pas avant 100% ». Timeout 5 min.
- Rappel déploiement Pi : le correctif frontend nécessite rebuild GitHub Actions (~15 min) puis pull. Le bouton OTA in-app fait tout (git reset --hard + pull + up + restart proxy) SI le build Actions est terminé. La barre de progression n'apparaîtra qu'à partir de la MAJ SUIVANTE (elle fait partie de cette MAJ).
- ⚠️ Auto-ouverture du portail captif : dépend du téléphone (certaines surcouches Android la bloquent). Repli fiable : navigateur → 10.42.0.1. Astuce : « oublier le réseau » puis reconnecter force la re-détection.

## OTA fiabilisé + AP stable + carte simplifiée — [2026-06]
- ✅ BUG in-app OTA (bloque à 92%, MAJ non appliquée) : cause = le conteneur updater voyait le dépôt sur `/repo` alors que `docker compose` (démon hôte) résout les volumes relatifs (./automate/...) sur le VRAI chemin hôte → montages cassés → MAJ échoue en silence. Fix : `HOST_REPO_DIR=${PWD}` ajouté dans docker-compose.pi.yml (backend env) ; apply_update monte le dépôt au MÊME chemin hôte (host_dir:host_dir) et exécute compose depuis ce chemin. À valider sur Pi (non exécutable en cloud, 502 gracieux OK).
- ✅ Commande de MAJ FIABLE : `automate/update.sh` (une seule commande `sudo bash automate/update.sh` : git reset --hard @{u}|origin/main → compose pull → up -d → restart proxy, avec progression visible). Méthode recommandée vs bouton.
- ✅ UpdateBanner : barre de progression PERSISTE au rechargement (localStorage climazone_ota, reprise <6min) et ne bloque plus à 92% (fin détectée dès update_available=false/version changée après 20s ; sinon message « probablement terminée, rechargez »). Cap 94%.
- ✅ wifi-ap-setup.sh robuste : liaison AP par ADRESSE MAC (802-11-wireless.mac-address + interface-name vide) → stable malgré inversion wlan0/wlan1 au reboot ; option DHCP 114 RETIRÉE (cassait dnsmasq/l'AP). Redirection captive DNS conservée (best-effort).
- Décisions produit : abandon écran ESP32-S3 (trop de travail) → tablette Wi-Fi sur ZONECLIMATE + navigateur 10.42.0.1. Abandon portail captif auto-open (peu fiable selon tel) et carte QR/onboarding (user veut rester simple). Accès offline OK confirmé.
- ⚠️ AP : sur ce Pi, wlan0=interne (Wi-Fi maison), wlan1=clé USB (AP ZONECLIMATE). Country Wi-Fi FR requis (raspi-config do_wifi_country FR) sinon l'AP refuse les connexions.

## Modbus VALSON/TCL (registres corrigés) + Wi-Fi + OTA hors-ligne — [2026-07]
- ✅ Registre reprise d'air CORRIGÉ (modbus_gainable.py). L'ancien 0xA647 était FAUX = registre de DÉFAUTS (bit14 = "panne sonde reprise"), converti en température il donnait 0→-100°C → sécurité anti-gel déclenchée à tort → gainable coupé. D'après le PDF officiel (Modbus Protocol V1.0), l'unité intérieure gainable n'expose qu'UNE sonde d'air exploitable : 0x0318 (ambiance intérieure = air de reprise sur un gainable). REG_RETURN_AIR = REG_ROOM_TEMP = 0x0318. Ajouté REG_COIL=0x031A (tube central/batterie, info). Outdoor 0xA616 OK.
- ✅ Conversion sécurisée _to_celsius_safe : valeur brute 0 (=-100°C, "donnée invalide"/capteur absent) ou hors plage [-50..100°C] → None. La sécurité anti-gel/surchauffe ne se déclenche plus sur lecture invalide (garde `ret is not None`).
- Params comm confirmés par doc : 9600 bps, sans parité, 8 data, 1 stop, FC03 lecture / FC06 écriture. Modes 1=froid 2=déshu 4=chaud 5=auto. Ventil 1=auto 2=bas 4=moyen 6=haut. Consigne ×10 (160-310). Esclave 1-247 (DIP BM2 + rotacteur BM3).
- ⚠️ EN ATTENTE VALIDATION USER : re-test bouton "Tester" sur Pi câblé → reprise d'air doit afficher une valeur réelle (~22-25°C) et le gainable démarrer. Question posée : afficher la temp. batterie 0x031A à la place du doublon "Ambiance" + baser l'anti-gel dessus ?
- ✅ Wi-Fi (WifiManager.jsx) : champ mot de passe TOUJOURS visible (avant : masqué si `secured` faux ; le parsing SECURITY de nmcli échouait sur STARLINK → pas de saisie possible). Bouton activé en permanence + Enter pour valider + note "laissez vide si réseau ouvert".
- ✅ OTA update-info (server.py) : détecte l'échec de `git fetch` (returncode != 0 = pas d'Internet) → renvoie check_failed=true + detail clair au lieu de comparer l'état local et annoncer faussement "à jour". UpdateBanner.jsx : nouvel état amber "Vérification impossible" (icône WarningCircle) + toast.error. Vérifié en cloud (check_failed:true renvoyé, bandeau amber affiché).

## Fiabilité terrain / récupération sans terminal — [2026-07]
- ✅ docker-compose.pi.yml : `pull_policy: always` → `missing` (backend+frontend). Cause d'un "planté après reboot hors-ligne" : tout `docker compose up` tentait de re-puller depuis ghcr.io → échec sans Internet. Désormais le boot/up utilise les images LOCALES déjà téléchargées. Les MAJ continuent de puller explicitement (update.sh ligne 27 `docker compose pull`).
- ✅ install-pi.sh : ajout d'un service systemd `zoneclimate.service` (oneshot, RemainAfterExit, WorkingDirectory=$HOME/zoneclimate, ExecStart=docker compose up -d, enable multi-user). Auto-démarrage + auto-réparation au boot, 100% hors-ligne (recrée les conteneurs manquants). Combiné à restart:unless-stopped → l'app remonte toujours seule après une coupure de courant.
- ⚠️ Ces correctifs sont dans le CODE, pas encore sur le Pi de test (ancienne image). Doivent être buildés (Save to GitHub → GitHub Actions ~15 min) puis appliqués UNE fois au Pi là où il y a Internet/Ethernet (atelier).
- Stratégie de récupération terrain validée avec l'utilisateur : préparer/mettre à jour chaque Pi à l'atelier (Internet facile), puis pose chez le client SANS Internet. Récup en cas de blocage = débrancher/rebrancher (self-heal) ; ultime filet = carte SD de secours pré-configurée à échanger.
- Pi de test ACTUEL bloqué (login "une erreur est survenue" persistant après reboot) : non diagnostiquable à distance (pas d'accès terminal/logs). Cause probable : ancienne image + tentatives Wi-Fi répétées ayant laissé un conteneur/état dégradé. Résolution recommandée : brancher le Pi une fois là où il y a Ethernet et lancer la MAJ (récupère l'image corrigée + ces protections).
