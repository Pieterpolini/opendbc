"""Design data for the CANduino OLED gear-display shield."""

# ---------------------------------------------------------------- board
BX0, BY0 = 100.0, 50.0
BW, BH = 28.0, 62.0
BX1, BY1 = BX0 + BW, BY0 + BH
CX = BX0 + BW / 2.0                      # 114.0

ROW_PITCH = 15.24                        # Nano-compatible row spacing
P1X = CX - ROW_PITCH / 2                 # 106.38  left row  (D13..CAN-H)
P2X = CX + ROW_PITCH / 2                 # 121.62  right row (D12..CAN-L)
PIN1Y = 59.0                             # y of socket pin 1
PP = 2.54

def p1(n):  return (P1X, PIN1Y + PP * (n - 1))
def p2(n):  return (P2X, PIN1Y + PP * (n - 1))

# CANduino v4 / v4.5 header mapping (2 x 16, from CANduino_v4_Sub_komp.png)
ROW_L = ["D13", "+3V3", "AREF", "A0", "A1", "A2", "A3", "A4",
         "A5", "A6", "A7", "+5V", "RESET", "GND", "VIN", "CAN_H"]
ROW_R = ["D12", "D11", "D10", "D9", "D8", "D7", "D6", "D5",
         "D4", "D3", "D2", "GND", "RESET", "D0_RX", "D1_TX", "CAN_L"]

# ---------------------------------------------------------------- parts
# ref: (lib_id, value, footprint, x, y, rot, layer, pin->net, sch_x, sch_y, desc)
NC = None

PARTS = {}

SILK_REF = {"J1", "J2"}
REF_OFF = {"J1": 11.5}

def add(ref, lib_id, value, fp, x, y, rot, layer, nets, sx, sy, desc="", exclude_bom=False):
    PARTS[ref] = dict(ref=ref, lib_id=lib_id, value=value, fp=fp, x=x, y=y, rot=rot,
                      layer=layer, nets=nets, sx=sx, sy=sy, desc=desc,
                      exclude_bom=exclude_bom, silk_ref=(ref in SILK_REF),
                      ref_off=REF_OFF.get(ref, -3.2))

# --- connectors -------------------------------------------------------
add("J1", "Connector_Generic:Conn_01x08", "Power/CAN/Light",
    "Connector_JST:JST_XH_S8B-XH-A_1x08_P2.50mm_Horizontal",
    122.75, 109.5, 180, "F.Cu",
    {1: "+12V_IN", 2: "GND", 3: "CAN_H", 4: "CAN_L",
     5: "LIGHT_IN", 6: "GND", 7: "SPARE_A2", 8: "SPARE_D6"},
    40, 40, "JST S8B-XH-A, right angle, 2.50 mm")

add("J2", "Connector_Generic:Conn_01x04", "OLED I2C",
    "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Horizontal",
    110.19, 55.0, 90, "F.Cu",
    {1: "GND", 2: "+5V", 3: "SCL", 4: "SDA"},
    40, 90, "1x4 male, right angle, 2.54 mm")

add("P1", "Connector_Generic:Conn_01x16", "CANduino left row",
    "Connector_PinSocket_2.54mm:PinSocket_1x16_P2.54mm_Vertical",
    P1X, PIN1Y, 0, "B.Cu",
    {4: "BRIGHT_DAY", 5: "BRIGHT_NIGHT", 6: "SPARE_A2", 8: "SDA", 9: "SCL",
     12: "+5V", 14: "GND", 15: "VIN", 16: "CAN_H"},
    130, 40, "1x16 female socket, bottom side")

add("P2", "Connector_Generic:Conn_01x16", "CANduino right row",
    "Connector_PinSocket_2.54mm:PinSocket_1x16_P2.54mm_Vertical",
    P2X, PIN1Y, 0, "B.Cu",
    {7: "SPARE_D6", 8: "LIGHT_D5", 12: "GND", 16: "CAN_L"},
    130, 100, "1x16 female socket, bottom side")

# --- 12 V input protection (right edge strip) -------------------------
add("F1", "Device:Polyfuse", "0.5A PTC", "Fuse:Fuse_1206_3216Metric",
    124.8, 97.0, 90, "F.Cu", {1: "+12V_IN", 2: "V_FUSED"}, 40, 155,
    "PTC resettable fuse, 1206, Ihold 0.5 A, 60 V")
add("D2", "Device:D_TVS", "SMBJ24A pin1=K", "Diode_SMD:D_SMB",
    124.8, 90.5, 90, "F.Cu", {1: "V_FUSED", 2: "GND"}, 65, 160,
    "Unidirectional TVS 24 V, SMB, pin 1 = cathode (band)")
add("D1", "Device:D_Schottky", "SS34", "Diode_SMD:D_SMA",
    124.8, 82.5, 270, "F.Cu", {1: "VIN", 2: "V_FUSED"}, 90, 155,
    "Schottky 40 V / 3 A, SMA, reverse-polarity series diode")
add("C1", "Device:C", "10uF/50V", "Capacitor_SMD:C_1210_3225Metric",
    124.8, 76.0, 90, "F.Cu", {1: "VIN", 2: "GND"}, 115, 160, "X7R 1210")
add("C2", "Device:C", "100nF/50V", "Capacitor_SMD:C_0805_2012Metric",
    124.8, 71.0, 90, "F.Cu", {1: "VIN", 2: "GND"}, 135, 160, "X7R 0805")

# --- 5 V decoupling ---------------------------------------------------
add("C3", "Device:C", "100nF", "Capacitor_SMD:C_0805_2012Metric",
    117.9, 88.0, 0, "F.Cu", {1: "+5V", 2: "GND"}, 155, 160, "X7R 0805")
add("C4", "Device:C", "10uF", "Capacitor_SMD:C_0805_2012Metric",
    117.9, 91.0, 0, "F.Cu", {1: "+5V", 2: "GND"}, 175, 160, "X5R 0805")

# --- brightness trimmers ---------------------------------------------
add("RV1", "Device:R_Potentiometer_Trim", "10k",
    "Potentiometer_THT:Potentiometer_Runtron_RM-065_Vertical",
    110.5, 62.5, 0, "F.Cu", {1: "+5V", 2: "BRIGHT_DAY", 3: "GND"}, 60, 100,
    "Trimmer RM-065 / 3362P, level 1 = day")
add("RV2", "Device:R_Potentiometer_Trim", "10k",
    "Potentiometer_THT:Potentiometer_Runtron_RM-065_Vertical",
    110.5, 71.5, 0, "F.Cu", {1: "+5V", 2: "BRIGHT_NIGHT", 3: "GND"}, 90, 100,
    "Trimmer RM-065 / 3362P, level 2 = night")

# --- lighting input opto-coupler --------------------------------------
add("R1", "Device:R", "3k3", "Resistor_SMD:R_0805_2012Metric",
    113.5, 88.0, 0, "F.Cu", {1: "LIGHT_IN", 2: "LIGHT_A"}, 60, 220,
    "LED series resistor, 0805, >=1/8 W")
add("D3", "Device:D", "1N4148W", "Diode_SMD:D_SOD-123",
    113.5, 91.0, 0, "F.Cu", {1: "LIGHT_A", 2: "GND"}, 80, 225,
    "Reverse protection across the opto LED, SOD-123")
add("U1", "Isolator:PC817", "PC817", "Package_DIP:DIP-4_W7.62mm",
    110.0, 82.0, 0, "F.Cu",
    {1: "LIGHT_A", 2: "GND", 3: "GND", 4: "LIGHT_D5"}, 110, 220,
    "Opto-coupler, DIP-4")
add("R2", "Device:R", "10k", "Resistor_SMD:R_0805_2012Metric",
    113.5, 94.0, 0, "F.Cu", {1: "+5V", 2: "LIGHT_D5"}, 145, 215,
    "Pull-up for D5, 0805")
add("C5", "Device:C", "1uF", "Capacitor_SMD:C_0805_2012Metric",
    117.9, 94.0, 0, "F.Cu", {1: "LIGHT_D5", 2: "GND"}, 165, 220,
    "Filters PWM dimming on the lighting feed, 0805")

# ---------------------------------------------------------------- nets
NETS = ["GND", "+5V", "VIN", "+12V_IN", "V_FUSED", "CAN_H", "CAN_L",
        "SCL", "SDA", "BRIGHT_DAY", "BRIGHT_NIGHT", "LIGHT_IN", "LIGHT_A",
        "LIGHT_D5", "SPARE_A2", "SPARE_D6"]

GND_NET = "GND"

# ---------------------------------------------------------------- rules
TRACE_W = 0.4
POWER_W = 0.6
CLEAR = 0.25
VIA_D, VIA_DRILL = 0.8, 0.4
EDGE_KEEPOUT = 0.35
