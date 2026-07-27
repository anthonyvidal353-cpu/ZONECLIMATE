#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

// Connexion Wi-Fi (bloquant avec timeout). Renvoie true si connecté.
bool net_connect_wifi(uint32_t timeout_ms = 20000);
bool net_wifi_connected();

// API panneau (/api/panel/*). Toutes ajoutent l'en-tête X-Panel-Token.
// Renvoient true si HTTP 200 ; remplissent `doc` avec la réponse JSON.
bool api_get_installations(JsonDocument &doc);
bool api_get_zones(const char *iid, JsonDocument &doc);
bool api_get_unassigned(const char *iid, JsonDocument &doc);

// Associe un code à une zone existante (zone_id) OU crée une nouvelle zone
// (new_zone_name non vide). Renvoie le code HTTP ; `msg` = message à afficher.
int api_associate(const char *iid, const char *code,
                  const char *zone_id, const char *new_zone_name, String &msg);
