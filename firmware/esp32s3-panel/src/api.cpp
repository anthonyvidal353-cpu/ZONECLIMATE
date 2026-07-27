// ============================================================================
// api.cpp — Client HTTP vers le backend de l'automate (/api/panel/*)
// ============================================================================
#include "api.h"
#include "config.h"
#include <WiFi.h>
#include <HTTPClient.h>

bool net_wifi_connected() { return WiFi.status() == WL_CONNECTED; }

bool net_connect_wifi(uint32_t timeout_ms) {
    if (net_wifi_connected()) return true;
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeout_ms) {
        delay(250);
    }
    return net_wifi_connected();
}

static bool http_get_json(const String &path, JsonDocument &doc) {
    if (!net_wifi_connected() && !net_connect_wifi()) return false;
    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.begin(String(BACKEND_URL) + path);
    http.addHeader("X-Panel-Token", PANEL_TOKEN);
    int rc = http.GET();
    bool ok = false;
    if (rc == 200) {
        DeserializationError err = deserializeJson(doc, http.getStream());
        ok = !err;
    }
    http.end();
    return ok;
}

bool api_get_installations(JsonDocument &doc) {
    return http_get_json("/api/panel/installations", doc);
}

bool api_get_zones(const char *iid, JsonDocument &doc) {
    return http_get_json(String("/api/panel/installations/") + iid + "/zones", doc);
}

bool api_get_unassigned(const char *iid, JsonDocument &doc) {
    return http_get_json(String("/api/panel/installations/") + iid + "/catalog/unassigned", doc);
}

int api_associate(const char *iid, const char *code,
                  const char *zone_id, const char *new_zone_name, String &msg) {
    if (!net_wifi_connected() && !net_connect_wifi()) {
        msg = "Wi-Fi indisponible";
        return -1;
    }
    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.begin(String(BACKEND_URL) + "/api/panel/installations/" + iid + "/associate");
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Panel-Token", PANEL_TOKEN);

    StaticJsonDocument<256> body;
    body["code"] = code;
    if (new_zone_name && strlen(new_zone_name) > 0) {
        body["new_zone_name"] = new_zone_name;
    } else if (zone_id && strlen(zone_id) > 0) {
        body["zone_id"] = zone_id;
    }
    String payload;
    serializeJson(body, payload);

    int rc = http.POST(payload);
    String resp = http.getString();
    if (rc == 200) {
        msg = "Appareil associe !";
    } else {
        StaticJsonDocument<256> d;
        if (deserializeJson(d, resp) == DeserializationError::Ok && d.containsKey("detail")) {
            msg = String((const char *)d["detail"]);
        } else {
            msg = "Erreur (" + String(rc) + ")";
        }
    }
    http.end();
    return rc;
}
