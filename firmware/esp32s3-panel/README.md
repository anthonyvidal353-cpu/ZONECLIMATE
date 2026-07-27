# ClimaZone — Panneau tactile d'appairage (ESP32-S3)

Firmware pour un **écran tactile Waveshare ESP32-S3-Touch-LCD-4.3** (4,3", 800×480,
tactile capacitif GT911) installé **de série sur l'automate**. Il permet à
l'installateur — ou au client **sans smartphone** — d'**associer les appareils aux
zones** directement depuis l'écran.

> L'ESP32-S3 n'affiche PAS l'application web (c'est un microcontrôleur). Ce firmware
> est une **interface native LVGL** qui dialogue avec l'automate via l'API
> `/api/panel/*` (jeton fixe `X-Panel-Token`).

---

## 1. Ce dont vous avez besoin
- La carte **Waveshare ESP32-S3-Touch-LCD-4.3** (ou 4.3B/4.3C).
- Un câble **USB-C** (données) vers votre PC.
- **VS Code + PlatformIO** (extension). Alternative : Arduino IDE (voir §6).

## 2. Réglages (obligatoire) — `src/config.h`
```c
#define WIFI_SSID     "ZONECLIMATE"            // Wi-Fi de l'automate (ou Wi-Fi maison)
#define WIFI_PASSWORD "..."                    // mot de passe du réseau
#define BACKEND_URL   "http://10.42.0.1"       // AP: 10.42.0.1  |  maison: http://zoneclimate.local
#define PANEL_TOKEN   "ZONECLIMATE-PANEL-2026" // == PANEL_TOKEN du backend (.env)
```
> Le `PANEL_TOKEN` doit être **identique** à celui du backend
> (`backend/.env` et `docker-compose.pi.yml`). Valeur par défaut prête à l'emploi.

## 3. Compiler et flasher (PlatformIO)
```bash
cd firmware/esp32s3-panel
pio run                 # compile
pio run -t upload       # téléverse (carte branchée en USB-C)
pio device monitor      # logs série (115200 bauds)
```

## 4. Utilisation sur le chantier
1. À l'allumage, l'écran se connecte au Wi-Fi puis interroge l'automate.
2. **S'il y a plusieurs zonings**, l'écran demande lequel configurer (sinon il entre direct).
3. Écran d'appairage :
   - **Colonne gauche** = appareils détectés **non associés** (✓ = en ligne). Touchez-en un
     (ou « Saisir un code manuellement » et tapez le code imprimé sur l'appareil).
   - **Colonne droite** = **zones** existantes. Touchez la zone cible
     (ou « Créer une nouvelle zone » et saisissez son nom).
   - Bouton **ASSOCIER** → l'appareil est rattaché à la zone. La liste se met à jour.

## 5. Endpoints utilisés (référence)
| Méthode | Chemin | Rôle |
|--------|--------|------|
| GET | `/api/panel/installations` | liste des zonings de l'automate |
| GET | `/api/panel/installations/{iid}/zones` | zones d'un zoning |
| GET | `/api/panel/installations/{iid}/catalog/unassigned` | appareils non associés |
| POST | `/api/panel/installations/{iid}/associate` | associe `{code, zone_id \| new_zone_name}` |

Tous exigent l'en-tête `X-Panel-Token: <PANEL_TOKEN>`.

## 6. ⚠️ Si l'écran reste noir ou le tactile ne répond pas
Les révisions de carte diffèrent sur l'**expandeur CH422G** (reset écran/tactile +
rétroéclairage) et les versions de librairies :
- **Versions VALIDÉES** : Arduino-ESP32 **core 2.x** (`platform = espressif32@6.5.0`),
  **LVGL 8.4** (⚠️ **PAS** LVGL 9), Arduino_GFX, bb_captouch.
- La lib d'expandeur peut varier. Si `ESP_IOExpander_Library.h` n'est pas trouvée ou son
  API diffère, installez la lib **du zip officiel Waveshare** :
  `https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-4.3/Esp32-s3-touch-lcd-lib.zip`
- **Solution de repli fiable** : reprenez l'initialisation écran+tactile du démo officiel
  Waveshare (« lvgl_porting ») dans `board.cpp::board_init()`, et **gardez** `ui.cpp` et
  `api.cpp` tels quels (toute la logique métier et réseau y est isolée).
- Couleurs inversées (bleu/rouge) ? Passez `LV_COLOR_16_SWAP` à `1` dans `src/lv_conf.h`.

## 7. Architecture du code
```
src/
├── config.h    ← À PERSONNALISER (Wi-Fi, URL backend, jeton)
├── board.cpp   ← écran RGB + tactile GT911 + CH422G + LVGL (spécifique carte)
├── api.cpp     ← client HTTP /api/panel/* (réutilisable)
├── ui.cpp      ← écrans LVGL (choix zoning / appairage) (réutilisable)
└── main.cpp    ← setup() / loop()
```

## 8. Notes
- Firmware **non testé en usine par l'assistant** (pas d'exécution embarquée possible en
  cloud) : à **flasher et valider sur la carte**.
- La carte n'a **pas de caméra** → pas de scan de QR code : sélection dans la liste ou
  saisie du code au clavier tactile.
