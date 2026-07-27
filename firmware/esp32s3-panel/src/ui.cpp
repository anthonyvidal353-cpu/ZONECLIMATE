// ============================================================================
// ui.cpp — Interface LVGL du panneau d'appairage ClimaZone
//   Écran 1 : choix de l'installation (si plusieurs)
//   Écran 2 : appairage — liste des appareils non associés + liste des zones
//             + "Nouvelle zone" + saisie manuelle du code + bouton ASSOCIER
// ============================================================================
#include "ui.h"
#include "api.h"
#include <lvgl.h>
#include <Arduino.h>

#define MAX_ITEMS 40
#define CZ_PURPLE  lv_color_hex(0x7C3AED)
#define CZ_GREEN   lv_color_hex(0x16A34A)
#define CZ_RED     lv_color_hex(0xDC2626)
#define CZ_DARK    lv_color_hex(0x0F172A)

// --- État courant ---
static char g_iid[64] = "";
static char g_iid_name[48] = "";
static char g_code[32] = "";
static char g_zone_id[64] = "";
static char g_new_zone[40] = "";

// --- Tables (évite les fuites : on stocke par index) ---
static char dev_codes[MAX_ITEMS][32];
static char dev_names[MAX_ITEMS][56];
static int dev_online[MAX_ITEMS];
static int dev_count = 0;

static char zone_ids[MAX_ITEMS][64];
static char zone_names[MAX_ITEMS][48];
static int zone_count = 0;

// --- Widgets réutilisés ---
static lv_obj_t *lbl_status = nullptr;
static lv_obj_t *lbl_sel = nullptr;      // "Appareil: X  →  Zone: Y"
static lv_obj_t *list_dev = nullptr;
static lv_obj_t *list_zone = nullptr;

static void build_installations();
static void build_main();

// ---------------------------------------------------------------------------
static void set_status(const char *txt, lv_color_t color) {
    if (!lbl_status) return;
    lv_label_set_text(lbl_status, txt);
    lv_obj_set_style_text_color(lbl_status, color, 0);
}

// Recherche du nom de zone sélectionnée
static const char *selected_zone_name() {
    for (int i = 0; i < zone_count; i++)
        if (strcmp(zone_ids[i], g_zone_id) == 0) return zone_names[i];
    return "(aucune)";
}

static void refresh_sel_label() {
    if (!lbl_sel) return;
    char buf[160];
    const char *dev = strlen(g_code) ? g_code : "(aucun)";
    const char *zn;
    if (strlen(g_new_zone)) zn = g_new_zone;
    else if (strlen(g_zone_id)) zn = selected_zone_name();
    else zn = "(aucune)";
    snprintf(buf, sizeof(buf), "Appareil : %s   #  Zone : %s", dev, zn);
    lv_label_set_text(lbl_sel, buf);
}

// ---------------------------------------------------------------------------
// Clavier tactile (plein écran) pour saisie manuelle : code appareil / nom de zone
// mode 0 = code, mode 1 = nouvelle zone
static void kb_ready_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t *kb = (lv_obj_t *)lv_event_get_user_data(e);
    lv_obj_t *ta = lv_keyboard_get_textarea(kb);
    intptr_t mode = (intptr_t)lv_obj_get_user_data(kb);
    if (code == LV_EVENT_READY) {
        const char *txt = lv_textarea_get_text(ta);
        if (mode == 0) {
            strncpy(g_code, txt, sizeof(g_code) - 1);
            g_code[sizeof(g_code) - 1] = 0;
        } else {
            strncpy(g_new_zone, txt, sizeof(g_new_zone) - 1);
            g_new_zone[sizeof(g_new_zone) - 1] = 0;
            g_zone_id[0] = 0;  // nouvelle zone => on oublie la zone existante
        }
    }
    if (code == LV_EVENT_READY || code == LV_EVENT_CANCEL) {
        lv_obj_del(lv_obj_get_parent(kb));  // supprime l'overlay
        refresh_sel_label();
    }
}

static void open_keyboard(intptr_t mode, const char *title) {
    lv_obj_t *ov = lv_obj_create(lv_scr_act());
    lv_obj_set_size(ov, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_color(ov, CZ_DARK, 0);
    lv_obj_clear_flag(ov, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(ov);
    lv_label_set_text(t, title);
    lv_obj_set_style_text_color(t, lv_color_white(), 0);
    lv_obj_align(t, LV_ALIGN_TOP_MID, 0, 12);

    lv_obj_t *ta = lv_textarea_create(ov);
    lv_textarea_set_one_line(ta, true);
    lv_textarea_set_placeholder_text(ta, mode == 0 ? "CZ-XXXX" : "Nom de la zone");
    lv_obj_set_width(ta, LV_PCT(80));
    lv_obj_align(ta, LV_ALIGN_TOP_MID, 0, 48);

    lv_obj_t *kb = lv_keyboard_create(ov);
    lv_obj_set_user_data(kb, (void *)mode);
    lv_keyboard_set_mode(kb, mode == 0 ? LV_KEYBOARD_MODE_TEXT_UPPER : LV_KEYBOARD_MODE_TEXT_LOWER);
    lv_keyboard_set_textarea(kb, ta);
    lv_obj_add_event_cb(kb, kb_ready_cb, LV_EVENT_READY, kb);
    lv_obj_add_event_cb(kb, kb_ready_cb, LV_EVENT_CANCEL, kb);
}

// ---------------------------------------------------------------------------
static void dev_btn_cb(lv_event_t *e) {
    intptr_t i = (intptr_t)lv_event_get_user_data(e);
    if (i < 0 || i >= dev_count) return;
    strncpy(g_code, dev_codes[i], sizeof(g_code) - 1);
    g_code[sizeof(g_code) - 1] = 0;
    refresh_sel_label();
}

static void zone_btn_cb(lv_event_t *e) {
    intptr_t i = (intptr_t)lv_event_get_user_data(e);
    if (i < 0 || i >= zone_count) return;
    strncpy(g_zone_id, zone_ids[i], sizeof(g_zone_id) - 1);
    g_zone_id[sizeof(g_zone_id) - 1] = 0;
    g_new_zone[0] = 0;  // zone existante => pas de nouvelle zone
    refresh_sel_label();
}

static void manual_code_cb(lv_event_t *e) { open_keyboard(0, "Saisir le code de l'appareil"); }
static void new_zone_cb(lv_event_t *e) { open_keyboard(1, "Nom de la nouvelle zone"); }

static void refresh_devices() {
    if (!list_dev) return;
    lv_obj_clean(list_dev);
    dev_count = 0;
    DynamicJsonDocument doc(8192);
    if (api_get_unassigned(g_iid, doc)) {
        for (JsonObject o : doc.as<JsonArray>()) {
            if (dev_count >= MAX_ITEMS) break;
            int i = dev_count++;
            strncpy(dev_codes[i], o["code"] | "", 31);
            const char *nm = o["name"] | "Appareil";
            const char *cat = o["category"] | "";
            dev_online[i] = (o["online"] | true) ? 1 : 0;
            snprintf(dev_names[i], sizeof(dev_names[i]), "%s %s (%s) [%s]",
                     dev_online[i] ? LV_SYMBOL_OK : LV_SYMBOL_WARNING,
                     nm, cat, dev_codes[i]);
            lv_obj_t *b = lv_list_add_btn(list_dev, LV_SYMBOL_WIFI, dev_names[i]);
            lv_obj_add_event_cb(b, dev_btn_cb, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        }
    }
    if (dev_count == 0)
        lv_list_add_text(list_dev, "Aucun appareil a associer");
}

static void refresh_zones() {
    if (!list_zone) return;
    lv_obj_clean(list_zone);
    zone_count = 0;
    DynamicJsonDocument doc(8192);
    if (api_get_zones(g_iid, doc)) {
        for (JsonObject o : doc.as<JsonArray>()) {
            if (zone_count >= MAX_ITEMS) break;
            int i = zone_count++;
            strncpy(zone_ids[i], o["id"] | "", 63);
            const char *nm = o["name"] | "Zone";
            bool master = o["is_master"] | false;
            snprintf(zone_names[i], sizeof(zone_names[i]), "%s%s", nm, master ? " (maitre)" : "");
            lv_obj_t *b = lv_list_add_btn(list_zone, LV_SYMBOL_HOME, zone_names[i]);
            lv_obj_add_event_cb(b, zone_btn_cb, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        }
    }
}

static void associate_cb(lv_event_t *e) {
    if (!strlen(g_code)) { set_status("Choisissez d'abord un appareil.", CZ_RED); return; }
    if (!strlen(g_zone_id) && !strlen(g_new_zone)) {
        set_status("Choisissez une zone (ou creez-en une).", CZ_RED);
        return;
    }
    set_status("Association en cours...", CZ_PURPLE);
    lv_refr_now(NULL);
    String msg;
    int rc = api_associate(g_iid, g_code,
                           strlen(g_new_zone) ? "" : g_zone_id,
                           g_new_zone, msg);
    if (rc == 200) {
        set_status(msg.c_str(), CZ_GREEN);
        // Réinitialise la sélection et rafraîchit les listes
        g_code[0] = 0; g_zone_id[0] = 0; g_new_zone[0] = 0;
        refresh_devices();
        refresh_zones();
        refresh_sel_label();
    } else {
        set_status(msg.c_str(), CZ_RED);
    }
}

static void refresh_cb(lv_event_t *e) {
    refresh_devices();
    refresh_zones();
    set_status("Listes actualisees.", CZ_PURPLE);
}

// ---------------------------------------------------------------------------
static void build_main() {
    lv_obj_t *s = lv_scr_act();
    lv_obj_clean(s);
    lv_obj_set_style_bg_color(s, lv_color_hex(0xF4F4F5), 0);

    // En-tête
    lv_obj_t *hdr = lv_obj_create(s);
    lv_obj_set_size(hdr, LV_PCT(100), 56);
    lv_obj_align(hdr, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_color(hdr, CZ_DARK, 0);
    lv_obj_set_style_radius(hdr, 0, 0);
    lv_obj_clear_flag(hdr, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t *title = lv_label_create(hdr);
    char tb[96];
    snprintf(tb, sizeof(tb), LV_SYMBOL_PLUS " Associer un appareil  -  %s", g_iid_name);
    lv_label_set_text(title, tb);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 12, 0);

    lv_obj_t *btn_ref = lv_btn_create(hdr);
    lv_obj_align(btn_ref, LV_ALIGN_RIGHT_MID, -8, 0);
    lv_obj_add_event_cb(btn_ref, refresh_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *rl = lv_label_create(btn_ref);
    lv_label_set_text(rl, LV_SYMBOL_REFRESH " Actualiser");

    // Colonne gauche : appareils
    lv_obj_t *cap1 = lv_label_create(s);
    lv_label_set_text(cap1, "1. Appareil (non associe)");
    lv_obj_align(cap1, LV_ALIGN_TOP_LEFT, 16, 64);
    list_dev = lv_list_create(s);
    lv_obj_set_size(list_dev, 370, 240);
    lv_obj_align(list_dev, LV_ALIGN_TOP_LEFT, 16, 88);

    lv_obj_t *bm = lv_btn_create(s);
    lv_obj_set_size(bm, 370, 40);
    lv_obj_align(bm, LV_ALIGN_TOP_LEFT, 16, 336);
    lv_obj_add_event_cb(bm, manual_code_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *bml = lv_label_create(bm);
    lv_label_set_text(bml, LV_SYMBOL_KEYBOARD " Saisir un code manuellement");
    lv_obj_center(bml);

    // Colonne droite : zones
    lv_obj_t *cap2 = lv_label_create(s);
    lv_label_set_text(cap2, "2. Zone de destination");
    lv_obj_align(cap2, LV_ALIGN_TOP_RIGHT, -16, 64);
    list_zone = lv_list_create(s);
    lv_obj_set_size(list_zone, 370, 240);
    lv_obj_align(list_zone, LV_ALIGN_TOP_RIGHT, -16, 88);

    lv_obj_t *bz = lv_btn_create(s);
    lv_obj_set_size(bz, 370, 40);
    lv_obj_align(bz, LV_ALIGN_TOP_RIGHT, -16, 336);
    lv_obj_add_event_cb(bz, new_zone_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *bzl = lv_label_create(bz);
    lv_label_set_text(bzl, LV_SYMBOL_PLUS " Creer une nouvelle zone");
    lv_obj_center(bzl);

    // Sélection courante
    lbl_sel = lv_label_create(s);
    lv_obj_align(lbl_sel, LV_ALIGN_TOP_MID, 0, 388);
    refresh_sel_label();

    // Bouton ASSOCIER
    lv_obj_t *ba = lv_btn_create(s);
    lv_obj_set_size(ba, 320, 56);
    lv_obj_align(ba, LV_ALIGN_BOTTOM_MID, 0, -44);
    lv_obj_set_style_bg_color(ba, CZ_PURPLE, 0);
    lv_obj_add_event_cb(ba, associate_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *bal = lv_label_create(ba);
    lv_label_set_text(bal, LV_SYMBOL_OK "  ASSOCIER");
    lv_obj_center(bal);

    // Statut
    lbl_status = lv_label_create(s);
    lv_obj_align(lbl_status, LV_ALIGN_BOTTOM_MID, 0, -12);
    set_status("Selectionnez un appareil et une zone.", CZ_DARK);

    refresh_devices();
    refresh_zones();
}

// ---------------------------------------------------------------------------
static void inst_btn_cb(lv_event_t *e) {
    intptr_t i = (intptr_t)lv_event_get_user_data(e);
    if (i < 0 || i >= dev_count) return;   // réutilise dev_* comme tampon installations
    strncpy(g_iid, dev_codes[i], sizeof(g_iid) - 1);
    strncpy(g_iid_name, dev_names[i], sizeof(g_iid_name) - 1);
    build_main();
}

static void build_installations() {
    lv_obj_t *s = lv_scr_act();
    lv_obj_clean(s);
    lv_obj_set_style_bg_color(s, lv_color_hex(0xF4F4F5), 0);

    DynamicJsonDocument doc(8192);
    if (!api_get_installations(doc)) {
        lv_obj_t *l = lv_label_create(s);
        lv_label_set_text(l, LV_SYMBOL_WARNING " Backend injoignable.\nVerifiez le Wi-Fi et BACKEND_URL.");
        lv_obj_center(l);
        return;
    }
    JsonArray arr = doc.as<JsonArray>();

    // Une seule installation => on entre directement
    if (arr.size() == 1) {
        strncpy(g_iid, arr[0]["id"] | "", sizeof(g_iid) - 1);
        strncpy(g_iid_name, arr[0]["name"] | "", sizeof(g_iid_name) - 1);
        build_main();
        return;
    }

    lv_obj_t *title = lv_label_create(s);
    lv_label_set_text(title, "Choisissez le zoning");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 20);

    lv_obj_t *list = lv_list_create(s);
    lv_obj_set_size(list, 600, 380);
    lv_obj_align(list, LV_ALIGN_CENTER, 0, 20);

    dev_count = 0;  // réutilise le tampon dev_* pour stocker id/nom
    for (JsonObject o : arr) {
        if (dev_count >= MAX_ITEMS) break;
        int i = dev_count++;
        strncpy(dev_codes[i], o["id"] | "", 31);
        strncpy(dev_names[i], o["name"] | "Zoning", 55);
        lv_obj_t *b = lv_list_add_btn(list, LV_SYMBOL_HOME, dev_names[i]);
        lv_obj_add_event_cb(b, inst_btn_cb, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }
    if (dev_count == 0) {
        lv_obj_t *l = lv_label_create(s);
        lv_label_set_text(l, "Aucune installation sur cet automate.");
        lv_obj_center(l);
    }
}

void ui_init() {
    // Splash
    lv_obj_t *s = lv_scr_act();
    lv_obj_set_style_bg_color(s, CZ_DARK, 0);
    lv_obj_t *l = lv_label_create(s);
    lv_label_set_text(l, "ClimaZone\nConnexion...");
    lv_obj_set_style_text_color(l, lv_color_white(), 0);
    lv_obj_center(l);
    lv_refr_now(NULL);

    net_connect_wifi();
    build_installations();
}
