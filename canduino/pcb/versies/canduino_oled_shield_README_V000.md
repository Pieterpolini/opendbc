# CANduino OLED gear-display shield — V000

Plug-on carrier PCB for a **CANduino v4 / v4.5** and a **1.3" SH1106 128×64 I²C OLED**,
for the MaxxECU / Dodge 8HP gear display (CAN package `0x700`).

---

## 1. Board summary

| Item | Value |
|---|---|
| Outline | 28.0 × 62.0 mm, 2 mm corner radius |
| Layers | 2 (F.Cu / B.Cu), 1.6 mm FR4, 1 oz |
| Track width | 0.4 mm signal, 0.6 mm power |
| Clearance | 0.25 mm (design rule 0.2 mm) |
| Vias | 17 × Ø0.8 mm pad / Ø0.4 mm drill |
| Drill sizes | 0.40 / 0.80 / 0.95 / 1.00 mm |
| Ground | Solid pour on B.Cu, thermal relief on all THT ground pads |
| Mounting holes | none (held by the 32-pin socket) |
| Stack height | ≈ 22 mm incl. CANduino, sockets and trimmers |

## 2. Connectors

### J1 — vehicle harness (JST XH 8-pin, right angle, cable exits lengthwise)

| Pin | Net | Goes to | Note |
|---|---|---|---|
| 1 | +12V | F1 → D1 → CANduino VIN | switched ignition feed |
| 2 | GND | ground pour | |
| 3 | CAN-H | CANduino left row pin 16 | |
| 4 | CAN-L | CANduino right row pin 16 | |
| 5 | LIGHT 14.8 V | R1 → PC817 → D5 | dashboard illumination feed |
| 6 | GND | ground pour | return for the lighting feed |
| 7 | spare | A2 | free analogue/digital input |
| 8 | spare | D6 | free digital I/O |

### J2 — OLED (1×4 male pin header, right angle, 2.54 mm)

| Pin | Silk | Net | CANduino |
|---|---|---|---|
| 1 | G | GND | GND |
| 2 | V | +5V | +5V (left row pin 12) |
| 3 | C | SCL | A5 (left row pin 9) |
| 4 | D | SDA | A4 (left row pin 8) |

Use a ready-made 4-way female–female flat cable. Fit the **same right-angle 1×4 header
on the OLED module** so both cable ends run flat.

> **Check before you plug in:** J2 is wired GND / +5V / SCL / SDA. Not every 1.3" module
> uses that order — some are VCC / GND / SCL / SDA. Read the silkscreen on your own
> display first; swapping +5V and GND destroys the module.

## 3. CANduino pins used

| Row / pin | Signal | Used for |
|---|---|---|
| L4 | A0 | RV1 wiper — brightness level 1 (day) |
| L5 | A1 | RV2 wiper — brightness level 2 (night) |
| L6 | A2 | J1 spare |
| L8 | A4 | SDA |
| L9 | A5 | SCL |
| L12 | +5V | OLED + trimmers |
| L14 | GND | |
| L15 | VIN | protected 12 V |
| L16 | CAN-H | to J1.3 |
| R7 | D6 | J1 spare |
| R8 | D5 | lighting input from the opto-coupler |
| R12 | GND | |
| R16 | CAN-L | to J1.4 |

D2 and D10…D13 stay free — they belong to the on-board MCP25625.
CAN termination is **not** on this board; use the CANduino's own `CAN_T` jumper.

## 4. 12 V input protection

```
J1.1 --[F1 PTC 0.5 A]--+--[D1 SS34]--+-- VIN (CANduino)
                       |             |
                    [D2 TVS]     [C1 10u][C2 100n]
                     24 V            |
                       |             |
                      GND           GND
```

| Part | Protects against |
|---|---|
| F1 | short circuit / overload (resettable) |
| D2 | load dump and transients above ~27 V |
| D1 | reverse polarity (series diode, ≈0.4 V drop) |
| C1, C2 | supply dips and HF noise |

The CANduino's own regulator then makes 5 V and 3.3 V.

## 5. Lighting input and brightness

The 14.8 V dashboard illumination feed drives a PC817 opto-coupler through R1 (3k3,
≈4 mA). D3 protects the LED against reverse polarity. The transistor pulls D5 low when
the lights are on; R2 (10k) pulls it up, C5 (1 µF) filters PWM dimming.

Brightness itself is **software**: the SH1106 has no analogue brightness input, only the
contrast register (command `0x81`). The two trimmers set two levels which the sketch
reads on A0 and A1 and writes to the display:

```cpp
void setContrast(uint8_t v) {
  Wire.beginTransmission(SCREEN_ADDRESS);
  Wire.write(0x00);   // command stream
  Wire.write(0x81);   // set contrast
  Wire.write(v);
  Wire.endTransmission();
}

// in loop(), e.g. every 250 ms:
bool night = (digitalRead(5) == LOW);              // lights on
uint8_t want = map(analogRead(night ? A1 : A0), 0, 1023, 0, 255);
if (want != lastContrast) { setContrast(want); lastContrast = want; }
```

`pinMode(5, INPUT);` — the external 10k pull-up is on the board.
The level can also be forced over CAN instead of using D5.

## 6. Bill of materials

| Ref | Value | Package | Side | Suggested part |
|---|---|---|---|---|
| J1 | 8-pin JST XH, right angle | S8B-XH-A | top | JST S8B-XH-A |
| J2 | 1×4 male header, right angle | 2.54 mm | top | generic |
| P1, P2 | 1×16 female socket | 2.54 mm | **bottom** | generic |
| F1 | PTC 0.5 A hold / 60 V | 1206 | top | Littelfuse 1206L050YR |
| D1 | Schottky 40 V / 3 A | SMA | top | SS34 |
| D2 | TVS 24 V unidirectional | SMB | top | SMBJ24A (pin 1 = band = cathode) |
| D3 | small-signal diode | SOD-123 | top | 1N4148W |
| U1 | opto-coupler | DIP-4 | top | PC817 / EL817 |
| RV1, RV2 | 10 kΩ trimmer | RM-065 / 3362P | top | Bourns 3362P-1-103LF |
| R1 | 3k3 | 0805 | top | — |
| R2 | 10k | 0805 | top | — |
| C1 | 10 µF / 50 V X7R | 1210 | top | — |
| C2 | 100 nF / 50 V X7R | 0805 | top | — |
| C3 | 100 nF X7R | 0805 | top | — |
| C4 | 10 µF X5R | 0805 | top | — |
| C5 | 1 µF X7R | 0805 | top | — |

Also needed: two 1×16 male pin headers on the CANduino itself (if not already fitted),
one 1×4 right-angle male header for the OLED module, and a 4-way female–female cable.

## 7. Assembly order

1. SMD parts on the top side (F1, D1, D2, D3, R1, R2, C1–C5).
2. U1 (DIP-4) and RV1/RV2 on the top side.
3. J1 and J2 on the top side.
4. **Last**: P1 and P2 — the two 1×16 female sockets go on the **bottom** side, soldered
   from the top. Plug them onto the CANduino first so they end up square.

The trimmers must stay reachable after installation — keep the top side accessible.

## 8. Files

| File | Contents |
|---|---|
| `canduino_oled_shield_V000.kicad_pro/.kicad_sch/.kicad_pcb` | KiCad 7 project |
| `canduino_oled_shield_gerbers_V000.zip` | Gerber X2 + Excellon drill (JLCPCB / PCBWay ready) |
| `schematic_V000.pdf` | schematic |
| `pcb_top_V000.pdf`, `pcb_bottom_V000.pdf` | copper + silkscreen |
| `pcb_assembly_V000.pdf` | assembly drawing (fab layer, all designators) |
| `bom_V000.csv` | bill of materials |

Order settings: 2 layers, 1.6 mm, HASL or ENIG, any colour, 1 oz copper. No controlled
impedance, no castellations, no special requirements.

## 9. Verified vs not verified

| Item | Status |
|---|---|
| Clearance/DRC of all copper (pad↔pad, pad↔track, track↔track, pour) | **verified** by geometric check, 0 violations |
| All 16 nets fully routed, each net a connected tree | **verified** by construction |
| Footprints, pad sizes, drill sizes | **verified** — from the official KiCad 7 libraries |
| Board loads and plots in KiCad 7 | **verified** — Gerbers and drill exported without error |
| Component courtyards do not overlap | **verified** |
| CANduino **v4** pinout (2×16, CAN-H/CAN-L on pin 16 of each row) | **verified** from `CANduino_v4_Sub_komp.png` in the MassiveButDynamic repo |
| CANduino **v4.5** pinout identical to v4 | **NOT verified** — massivebutdynamic.com is blocked from this environment, the v4.5 manual could not be read |
| Row-to-row spacing 15.24 mm (0.6", Nano-compatible) | **NOT verified** — inferred from the 18 mm board width and Nano compatibility |
| J2 pin order matches your specific OLED module | **NOT verified** — depends on the module |
| Mechanical fit in the car, cable routing | **NOT verified** |
| Firmware support for A0/A1/D5 | **not written yet** — the current sketch (V012) does not read them |

**Before ordering, please measure two things on your own CANduino:**
1. The centre-to-centre distance between the two pin rows (expected 15.24 mm).
2. Continuity from the last pin of each row to the CAN connector — i.e. that CAN-H and
   CAN-L really are on pin 16 of the left and right row.

If either differs, say so and I will adjust the board; it is a small change.
