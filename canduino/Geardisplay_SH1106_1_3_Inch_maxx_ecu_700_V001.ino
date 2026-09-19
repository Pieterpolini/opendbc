#include <SPI.h>
#include <mcp_can.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH1106.h>

#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSansBold9pt7b.h>

constexpr uint8_t SCREEN_ADDRESS = 0x3C;
constexpr int8_t OLED_RESET = -1;

// --- MaxxECU "display" CAN package -------------------------------------------
// CAN 1, standard ID 0x700, little endian, 8 values, 50 Hz.
// All values are 8 bit with offset 0, multiplier 1, divider 1, so each value
// occupies exactly one byte in the order it is configured in MaxxECU:
//
//   byte 0  Dodge 8HP Gearbox Mode   signed 8 bit
//   byte 1  VSS Gear                 signed 8 bit
//   byte 2  Dodge 8HP Drive Mode     signed 8 bit
//   byte 3  Transmission Oil Temp    unsigned 8 bit
//   byte 4  Engine Oil Temp          signed 8 bit
//   byte 5  VSS Speed                signed 8 bit
//   byte 6  fixed value 0            signed 8 bit
//   byte 7  fixed value 0            signed 8 bit
constexpr unsigned long CAN_ID_DISPLAY = 0x700;

constexpr uint8_t IDX_GEARBOX_MODE = 0;
constexpr uint8_t IDX_VSS_GEAR     = 1;
constexpr uint8_t IDX_DRIVE_MODE   = 2;
constexpr uint8_t IDX_TRANS_OIL    = 3;
constexpr uint8_t IDX_ENGINE_OIL   = 4;
constexpr uint8_t IDX_VSS_SPEED    = 5;

// The SH1106 library uses the same drawing functions as the standard SSD1306 library.
// We pass true for the fourth parameter to use the default I2C address for 128x64 display
Adafruit_SH1106 tft(OLED_RESET);
MCP_CAN CAN0(10);

// Live values
char gear = '_';
char gmode = '_';
uint8_t temp = 0;

// Timing
unsigned long lastDisplayUpdate = 0;
constexpr unsigned long DISPLAY_INTERVAL = 500;

// Display positions stored in PROGMEM to save RAM
const int16_t POSITIONS[] PROGMEM = {
  2, 54,     // gear (X, Y)
  52, 30,   // mode (X, Y)
  80, 50    // oil temp (X, Y)
};

inline int16_t getPos(uint8_t index) {
  return pgm_read_word(&POSITIONS[index]);
}

// --- CAN VALUE DECODING ---
// Value encodings per the MaxxECU webhelp (8HP RealTime Data / 8HP Drive modes):
//
//   Gearbox Mode  0 = Park, 1 = Reverse, 2 = Neutral, 4 = Drive,
//                 8 / 16 / 32 = Manual, Manual+, Manual-
//   VSS Gear      1..8 = engaged gear, 0 = none, -1 = reverse
//   Drive Mode    0 = NOT_SET, 1 = STREET, 3 = SPORT, 5 = TRACK, 10 = DRAG

constexpr int8_t MODE_PARK    = 0;
constexpr int8_t MODE_REVERSE = 1;
constexpr int8_t MODE_NEUTRAL = 2;
constexpr int8_t MODE_DRIVE   = 4;

// Manual is reported as 8; some documentation also lists 5, and the paddle
// positions Manual+ / Manual- as 16 / 32. Accept all of them.
inline bool isManualMode(int8_t gearboxMode) {
  return gearboxMode == 5 || gearboxMode == 8 || gearboxMode == 16 || gearboxMode == 32;
}

// Gear character. The gearbox mode selector decides P / R / N; in Drive or
// Manual the engaged gear comes from VSS Gear.
char decodeGear(int8_t vssGear, int8_t gearboxMode) {
  switch (gearboxMode) {
    case MODE_PARK:    return 'P';
    case MODE_REVERSE: return 'R';
    case MODE_NEUTRAL: return 'N';
    default: break;
  }

  if (vssGear >= 1 && vssGear <= 8) return '0' + vssGear;
  if (vssGear == -1) return 'R';

  // Drive or Manual selected but no gear engaged yet (standing still).
  if (gearboxMode == MODE_DRIVE || isManualMode(gearboxMode)) return 'D';

  return '-';
}

// Drive mode character: S = STREET, P = SPORT, T = TRACK, D = DRAG.
char decodeDriveMode(int8_t driveMode) {
  switch (driveMode) {
    case 1:  return 'S';
    case 3:  return 'P';
    case 5:  return 'T';
    case 10: return 'D';
    default: return '-'; // 0 = NOT_SET
  }
}

// --- FADE EFFECT HELPER FUNCTIONS ---

// Helper function to draw the "KCP" text with specified font
void drawKCPText(const GFXfont *font) {
  tft.clearDisplay();
  tft.setTextColor(WHITE);
  tft.setFont(font);
  tft.setCursor(0, 15);
  tft.println(F("Build by KCP"));
  tft.display();
}

// Function to simulate fade-in using different font styles
void fadeInKCP() {
  const int DELAY_TIME = 150; // Delay between fade steps

  // Step 1: Draw with regular, smaller font (simulates dimmer look)
  drawKCPText(&FreeSans9pt7b);
  delay(DELAY_TIME);

  // Step 2: Draw with the bold, final font (full brightness)
  drawKCPText(&FreeSansBold9pt7b);
  tft.display();
}

// Function to simulate fade-out by wiping the text away
void fadeOutKCP() {
  const int DELAY_TIME = 20; // Fast delay for smooth wiping
  const int STEP_WIDTH = 10; // How many pixels to wipe per step

  // Define the area to wipe (covers where the text was drawn)
  const int startX = 0;
  const int startY = 0;
  const int wipeHeight = 25;

  // Wipe the area from left to right
  for (int x = startX; x < tft.width(); x += STEP_WIDTH) {
    // Fill a rectangle with black (erasing the content)
    tft.fillRect(x, startY, STEP_WIDTH, wipeHeight, BLACK);
    tft.display();
    delay(DELAY_TIME);
  }
}

// --- SETUP AND LOOP ---

void setup() {
  Serial.begin(115200);

  if (CAN0.begin(MCP_ANY, CAN_500KBPS, MCP_16MHZ) == CAN_OK)
    Serial.println(F("MCP2515 Initialized Successfully!"));
  else
    Serial.println(F("Error Initializing MCP2515..."));

  CAN0.setMode(MCP_NORMAL);

  Wire.begin();
  tft.begin(SH1106_SWITCHCAPVCC, SCREEN_ADDRESS, true);
  

  // --- STARTUP FADE EFFECT ---
  
  fadeInKCP(); // Fade In: Draw text with increasing boldness

  delay(2000); // Hold full brightness for 2 seconds

  fadeOutKCP(); // Fade Out: Wipe the text away
  
  // --- END OF STARTUP EFFECT ---

  // Final cleanup and setup for main loop
  tft.clearDisplay(); 
  tft.display();
  tft.setFont(NULL);
}

void updateDisplay() {
  tft.clearDisplay();

  // GEAR
  tft.setFont(&FreeSans9pt7b);
  tft.setTextColor(WHITE); // Ensure text is white over the new BLACK background
  tft.setTextSize(4);
  tft.setCursor(getPos(0), getPos(1)); 
  tft.print(gear);

  // MODE
  tft.setFont(&FreeSansBold9pt7b);
  tft.setTextSize(2);
  tft.setCursor(getPos(2), getPos(3));
  tft.print(gmode);

  // OIL TEMP
  tft.setFont(NULL);
  tft.setTextSize(1);
  tft.setCursor(getPos(4), getPos(5));
  tft.print(F("OIL:"));
  tft.print(temp);

  tft.display();
}

void loop() {
  // CAN read
  if (CAN_MSGAVAIL == CAN0.checkReceive()) {
    long unsigned int rxId;
    byte len;
    byte rxBuf[8];

    CAN0.readMsgBuf(&rxId, &len, rxBuf);

    // --- Gear, drive mode and transmission oil temp all come from 0x700 ---
    if (rxId == CAN_ID_DISPLAY && len >= 4) {
      gear = decodeGear((int8_t)rxBuf[IDX_VSS_GEAR], (int8_t)rxBuf[IDX_GEARBOX_MODE]);
      gmode = decodeDriveMode((int8_t)rxBuf[IDX_DRIVE_MODE]);
      temp = rxBuf[IDX_TRANS_OIL];
    }

    // --- Light serial dump WITHOUT sprintf() ---
    Serial.print(F("ID:0x"));
    Serial.print(rxId, HEX);
    Serial.print(F(" DLC:"));
    Serial.print(len);
    Serial.print(F(" Data:"));

    if (rxId & 0x40000000)
      Serial.print(F(" RFR"));
    else {
      for (byte i = 0; i < len; i++) {
        Serial.print(F(" 0x"));
        if (rxBuf[i] < 0x10) Serial.print('0');
        Serial.print(rxBuf[i], HEX);
      }
    }
    Serial.println();
  }

  // --- Change detection ---
  static uint8_t lastGear = '-';
  static uint8_t lastMode = '-';
  static uint8_t lastTemp = 0;

  bool changed = (gear != lastGear) || (gmode != lastMode) || (temp != lastTemp);

  if (changed && millis() - lastDisplayUpdate >= DISPLAY_INTERVAL) {
    lastGear = gear;
    lastMode = gmode;
    lastTemp = temp;

    updateDisplay();
    lastDisplayUpdate = millis();
  }
}
