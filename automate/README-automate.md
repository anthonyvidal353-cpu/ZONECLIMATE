# ClimaZone — Mettre en route l'automate (Raspberry Pi 5)

Ce guide met en service l'automate qui régule votre climatisation gainable.
Deux étapes : **(1)** installer et tester l'app sur le Wi-Fi de la maison,
**(2)** plus tard, activer le point d'accès Wi-Fi « ZONING VALSON » pour isoler
les appareils Tuya (nécessite une clé USB Wi-Fi).

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
Sur le navigateur du Pi : **http://localhost:3000**
Connectez-vous avec le compte administrateur défini pendant l'installation.

> Depuis un téléphone/tablette du même réseau : utilisez `http://<IP_DU_PI>:3000`
> (l'IP du Pi s'obtient avec `hostname -I`). Pour un accès fluide depuis d'autres
> appareils, demandez-moi la variante « accès réseau ».

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
sudo bash ~/zoneclimate/automate/kiosk-setup.sh "http://localhost:3000/ecran/<ID_INSTALLATION>"
sudo reboot
```

`<ID_INSTALLATION>` est visible dans l'URL `/installations/<ID>` de l'app.
Détails et branchements écran : voir **README-ecran.md**.

---

## Étape 2 — Point d'accès Wi-Fi « ZONING VALSON »

> Vous avez la **clé USB Wi-Fi** : on active donc le double Wi-Fi.
> Principe : l'antenne **interne (wlan0)** diffuse « ZONING VALSON » pour les
> appareils Tuya ; la **clé USB (wlan1)** garde l'internet de la maison.

### a) Brancher la clé USB Wi-Fi
Branchez-la, puis vérifiez qu'elle apparaît :
```bash
nmcli device | grep wifi
```
Vous devez voir **deux** interfaces (ex. `wlan0` interne + `wlan1` clé USB).

### b) Mettre l'internet de la maison sur la CLÉ USB (wlan1)
```bash
sudo nmcli device wifi connect "NOM_DE_VOTRE_WIFI_MAISON" password "MOT_DE_PASSE_MAISON" ifname wlan1
```
(Vérifiez : `ping -c2 8.8.8.8` doit répondre.)

### c) Créer le point d'accès « ZONING VALSON » sur l'antenne interne (wlan0)
```bash
sudo bash ~/zoneclimate/automate/wifi-ap-setup.sh
```
Le script affiche les interfaces + qui porte l'internet, puis vous demande
l'interface du point d'accès (**wlan0**) et un mot de passe. Il crée le réseau
avec DHCP + partage internet automatiques.

### d) Appairer les appareils Tuya
Lors de l'appairage dans **SmartLife**, connectez vos appareils au réseau
**« ZONING VALSON »**. Ils resteront isolés sur l'automate tout en ayant internet
pour l'appairage initial.

> Si l'AP ne démarre pas sur `wlan0` (rare), relancez le script en choisissant
> `wlan1` pour l'AP et mettez l'internet maison sur `wlan0`.

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
