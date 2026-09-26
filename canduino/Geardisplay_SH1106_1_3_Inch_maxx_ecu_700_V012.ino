#include <SPI.h>
#include <mcp_can.h>
#include <Wire.h>
#include <avr/wdt.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH1106.h>

// Trimmed fonts holding only the characters this display draws, at their
// native size (setTextSize(1)) so nothing is pixel-doubled. About 3.9 kB.
// The Adafruit FreeSans fonts are deliberately NOT included: they cost ~4 kB
// and everything they were used for now uses the built-in 5x7 font.
#include "kcp_fonts.h"

constexpr uint8_t SCREEN_ADDRESS = 0x3C;

// MCP2515 crystal on this Canduino board. Wrong value = wrong bit timing,
// which shows up as no frames at all or as garbled data.
#define MCP_CRYSTAL MCP_8MHZ
constexpr int8_t OLED_RESET = -1;

// --- MaxxECU "display" CAN package -------------------------------------------
// CAN 1, standard ID 0x700, little endian, 8 values, 50 Hz.
// All values are 8 bit, so each one occupies exactly one byte in the order it
// is configured in MaxxECU:
//
//   byte 0  Dodge 8HP Gearbox Mode   signed 8 bit
//   byte 1  VSS Gear                 signed 8 bit
//   byte 2  Dodge 8HP Drive Mode     signed 8 bit
//   byte 3  Transmission Oil Temp    unsigned 8 bit
//   byte 4  Engine Oil Temp          unsigned 8 bit
//   byte 5  VSS Speed                unsigned 8 bit
//   byte 6  fixed value 0
//   byte 7  fixed value 0
constexpr unsigned long CAN_ID_DISPLAY = 0x700;

constexpr uint8_t IDX_GEARBOX_MODE = 0;
constexpr uint8_t IDX_VSS_GEAR     = 1;
constexpr uint8_t IDX_DRIVE_MODE   = 2;
constexpr uint8_t IDX_TRANS_OIL    = 3;
constexpr uint8_t IDX_ENGINE_OIL   = 4;
constexpr uint8_t IDX_VSS_SPEED    = 5;

// IMPORTANT - set Divider = 10 on both temperature values in the MaxxECU CAN
// package. MaxxECU holds temperatures internally in 0.1 C, so with Divider = 1
// the value overflows the byte: 63.0 C is sent as 630 & 0xFF = 0x76 and 64.0 C
// as 640 & 0xFF = 0x80. That wrap cannot be undone here, only in MaxxECU.
// With Divider = 10 each byte carries whole degrees up to 255 C.
// Set Engine Oil Temp AND VSS Speed to unsigned 8 bit as well: as signed they
// wrap to a negative number above 127.
constexpr uint8_t TEMP_WARN = 100;   // degrees C at which the screen starts to blink

// The SH1106 library uses the same drawing functions as the SSD1306 library.
Adafruit_SH1106 tft(OLED_RESET);
MCP_CAN CAN0(10);

// Live values
char gear = '-';
char gmode = '-';
char gsel = 0;        // 'D' or 'M', 0 = nothing to show
uint8_t toil = 0;     // transmission oil temp, degrees C
uint8_t eoil = 0;     // engine oil temp, degrees C
uint8_t vss = 0;      // vehicle speed, km/h

// Timing
unsigned long lastDraw = 0;
constexpr unsigned long DRAW_INTERVAL = 500;   // normal screen, max 2 Hz
constexpr unsigned long BLINK_INTERVAL = 500;  // warning screen on/off
// Layout, all in pixels on the 128 x 64 panel
constexpr int16_t RIGHT_X = 126;   // right edge everything is aligned to
constexpr int16_t BASE_Y  = 60;    // baseline of the gear and of the D / M
constexpr int16_t MODE_Y  = 25;    // baseline of the drive mode letter
constexpr int16_t SPEED_Y = 49;    // baseline of the speed digits
constexpr int16_t OIL_Y   = 57;    // top of the oil temperature line

uint8_t digits(uint8_t v) { return v >= 100 ? 3 : (v >= 10 ? 2 : 1); }

// Advance width of the drive mode letters in KcpMode.
int16_t modeWidth(char c) {
  if (c == 'C' || c == 'R') return 24;
  if (c == 'E' || c == 'S') return 22;
  return 11;   // the dash
}

// --- CAN VALUE DECODING ---
// Value encodings per the MaxxECU webhelp, Manual (5) confirmed on the car:
//   Gearbox Mode  0 = Park, 1 = Reverse, 2 = Neutral, 4 = Drive, 5 = Manual
//   VSS Gear      1..8 = engaged gear, 0 = none, -1 = reverse
//   Drive Mode    0 = NOT_SET, 1 = STREET, 3 = SPORT, 5 = TRACK, 10 = DRAG
constexpr int8_t MODE_PARK    = 0;
constexpr int8_t MODE_REVERSE = 1;
constexpr int8_t MODE_NEUTRAL = 2;
constexpr int8_t MODE_DRIVE   = 4;
constexpr int8_t MODE_MANUAL  = 5;

// Gear character. The selector decides P / R / N; in Drive or Manual the
// engaged gear comes from VSS Gear.
char decodeGear(int8_t vssGear, int8_t gearboxMode) {
  switch (gearboxMode) {
    case MODE_PARK:    return 'P';
    case MODE_REVERSE: return 'R';
    case MODE_NEUTRAL: return 'N';
    default: break;
  }
  if (vssGear >= 1 && vssGear <= 8) return '0' + vssGear;
  if (vssGear == -1) return 'R';
  // Drive or Manual with no gear reported yet: standing still the box is
  // effectively in first, so show 1 instead of a D that would sit next to the
  // D or M of the selector and say the same thing twice.
  if (gearboxMode == MODE_DRIVE || gearboxMode == MODE_MANUAL) return '1';
  return '-';
}

// D for Drive, M for Manual, nothing in P / R / N.
char decodeSelector(int8_t gearboxMode) {
  if (gearboxMode == MODE_DRIVE)  return 'D';
  if (gearboxMode == MODE_MANUAL) return 'M';
  return 0;
}

// E = STREET (Eco), C = SPORT (Comfort), S = TRACK (Sport), R = DRAG (Race)
char decodeDriveMode(int8_t driveMode) {
  switch (driveMode) {
    case 1:  return 'E';
    case 3:  return 'C';
    case 5:  return 'S';
    case 10: return 'R';
    default: return '-';
  }
}

// --- DRAWING ---

void drawNormal() {
  tft.clearDisplay();
  tft.setTextColor(WHITE);
  tft.setTextSize(1);

  // Gear, bottom left. Shows P / R / N, or 1..8 once a gear is engaged.
  tft.setFont(&KcpGear);
  tft.setCursor(2, BASE_Y);
  tft.print(gear);
  const int16_t gearEnd = tft.getCursorX();

  // Drive mode, top right, right aligned.
  tft.setFont(&KcpMode);
  tft.setCursor(RIGHT_X - modeWidth(gmode), MODE_Y);
  tft.print(gmode);

  // Speed, right aligned and vertically centred between the mode letter and
  // the oil line. Digits are a fixed 13 px wide, the VSS label 17 px.
  const uint8_t spdDigits = digits(vss);
  const int16_t spdX = RIGHT_X - (13 * spdDigits + 20);
  tft.setFont(&KcpNum);
  tft.setCursor(spdX, SPEED_Y);
  tft.print(vss);
  tft.setFont(NULL);
  tft.setCursor(RIGHT_X - 17, SPEED_Y - 7);
  tft.print(F("VSS"));

  // D or M next to the gear, on the same baseline. Only shown beside an actual
  // gear number: with P, R, N or a standstill D the big character already says
  // what the selector is doing, so a second letter adds nothing.
  if (gsel && gear >= '1' && gear <= '8') {
    const int16_t selW = (gsel == 'M') ? 19 : 17;
    int16_t selX = gearEnd + 6;
    if (selX + selW + 4 > spdX) selX = spdX - selW - 4;
    tft.setFont(&KcpSel);
    tft.setCursor(selX, BASE_Y);
    tft.print(gsel);
  }

  // Transmission oil temperature, bottom right. Right aligned so it stays put
  // when it goes from two to three digits.
  tft.setFont(NULL);
  tft.setCursor(127 - 6 * (5 + digits(toil)), OIL_Y);
  tft.print(F("Toil:"));
  tft.print(toil);

  tft.display();
}

// Shown alternating with the normal screen while a temperature is too high.
void drawWarning() {
  tft.clearDisplay();
  tft.setTextColor(WHITE);
  tft.setTextSize(1);

  tft.setFont(&KcpMode);
  tft.setCursor(18, 26);
  tft.print(F("TEMP"));
  tft.setCursor(7, 56);
  tft.print(F("HOOG!"));

  // Small line telling which one is hot: B = bak, M = motor.
  tft.setFont(NULL);
  tft.setCursor(2, 57);
  tft.print('B'); tft.print(toil);
  tft.print(F(" M")); tft.print(eoil);

  tft.display();
}

// --- SETUP AND LOOP ---

void setup() {
  CAN0.begin(MCP_ANY, CAN_500KBPS, MCP_CRYSTAL);
  CAN0.setMode(MCP_NORMAL);

  Wire.begin();
  Wire.setClock(400000);       // 4x faster refresh, so the CAN buffers get
                               // drained sooner and cannot overflow
  Wire.setWireTimeout(25000, true);  // never block forever on a noisy I2C bus

  tft.begin(SH1106_SWITCHCAPVCC, SCREEN_ADDRESS, true);

  // Splash, built-in font only so it costs no extra flash
  tft.clearDisplay();
  tft.setTextColor(WHITE);
  tft.setFont(NULL);
  tft.setTextSize(1);
  tft.setCursor(30, 26);
  tft.println(F("Build by KCP"));
  tft.display();
  delay(700);
  tft.setTextSize(2);
  tft.clearDisplay();
  tft.setCursor(4, 24);
  tft.println(F("Build by"));
  tft.setCursor(40, 44);
  tft.println(F("KCP"));
  tft.display();
  delay(1300);

  tft.clearDisplay();
  tft.display();
  tft.setTextSize(1);

  // Recover automatically from a hang instead of staying frozen until the
  // ignition is cycled. Needs a bootloader that clears the watchdog on reset
  // (optiboot does). Remove these two lines if the board resets in a loop.
  wdt_enable(WDTO_2S);
}

void loop() {
  wdt_reset();

  // Drain every pending frame: the MCP2515 only has two receive buffers and a
  // full one stops reception until it is read.
  while (CAN_MSGAVAIL == CAN0.checkReceive()) {
    unsigned long rxId;
    byte len;
    byte rxBuf[8];
    CAN0.readMsgBuf(&rxId, &len, rxBuf);

    if (rxId == CAN_ID_DISPLAY && len >= 6) {
      gear  = decodeGear((int8_t)rxBuf[IDX_VSS_GEAR], (int8_t)rxBuf[IDX_GEARBOX_MODE]);
      gsel  = decodeSelector((int8_t)rxBuf[IDX_GEARBOX_MODE]);
      gmode = decodeDriveMode((int8_t)rxBuf[IDX_DRIVE_MODE]);
      toil  = rxBuf[IDX_TRANS_OIL];
      eoil  = rxBuf[IDX_ENGINE_OIL];
      vss   = rxBuf[IDX_VSS_SPEED];
    }
  }

  const bool alarm = (toil > TEMP_WARN) || (eoil > TEMP_WARN);
  const unsigned long now = millis();

  static uint8_t lastGear = 0, lastMode = 0, lastSel = 0, lastToil = 0, lastVss = 0;
  static bool lastAlarm = false, blinkOn = false;

  if (alarm) {
    if (now - lastDraw >= BLINK_INTERVAL) {
      blinkOn = !blinkOn;
      if (blinkOn) drawWarning(); else drawNormal();
      lastDraw = now;
    }
  } else {
    const bool changed = (gear != lastGear) || (gmode != lastMode) ||
                         (gsel != lastSel)  || (toil != lastToil) ||
                         (vss  != lastVss)  || lastAlarm;
    if (changed && now - lastDraw >= DRAW_INTERVAL) {
      lastGear = gear; lastMode = gmode; lastSel = gsel; lastToil = toil; lastVss = vss;
      drawNormal();
      lastDraw = now;
    }
  }
  lastAlarm = alarm;
}
