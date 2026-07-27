// ============================================================================
// board.cpp — Bring-up matériel Waveshare ESP32-S3-Touch-LCD-4.3
// ----------------------------------------------------------------------------
// Sources : brochage officiel Waveshare + exemple communautaire Westcott1
//   https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-4.3
//   https://github.com/Westcott1/Waveshare-ESP32-S3-Touch-LCD-4.3-and-Arduino
//
// ⚠️ SI L'ÉCRAN RESTE NOIR OU LE TACTILE NE RÉPOND PAS :
//   Les révisions de carte (4.3 / 4.3B / 4.3C) diffèrent sur l'expandeur CH422G.
//   Dans ce cas, remplacez le contenu de board_init() par l'initialisation du
//   démo officiel Waveshare (« lvgl_porting » de la lib Esp32-s3-touch-lcd-lib.zip)
//   puis appelez ui_init() + le reste. api.cpp et ui.cpp restent inchangés.
// ============================================================================
#include "board.h"
#include <Arduino.h>
#include <esp_heap_caps.h>
#include <Arduino_GFX_Library.h>
#include <bb_captouch.h>
#include <ESP_IOExpander_Library.h>

// --------- Tactile GT911 (I2C) ---------
#define TOUCH_SDA 8
#define TOUCH_SCL 9
#define TOUCH_INT 4
#define TOUCH_RST -1   // reset géré par l'expandeur CH422G

// --------- Broches de l'expandeur CH422G (EXIO) ---------
// Sur la 4.3 : reset écran, reset tactile et rétroéclairage sont pilotés
// par le CH422G, pas par des GPIO directs.
#define EXIO_TP_RST   1
#define EXIO_LCD_BL   2
#define EXIO_LCD_RST  3

static const uint16_t LCD_W = 800;
static const uint16_t LCD_H = 480;

// --------- Panneau RGB (brochage Waveshare) ---------
static Arduino_ESP32RGBPanel *rgbpanel = new Arduino_ESP32RGBPanel(
    5 /* DE */, 3 /* VSYNC */, 46 /* HSYNC */, 7 /* PCLK */,
    1 /* R0 */, 2 /* R1 */, 42 /* R2 */, 41 /* R3 */, 40 /* R4 */,
    39 /* G0 */, 0 /* G1 */, 45 /* G2 */, 48 /* G3 */, 47 /* G4 */, 21 /* G5 */,
    14 /* B0 */, 38 /* B1 */, 18 /* B2 */, 17 /* B3 */, 10 /* B4 */,
    0 /* hsync_pol */, 40 /* hsync_fp */, 48 /* hsync_pw */, 88 /* hsync_bp */,
    0 /* vsync_pol */, 13 /* vsync_fp */, 3 /* vsync_pw */, 32 /* vsync_bp */,
    1 /* pclk_active_neg */, 16000000 /* prefer_speed */);

static Arduino_RGB_Display *gfx =
    new Arduino_RGB_Display(LCD_W, LCD_H, rgbpanel, 0 /* rotation */, true /* auto_flush */);

static BBCapTouch bbct;
static ESP_IOExpander *expander = nullptr;

// --------- LVGL ---------
static lv_disp_draw_buf_t draw_buf;
static lv_color_t *lvbuf = nullptr;

static void lv_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p) {
    uint32_t w = area->x2 - area->x1 + 1;
    uint32_t h = area->y2 - area->y1 + 1;
    gfx->draw16bitRGBBitmap(area->x1, area->y1, (uint16_t *)&color_p->full, w, h);
    lv_disp_flush_ready(drv);
}

static void lv_touch_cb(lv_indev_drv_t *drv, lv_indev_data_t *data) {
    TOUCHINFO ti;
    if (bbct.getSamples(&ti) && ti.count > 0) {
        data->state = LV_INDEV_STATE_PRESSED;
        data->point.x = ti.x[0];
        data->point.y = ti.y[0];
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

void board_init() {
    // 1) Expandeur CH422G : relâche les resets et allume le rétroéclairage.
    expander = new ESP_IOExpander_CH422G(
        (i2c_port_t)I2C_NUM_0, ESP_IO_EXPANDER_I2C_CH422G_ADDRESS_000, TOUCH_SCL, TOUCH_SDA);
    expander->init();
    expander->begin();
    expander->multiPinMode(EXIO_TP_RST | EXIO_LCD_BL | EXIO_LCD_RST, OUTPUT);
    // Pulse de reset écran + tactile
    expander->multiDigitalWrite(EXIO_TP_RST | EXIO_LCD_RST, LOW);
    delay(20);
    expander->multiDigitalWrite(EXIO_TP_RST | EXIO_LCD_RST, HIGH);
    delay(50);
    // Rétroéclairage ON
    expander->digitalWrite(EXIO_LCD_BL, HIGH);

    // 2) Écran
    gfx->begin();
    gfx->fillScreen(BLACK);

    // 3) Tactile GT911
    bbct.init(TOUCH_SDA, TOUCH_SCL, TOUCH_RST, TOUCH_INT);

    // 4) LVGL
    lv_init();
    // Tampon de rendu en PSRAM (1/10e de l'écran)
    size_t buf_px = LCD_W * 80;
    lvbuf = (lv_color_t *)heap_caps_malloc(buf_px * sizeof(lv_color_t), MALLOC_CAP_SPIRAM);
    if (!lvbuf) lvbuf = (lv_color_t *)malloc(buf_px * sizeof(lv_color_t));
    lv_disp_draw_buf_init(&draw_buf, lvbuf, nullptr, buf_px);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = LCD_W;
    disp_drv.ver_res = LCD_H;
    disp_drv.flush_cb = lv_flush_cb;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = lv_touch_cb;
    lv_indev_drv_register(&indev_drv);
}

void board_loop() {
    lv_timer_handler();
    delay(5);
}
