# ClimaZone — Écran tactile de l'automate (mode borne / kiosque)

Ce guide configure le Raspberry Pi (« l'automate ») pour démarrer **directement sur
l'application en plein écran** dès la mise sous tension. L'écran devient une vraie
**borne tactile** : branché → l'app s'affiche, sans manipulation.

## ✅ Matériel compatible
- **Raspberry Pi** (3 / 4 / 5) avec Raspberry Pi OS.
- Un **écran tactile compatible Raspberry Pi** (DSI ou HDMI + USB tactile), en
  **portrait (480×800)** ou **paysage (800×480)** — l'app s'adapte automatiquement.
- (Option) une **webcam USB** ou la caméra Pi pour scanner les QR codes depuis l'écran.

> ⚠️ Une carte **ESP32-P4 / ESP32-C6** n'est **pas** compatible : c'est un microcontrôleur,
> il ne peut pas afficher une page web. Choisissez un écran pour Raspberry Pi.

## 🚀 Installation en 1 commande
Sur l'automate (Raspberry Pi), récupérez l'**ID de l'installation** (visible dans l'URL
`/installations/<ID>` de l'app), puis lancez :

```bash
sudo bash kiosk-setup.sh "http://localhost:3000/ecran/<ID_INSTALLATION>"
sudo reboot
```

Au redémarrage, l'écran affiche directement ClimaZone en plein écran.

## 🔐 Connexion (une seule fois)
La première fois, connectez-vous avec le compte de l'installation. La session reste
active **7 jours** (jeton stocké localement). Le navigateur en mode kiosque conserve la
session entre les redémarrages.

> Pour une borne **toujours connectée sans ré-authentification**, une option « mode borne »
> (session longue durée dédiée) est prévue — demandez-la si besoin.

## 🖥️ Fonctions intégrées à l'écran
- **Plein écran** (bouton ⤢) + **anti-veille logiciel** (Wake Lock : l'écran ne s'éteint pas).
- **Anti-veille matériel** (xset) configuré par le script.
- **Scanner** : bouton caméra pour appairer un appareil via son QR code, directement sur la borne.
- Contrôle des zones : consigne +/‑, marche/arrêt, mode Chaud/Froid.

## 🧭 Orientation de l'écran
- **Portrait** : ajoutez `display_rotate=1` (ou `3`) dans `/boot/firmware/config.txt`
  (X11) ou via `Réglages d'écran` (Wayland), puis redémarrez.
- L'interface s'adapte seule à la largeur (portrait comme paysage).

## 🌊 Raspberry Pi OS Bookworm (Wayland)
Si le bureau utilise **Wayland** (labwc/wayfire) au lieu de X11, remplacez l'autostart par :

```bash
# ~/.config/wayfire.ini  (section [autostart])
[autostart]
chromium = chromium-browser --kiosk --noerrdialogs --disable-infobars "http://localhost:3000/ecran/<ID_INSTALLATION>"
screensaver = false
dpms = false
```

## 🔧 Dépannage
- Écran noir / pas de démarrage auto : vérifiez l'auto-login du bureau
  (`sudo raspi-config` → *System Options* → *Boot / Auto Login* → *Desktop Autologin*).
- L'app ne charge pas : vérifiez que les conteneurs Docker tournent
  (`docker compose ps`) et que `http://localhost:3000` répond.
- Sortir du kiosque : clavier `Alt+F4` ou `Ctrl+W`, ou touchez le bouton ✕ de l'app.
