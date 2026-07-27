// ============================================================================
// main.cpp — Panneau tactile d'appairage ClimaZone (Waveshare ESP32-S3 4.3")
// ============================================================================
#include <Arduino.h>
#include "board.h"
#include "ui.h"

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("ClimaZone panel booting...");
    board_init();   // écran + tactile + LVGL
    ui_init();      // Wi-Fi + interface d'appairage
}

void loop() {
    board_loop();   // fait tourner LVGL
}
