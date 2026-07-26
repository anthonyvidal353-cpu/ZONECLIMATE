# ClimaZone — Mettre en route l'automate (Raspberry Pi 5)

Ce guide met en service l'automate qui régule votre climatisation gainable.
Deux étapes : **(1)** installer et tester l'app sur le Wi-Fi de la maison,
**(2)** plus tard, activer le point d'accès Wi-Fi « ZONECLIMATE » pour piloter le
zoning **même sans Internet** (accès local via la clé USB Wi-Fi).

---

## 🔌 Matériel
- Raspberry Pi 5 (Raspberry Pi OS Bookworm 64-bit, déjà installé).
- Convertisseur **USB ↔ RS485** (branché en USB, relié au gainable en **A-B-GND**).
- (Étape 2) une **clé USB Wi-Fi** (2ᵉ antenne) pour le mode double Wi-Fi.
- (Option) écran tactile Raspberry Pi pour le mode borne.

---

## Étape 0 — Construire les images dans le cloud (UNE SEULE FOIS)

> L'app n'est **jamais compilée sur le Raspberry** (trop lent). Elle est construite
> gratuitement par **GitHub Actions**, puis le Pi la télécharge toute prête.

1. Faites **« Save to GitHub »** : ça déclenche la construction automatique
   (onglet **Actions** de votre dépôt → attendez le ✅ vert, ~15 min).
2. Rendez les 2 images **publiques** (pour que le Pi les télécharge sans mot de passe) :
   - Sur github.com → votre profil → onglet **Packages** →
     `zoneclimate-backend` → **Package settings** → **Change visibility** → **Public**.
   - Idem pour `zoneclimate-frontend`.
   *(À faire une seule fois. Ensuite chaque mise à jour est automatique.)*

---

## Étape 1 — Installation de l'application

### 1. Ouvrir un terminal sur le Pi
Bureau → icône **Terminal** (ou `Ctrl+Alt+T`).

### 2. Lancer l'installation en une commande

```bash
curl -fsSL https://raw.githubusercontent.com/anthonyvidal353-cpu/ZONECLIMATE/main/automate/install-pi.sh -o install-pi.sh
bash install-pi.sh https://github.com/anthonyvidal353-cpu/ZONECLIMATE.git
```

> Si votre branche principale s'appelle `master` (et non `main`), remplacez
> `main` par `master` dans la 1ʳᵉ ligne.
> Autre option : clonez d'abord le dépôt, puis lancez
> `bash ~/zoneclimate/automate/install-pi.sh`.

Le script :
1. installe **Docker** ;
2. récupère le code ;
3. détecte le **convertisseur RS485** (branchez-le AVANT) ;
4. crée la configuration (`.env`) — il vous demande l'**email** et le
   **mot de passe administrateur** ;
5. **télécharge** les images pré-construites et démarre l'app (aucune compilation).
5. construit et démarre l'application.

### 3. Ouvrir l'application
- Sur le Pi (s'il a un écran) : **http://localhost**
- Depuis un **téléphone / PC / tablette** du même réseau : **http://<IP_DU_PI>**
  *(l'IP est affichée à la fin de l'installation, ou avec la commande `hostname -I`.)*

Connectez-vous avec le compte administrateur défini pendant l'installation.

> 🖥️/📱 **Vous choisissez** : l'automate marche **sans écran** (piloté au téléphone)
> **ET** vous pouvez **brancher un écran à tout moment** — c'est la même adresse.

### 4. Brancher et tester le gainable (RS485)
- Câblage : **A → A**, **B → B**, **GND → GND** entre le convertisseur et le gainable.
- Dans l'app : onglet **Zones** → bouton **« Gainable Modbus »** →
  **Activer** → **Détecter** l'adresse → **Tester** (les températures ambiance /
  reprise / extérieur doivent s'afficher).

### 5. Mettre l'automate en régulation
- Basculez le pilotage sur **« Pilotage local »** (indispensable : active la
  régulation autonome + la lecture des vraies températures).
- La régulation tourne alors **en continu**, même sans écran allumé.

---

## Étape 1 bis — Écran tactile (mode borne, optionnel)
> Non nécessaire au fonctionnement : l'automate régule tout seul en tâche de fond.
> Utile seulement si vous ajoutez un écran tactile plus tard.

```bash
sudo bash ~/zoneclimate/automate/kiosk-setup.sh "http://localhost/ecran/<ID_INSTALLATION>"
sudo reboot
```

`<ID_INSTALLATION>` est visible dans l'URL `/installations/<ID>` de l'app.
Détails et branchements écran : voir **README-ecran.md**.

---

## Étape 2 — Réseau Wi-Fi « ZONECLIMATE » (avec page de connexion automatique)

> L'automate diffuse son propre Wi-Fi **« ZONECLIMATE »** (via la clé USB).
> En s'y connectant, le téléphone **ouvre automatiquement la page de connexion**.
> ✅ **Fonctionne SANS Internet** : le zoning reste 100 % pilotable même box éteinte.
> Si la box est présente, son internet est **partagé** sur « ZONECLIMATE » pour que
> les appareils Tuya puissent s'appairer. Un seul réseau pour tout : vous + le Tuya.

### a) Brancher la clé USB Wi-Fi
```bash
nmcli device | grep wifi
```
Vous devez voir **deux** interfaces (interne + clé USB).

### b) (Optionnel) internet maison
- Pour un usage **100 % local sans internet** : rien à faire, passez à l'étape c).
- Si vous voulez que les appareils Tuya s'appairent au cloud pendant la mise en
  service, laissez le Wi-Fi maison connecté (antenne interne) : `ping -c2 8.8.8.8`.

### c) Créer le réseau « ZONECLIMATE »
```bash
sudo bash ~/zoneclimate/automate/wifi-ap-setup.sh
```
Le script détecte tout seul l'antenne à utiliser (la clé USB), vous demande un
**mot de passe** pour « ZONECLIMATE », et installe le portail captif.
Le réseau se **relance automatiquement à chaque démarrage** du Pi.

### d) Utilisation (sans internet)
- Sur votre téléphone : connectez-vous au Wi-Fi **« ZONECLIMATE »** → la page de
  connexion ClimaZone s'ouvre automatiquement. *(Sinon : `http://10.42.0.1`.)*
- Vous pilotez tout le zoning **sans aucune connexion internet**.
- Si la box est présente, appairez aussi vos appareils Tuya (SmartLife) sur ce
  même réseau **« ZONECLIMATE »** (ils gardent internet pour l'appairage).

---

## 🔄 Mettre à jour l'automate plus tard
Après un « Save to GitHub » (les images se reconstruisent toutes seules), sur le Pi :
```bash
cd ~/zoneclimate && git pull && sudo docker compose -f docker-compose.pi.yml pull && sudo docker compose -f docker-compose.pi.yml up -d
```

## 🧯 Dépannage rapide
- **Le gainable ne répond pas** : convertisseur branché AVANT le démarrage ?
  Vérifiez le port : `ls /dev/ttyUSB*` (ou `/dev/ttyACM*`). Relancez `install-pi.sh`
  pour re-détecter, ou éditez `RS485_DEVICE` dans `~/zoneclimate/.env`.
- **L'app ne s'ouvre pas** : `sudo docker compose -f docker-compose.pi.yml ps`
  (les 3 services doivent être « running »).
- **Voir les logs** : `sudo docker logs zoneclimate-backend --tail 50`
