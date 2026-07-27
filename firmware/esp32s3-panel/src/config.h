#pragma once
// ============================================================================
// ClimaZone — Réglages du panneau tactile   (À PERSONNALISER par l'installateur)
// ============================================================================

// --- Wi-Fi auquel le panneau se connecte ---
// En usage "sans Internet" : mettez le SSID/mot de passe du réseau « ZONECLIMATE »
// diffusé par l'automate. Sinon, le Wi-Fi de la maison.
#define WIFI_SSID       "ZONECLIMATE"
#define WIFI_PASSWORD   "changez-moi"

// --- Adresse du backend de l'automate ---
// Via l'AP « ZONECLIMATE » : http://10.42.0.1
// Via le réseau maison      : http://zoneclimate.local   (ou http://<IP_DU_PI>)
#define BACKEND_URL     "http://10.42.0.1"

// --- Jeton du panneau (doit être IDENTIQUE à PANEL_TOKEN côté backend/.env) ---
#define PANEL_TOKEN     "ZONECLIMATE-PANEL-2026"

// --- Divers ---
#define HTTP_TIMEOUT_MS 8000
