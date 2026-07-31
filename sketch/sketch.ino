#include <Arduino.h>
#include <Arduino_RouterBridge.h>
#include <SPI.h>

// --- PIN DEFINITIONS ---
const int VOCAL_BUTTON     = 2;
const int BASS_BUTTON      = 3;
const int DRUMS_BUTTON     = 4;
const int OTHER_BUTTON     = 5;
const int FINALIZE_BUTTON  = 6;
const int PLAYPAUSE_BUTTON = 7;
const int VOLUME_POT       = A0;

// TFT Display Pins (SPI)
#define TFT_CS   10
#define TFT_RST  8
#define TFT_DC   9

// --- ST7735 DISPLAY COMMANDS ---
#define ST7735_SWRESET 0x01
#define ST7735_SLPOUT  0x11
#define ST7735_COLMOD  0x3A
#define ST7735_DISPON  0x29
#define ST7735_CASET   0x2A
#define ST7735_RASET   0x2B
#define ST7735_RAMWR   0x2C

// Color definitions (16-bit RGB565)
#define COLOR_BLACK   0x0000
#define COLOR_GREEN   0x07E0
#define COLOR_WHITE   0xFFFF
#define COLOR_RED     0xF800
#define COLOR_YELLOW  0xFFE0

#define SCREEN_W 128
#define SCREEN_H 160

// --- 5x7 FONT TABLE (space, digits, A-Z, basic punctuation) ---
struct Glyph {
  char c;
  uint8_t bits[5];
};

const Glyph FONT[] = {
  {' ', {0x00,0x00,0x00,0x00,0x00}},
  {'!', {0x00,0x00,0x5F,0x00,0x00}},
  {',', {0x00,0x50,0x30,0x00,0x00}},
  {'.', {0x00,0x60,0x60,0x00,0x00}},
  {'-', {0x08,0x08,0x08,0x08,0x08}},
  {':', {0x00,0x36,0x36,0x00,0x00}},
  {'0', {0x3E,0x51,0x49,0x45,0x3E}},
  {'1', {0x00,0x42,0x7F,0x40,0x00}},
  {'2', {0x42,0x61,0x51,0x49,0x46}},
  {'3', {0x21,0x41,0x45,0x4B,0x31}},
  {'4', {0x18,0x14,0x12,0x7F,0x10}},
  {'5', {0x27,0x45,0x45,0x45,0x39}},
  {'6', {0x3C,0x4A,0x49,0x49,0x30}},
  {'7', {0x01,0x71,0x09,0x05,0x03}},
  {'8', {0x36,0x49,0x49,0x49,0x36}},
  {'9', {0x06,0x49,0x49,0x29,0x1E}},
  {'A', {0x7E,0x11,0x11,0x11,0x7E}},
  {'B', {0x7F,0x49,0x49,0x49,0x36}},
  {'C', {0x3E,0x41,0x41,0x41,0x22}},
  {'D', {0x7F,0x41,0x41,0x22,0x1C}},
  {'E', {0x7F,0x49,0x49,0x41,0x41}},
  {'F', {0x7F,0x09,0x09,0x01,0x01}},
  {'G', {0x3E,0x41,0x49,0x49,0x7A}},
  {'H', {0x7F,0x08,0x08,0x08,0x7F}},
  {'I', {0x00,0x41,0x7F,0x41,0x00}},
  {'J', {0x20,0x40,0x41,0x3F,0x01}},
  {'K', {0x7F,0x08,0x14,0x22,0x41}},
  {'L', {0x7F,0x40,0x40,0x40,0x40}},
  {'M', {0x7F,0x02,0x0C,0x02,0x7F}},
  {'N', {0x7F,0x04,0x08,0x10,0x7F}},
  {'O', {0x3E,0x41,0x41,0x41,0x3E}},
  {'P', {0x7F,0x09,0x09,0x09,0x06}},
  {'Q', {0x3E,0x41,0x51,0x21,0x5E}},
  {'R', {0x7F,0x09,0x19,0x29,0x46}},
  {'S', {0x46,0x49,0x49,0x49,0x31}},
  {'T', {0x01,0x01,0x7F,0x01,0x01}},
  {'U', {0x3F,0x40,0x40,0x40,0x3F}},
  {'V', {0x1F,0x20,0x40,0x20,0x1F}},
  {'W', {0x3F,0x40,0x38,0x40,0x3F}},
  {'X', {0x63,0x14,0x08,0x14,0x63}},
  {'Y', {0x07,0x08,0x70,0x08,0x07}},
  {'Z', {0x61,0x51,0x49,0x45,0x43}},
};
const int FONT_COUNT = sizeof(FONT) / sizeof(Glyph);

const uint8_t* findGlyph(char c) {
  if (c >= 'a' && c <= 'z') c -= 32;
  for (int i = 0; i < FONT_COUNT; i++) {
    if (FONT[i].c == c) return FONT[i].bits;
  }
  return FONT[0].bits;
}

// --- BUTTON STATE CALLBACKS FOR BRIDGE (Python polls these) ---
int vocal_state()    { return !digitalRead(VOCAL_BUTTON); }
int bass_state()     { return !digitalRead(BASS_BUTTON); }
int drums_state()    { return !digitalRead(DRUMS_BUTTON); }
int other_state()    { return !digitalRead(OTHER_BUTTON); }
int finalize_state() { return !digitalRead(FINALIZE_BUTTON); }

// --- DISPLAY HELPER FUNCTIONS ---
void writeCommand(uint8_t cmd) {
  digitalWrite(TFT_DC, LOW);
  digitalWrite(TFT_CS, LOW);
  SPI.transfer(cmd);
  digitalWrite(TFT_CS, HIGH);
}

void writeData(uint8_t data) {
  digitalWrite(TFT_DC, HIGH);
  digitalWrite(TFT_CS, LOW);
  SPI.transfer(data);
  digitalWrite(TFT_CS, HIGH);
}

void initDisplay() {
  digitalWrite(TFT_RST, HIGH); delay(50);
  digitalWrite(TFT_RST, LOW);  delay(50);
  digitalWrite(TFT_RST, HIGH); delay(150);

  writeCommand(ST7735_SWRESET); delay(150);
  writeCommand(ST7735_SLPOUT);  delay(150);
  writeCommand(ST7735_COLMOD);  writeData(0x05);
  writeCommand(ST7735_DISPON);  delay(100);
}

void fillRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint16_t color) {
  writeCommand(ST7735_CASET);
  writeData(0x00); writeData(x);
  writeData(0x00); writeData(x + w - 1);
  writeCommand(ST7735_RASET);
  writeData(0x00); writeData(y);
  writeData(0x00); writeData(y + h - 1);

  writeCommand(ST7735_RAMWR);
  digitalWrite(TFT_DC, HIGH);
  digitalWrite(TFT_CS, LOW);
  uint32_t total = (uint32_t)w * h;
  for (uint32_t i = 0; i < total; i++) {
    SPI.transfer(color >> 8);
    SPI.transfer(color & 0xFF);
  }
  digitalWrite(TFT_CS, HIGH);
}

void fillScreen(uint16_t color) {
  fillRect(0, 0, SCREEN_W, SCREEN_H, color);
}

void drawChar(uint8_t x, uint8_t y, const uint8_t* glyph, uint16_t color, uint8_t size) {
  for (uint8_t col = 0; col < 5; col++) {
    uint8_t line = glyph[col];
    for (uint8_t row = 0; row < 7; row++) {
      if (line & (1 << row)) {
        fillRect(x + col * size, y + row * size, size, size, color);
      }
    }
  }
}

void drawText(uint8_t x, uint8_t y, const char* text, uint16_t color, uint8_t size) {
  uint8_t cursor = x;
  uint8_t spacing = size;
  while (*text) {
    drawChar(cursor, y, findGlyph(*text), color, size);
    cursor += (5 * size) + spacing;
    text++;
  }
}

// --- FIVE-LINE STATUS DISPLAY -------------------------------------------
// Each row is independently owned by one piece of app state, so different
// events (upload, mute, finalize, play) can never overwrite each other.
#define ROW1_Y 8
#define ROW2_Y 32
#define ROW3_Y 56
#define ROW4_Y 80
#define ROW5_Y 104
#define ROW_H  20

bool set_display(String line1, String line2, String line3, String line4, String line5) {
  fillRect(0, ROW1_Y - 4, SCREEN_W, ROW_H, COLOR_BLACK);
  fillRect(0, ROW2_Y - 4, SCREEN_W, ROW_H, COLOR_BLACK);
  fillRect(0, ROW3_Y - 4, SCREEN_W, ROW_H, COLOR_BLACK);
  fillRect(0, ROW4_Y - 4, SCREEN_W, ROW_H, COLOR_BLACK);
  fillRect(0, ROW5_Y - 4, SCREEN_W, ROW_H, COLOR_BLACK);

  drawText(4, ROW1_Y, line1.c_str(), COLOR_GREEN, 1);
  drawText(4, ROW2_Y, line2.c_str(), COLOR_WHITE, 1);
  drawText(4, ROW3_Y, line3.c_str(), COLOR_WHITE, 1);
  drawText(4, ROW4_Y, line4.c_str(), COLOR_YELLOW, 1);
  drawText(4, ROW5_Y, line5.c_str(), COLOR_YELLOW, 1);

  return true;
}

// --- PLAYBACK CONTROL STATE (MCU pushes events to Python) ---
int lastVolume = -1;
bool lastPlayPauseState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

void setup() {
  Bridge.begin();

  pinMode(VOCAL_BUTTON, INPUT_PULLUP);
  pinMode(BASS_BUTTON, INPUT_PULLUP);
  pinMode(DRUMS_BUTTON, INPUT_PULLUP);
  pinMode(OTHER_BUTTON, INPUT_PULLUP);
  pinMode(FINALIZE_BUTTON, INPUT_PULLUP);
  pinMode(PLAYPAUSE_BUTTON, INPUT_PULLUP);

  Bridge.provide_safe("vocal_state", vocal_state);
  Bridge.provide_safe("bass_state", bass_state);
  Bridge.provide_safe("drums_state", drums_state);
  Bridge.provide_safe("other_state", other_state);
  Bridge.provide_safe("finalize_state", finalize_state);
  Bridge.provide_safe("set_display", set_display);

  pinMode(TFT_DC, OUTPUT);
  pinMode(TFT_RST, OUTPUT);
  pinMode(TFT_CS, OUTPUT);
  digitalWrite(TFT_CS, HIGH);

  SPI.begin();
  SPI.beginTransaction(SPISettings(12000000, MSBFIRST, SPI_MODE0));

  initDisplay();
  fillScreen(COLOR_BLACK);
  set_display("UPLOAD: WAITING", "KEPT: -", "MUTED: -", "FINAL: NO", "PLAY: NO");
}

void loop() {
  // -------------------------
  // Potentiometer volume
  // -------------------------
  int volume = map(analogRead(VOLUME_POT), 0, 1023, 0, 100);

  if (abs(volume - lastVolume) >= 2) {
    lastVolume = volume;
    Bridge.call("set_volume", String(volume));
  }

  // -------------------------
  // Play/Pause button
  // -------------------------
  int playPauseState = digitalRead(PLAYPAUSE_BUTTON);

  if (playPauseState == LOW && lastPlayPauseState == HIGH) {
    if (millis() - lastDebounceTime > debounceDelay) {
      Bridge.call("play_audio");
      lastDebounceTime = millis();
    }
  }
  lastPlayPauseState = playPauseState;

  delay(20);
  // Mute/finalize button states are read on-demand by Python via
  // Bridge.call(...) in poll_buttons() -- no polling needed here for those.
}