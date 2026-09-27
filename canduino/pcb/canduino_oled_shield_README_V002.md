# CANduino OLED gear-display shield — V002

**Changes vs V001:** J2 is now a **JST XH 4-pin right-angle (S4B-XH-A)** instead of a plain
2.54 mm pin header — latched and keyed, so the OLED cable cannot vibrate loose or be
plugged in backwards. The XH housing needs 9.7 mm of board depth, so the board grew from
62 to **66 mm**; the trimmers and the opto moved down accordingly. Copper otherwise
unchanged, DRC still clean.

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

| Pin | Net | CANduino |
|---|---|---|
| 1 | GND | GND |
| 2 | +5V | +5V (left row pin 12) |
| 3 | SCL | A5 (left row pin 9) |
| 4 | SDA | A4 (left row pin 8) |

Use a ready-made 4-way female–female flat cable. Fit the **same right-angle 1×4 header
on the OLED module** so both cable ends run flat.

> **Check before you plug in:** J2 is wired GND / +5V / SCL / SDA. Not every 1.3" module
> uses that order — some are VCC / GND / SCL / SDA. Read the silkscreen on your own
> display first; swapping +5V and GND destroys the module.

## 3. CANduino pins used

| Row / pin | Signal | Used for |
|---|---|---|
| L4 | A0 | RV1 wiper — spare (not used by the default firmware) |
| L5 | A1 | RV2 wiper — dimmed brightness level |
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
≈3–4 mA). D3 protects the LED against reverse polarity. R2 (10k) pulls D5 up, C5 (1 µF)
filters PWM dimming.

| Lighting input | D5 | Display |
|---|---|---|
| 0 V (lights off) | HIGH (pull-up) | **full brightness**, contrast 255, fixed |
| ≥ 12 V (lights on) | LOW (opto conducts) | **dimmed**, contrast set by trimmer **RV2** on A1 |

RV1 on A0 is **not used** by the default firmware and is fitted as a spare. One line in
`updateBrightness()` turns it into an adjustable bright level if ever wanted.

Brightness itself is software: the SH1106 has no analogue brightness input, only the
contrast register (command `0x81`). Firmware `..._V013.ino` implements this:

```cpp
void setContrast(uint8_t v) {
  Wire.beginTransmission(SCREEN_ADDRESS);
  Wire.write(0x00);   // command stream
  Wire.write(0x81);   // set contrast
  Wire.write(v);
  Wire.endTransmission();
}
```

with a 300 ms debounce on D5, a 200 ms update interval and a 3-count dead band so ADC
noise cannot make the display flicker.

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
| RV1 | 10 kΩ trimmer — spare, on A0 | RM-065 / 3362P | top | Bourns 3362P-1-103LF |
| RV2 | 10 kΩ trimmer — dim level, on A1 | RM-065 / 3362P | top | Bourns 3362P-1-103LF |
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
| `canduino_oled_shield_V002.kicad_pro/.kicad_sch/.kicad_pcb` | KiCad 7 project |
| `canduino_oled_shield_gerbers_V002.zip` | Gerber X2 + Excellon drill (JLCPCB / PCBWay ready) |
| `schematic_V002.pdf` | schematic |
| `pcb_top_V002.pdf`, `pcb_bottom_V002.pdf` | copper + silkscreen |
| `pcb_assembly_V002.pdf` | assembly drawing (fab layer, all designators) |
| `bom_V002.csv` | bill of materials |
| `Geardisplay_..._V013.ino` + `kcp_fonts.h` | firmware with the brightness control |

Order settings: 2 layers, 1.6 mm, HASL or ENIG, any colour, 1 oz copper. No controlled
impedance, no castellations, no special requirements.

## 9. Verified vs not verified

| Item | Status |
|---|---|
| Clearance of all copper (pad↔pad, pad↔track, track↔track, pour) | **verified** by geometric check, 0 violations |
| All 16 nets fully routed, each net a connected tree | **verified** by construction |
| Footprints, pad sizes, drill sizes | **verified** — official KiCad 7 libraries |
| Board loads and plots in KiCad 7 | **verified** — Gerbers and drill exported without error |
| Component courtyards do not overlap | **verified** |
| CANduino **v4.5** pinout (2×16, CAN-H / CAN-L on pin 16 of each row) | **verified** — official v4.5 drawing, identical to v4 |
| Board size 43 × 18 mm, pitch 2.54 mm | **verified** — v4.5 drawing |
| Row-to-row spacing 15.24 mm | **NOT verified** — not dimensioned in the drawing; follows from "same pin arrangement as the Nano" |
| J2 pin order matches your specific OLED module | **NOT verified** — depends on the module |
| Firmware V013 compiles for AVR / fits in flash | **NOT verified** — no AVR toolchain here; syntax checked only |
| Brightness behaviour on the bench and in the car | **NOT verified** |
| MCP crystal: V013 ships with `MCP_8MHZ` | **matches the board that works today.** If the custom 16 MHz board goes in, change line 18 to `MCP_16MHZ` |
| Mechanical fit in the car, cable routing | **NOT verified** |

**Still worth measuring before ordering:** the centre-to-centre distance between the two
pin rows on your own CANduino. Expected 15.24 mm (0.6", Nano standard). Everything else
is now confirmed from the official v4.5 drawing.
