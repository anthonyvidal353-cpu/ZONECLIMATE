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
- 2026-07-09 : Rebranding "ZoneClimate", masquage Tuya/SmartLife (réfs CZ- + QR codes), thème clair + accents violet (#7C3AED), confirmation suppression installation, correctifs contraste.
- 2026-07-10 : Démarrage NON DESTRUCTIF + sauvegarde/restauration. Sauvegarde JSON auto (périodique 45s + au démarrage + à l'arrêt) dans /app/backend/data/backup.json ; restauration auto si DB vide au démarrage. Onglet Admin « Sauvegarde » (télécharger / sauvegarder maintenant / restaurer un fichier). Endpoints /api/admin/backup, /api/admin/backup/save, /api/admin/restore (super_admin). Tests backend 16/16 (iteration_11).
- 2026-07-10 : BUG FIX B — la découverte d'appareils (appairage simulé) génère désormais le nombre EXACT d'appareils choisi par l'utilisateur (param count 1..10 + category thermostat/gainable) au lieu d'un aléatoire 1-3. UI : sélecteur type + nombre dans PairingPanel.
- 2026-07-10 : Correctif création — les zones sans nom sont auto-nommées « Zone N » (dédoublonnées) pour ne perdre aucun thermostat appairé. Tests 100% (iteration_12).
- 2026-07-10 : P2 (1/2/3) — Historique de température par zone (recharts, données simulées, plages 24/48/72h, endpoint GET /installations/{iid}/history) ; bannière d'alertes batterie faible (<=20%) / hors-ligne ; modèles de logement (Studio/T2/T3/Maison) dans l'assistant de création. Tests backend 10/10 + frontend OK (iteration_12).
- 2026-07-10 : Intégration API Tuya (Super Admin › onglet « API Tuya »). Gestion multi-projets Tuya (rotation, renouvellement conseillé +6 mois), 1 projet actif à la fois. Identifiants CHIFFRÉS au repos (Fernet, clé TUYA_ENC_KEY dans .env), secret jamais renvoyé au frontend (access_id masqué). Client Tuya OpenAPI signé HMAC-SHA256 (/app/backend/tuya.py). Endpoints /api/admin/tuya/{regions,projects,...,activate,test}. Bouton « Tester la connexion » réel. Collection tuya_projects incluse dans la sauvegarde. Tests 10/10 (iteration_13). NB: le test réel renvoie l'erreur Tuya 1114 tant que l'IP du serveur n'est pas ajoutée à la whitelist du projet Tuya.
- 2026-07-10 : Découverte RÉELLE des appareils (POST /installations/{iid}/discover?source=tuya) via le projet Tuya actif, en plus du mode simulé (source=sim). Pagination Tuya (20/page), dédoublonnage par tuya_id, mapping catégorie (gainable/thermostat). PairingPanel : sélecteur Réel/Simulation. tuya_id/product_id jamais exposés (fuite tuya_id dans /associate corrigée). Tests 8/8 (iteration_14). IMPORTANT : la connexion Tuya fonctionne (IP whitelistée), mais device_count=0 → l'utilisateur doit LIER son compte SmartLife au projet cloud (Cloud > Devices > Link App Account) pour que les appareils apparaissent.
- 2026-07-10 : Création d'installation SANS appareils fictifs (plus de faux code aléatoire) — la création définit uniquement les zones ; association réelle ensuite. Repli auto-nommage serveur. Tests 100% (iteration_15).
- 2026-07-10 : Multi-projets Tuya SIMULTANÉS (onglet renommé « Paramètres »). La découverte (catalogue + installation source=tuya) agrège désormais TOUS les projets configurés (capacités cumulées, contourne la limite ~10 appareils/projet de l'édition d'essai). Tolérance aux projets en échec : /admin/catalog/discover renvoie {items, errors} ; discover installation renvoie 200 si au moins un projet répond (correctif compteur succeeded). Catalogue affiche le nom du projet par appareil. Tests backend 8/8 + frontend 100% (iteration_18, bug 502 corrigé et auto-vérifié).
NB business : quotas Tuya = PAR PROJET (essai : 50 visibles / 10 pilotables / 2 comptes liés, usage commercial interdit ; ~1 maison de 6 appareils). Déploiement commercial => édition payante Flagship/Corporate requise.

## Comptes de démo
Voir /app/memory/test_credentials.md (admin/moderateur/installateur/client/invite).

## Backlog / prochaines étapes
- P1 : Brancher l'API Tuya Cloud réelle (Access ID/Secret) à la place du mock (produits, températures, vrais codes défauts DP).
- P1 : Application automatique des plages horaires (scheduler backend) sur les consignes.
- P2 : Scanner QR code caméra pour l'installateur (item 4 du lot P2, reporté à la demande de l'utilisateur).
- P2 : Édition des créneaux ; alertes batterie/hors-ligne (fait) ; historique (fait).
- P2 : Découpage server.py en modules (auth/installations/climate/invitations/backup) ; migration lifespan FastAPI ; brute-force lockout login.
- P3 (tech debt, remonté par testing agent) : restore_backup sans transaction (risque de wipe partiel si crash en cours) — envisager transaction Mongo ou DB fantôme + swap.

## Notes
- TOUTES LES DONNÉES SMARTLIFE/TUYA (appareils, températures, codes défauts) SONT SIMULÉES (mock).
