#pragma once
#include <lvgl.h>

// Initialise l'écran RGB, le rétroéclairage (via CH422G), le tactile GT911 et LVGL.
void board_init();

// À appeler en boucle dans loop() : fait tourner LVGL.
void board_loop();
