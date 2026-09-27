import os, sys, math, uuid, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp
from sexp import Str
import design as D

random.seed(11)
SYMDIR = "/usr/share/kicad/symbols"
PROJECT = "canduino_oled_shield_V002"
TITLE = "CANduino OLED gear display shield"
REV = "V002"
ROOT = str(uuid.UUID(int=random.getrandbits(128), version=4))

def uid():
    return str(uuid.UUID(int=random.getrandbits(128), version=4))

def n(v):
    return sexp.fmt(round(float(v), 4))

# ------------------------------------------------- schematic placement
SCH = {
    "J1":  (50, 60),   "J2":  (50, 120),
    "F1":  (118, 50),  "D2":  (143, 57),  "D1":  (170, 50),
    "C1":  (192, 57),  "C2":  (212, 57),
    "C3":  (252, 57),  "C4":  (272, 57),
    "RV1": (110, 115), "RV2": (150, 115),
    "R1":  (100, 190), "D3":  (124, 197), "U1":  (155, 190),
    "R2":  (196, 183), "C5":  (216, 190),
    "P1":  (330, 85),  "P2":  (330, 185),
}
for r, (x, y) in SCH.items():
    D.PARTS[r]["sx"], D.PARTS[r]["sy"] = x, y

SECTIONS = [
    (30, 22, "VEHICLE HARNESS  /  OLED CABLE", 2.5),
    (112, 22, "12 V INPUT PROTECTION  ->  CANduino VIN", 2.5),
    (245, 22, "5 V DECOUPLING", 2.5),
    (95, 100, "OLED BRIGHTNESS TRIMMERS (read on A0 / A1)", 2.5),
    (95, 168, "DASHBOARD LIGHTING INPUT 14.8 V  ->  D5", 2.5),
    (305, 22, "CANduino v4 / v4.5  2 x 16 PIN HEADER", 2.5),
]
NOTES = [
    (40, 250, "J1 pin 1 = +12 V switched.  F1/D1/D2 protect against reverse polarity, overload and load dump."),
    (40, 255, "J2 order GND / +5 V / SCL / SDA - CHECK the silkscreen of your own OLED module before plugging it in."),
    (40, 260, "CAN termination is on the CANduino itself (CAN_T jumper); there is none on this board."),
    (40, 265, "R1/U1/D3: the lighting feed may be PWM dimmed; C5 + R2 turn it into a clean level on D5."),
    (40, 270, "P1/P2 are 1x16 female sockets on the BOTTOM side of the board."),
]

# ------------------------------------------------- symbol library
def load_symbol(lib_id):
    lib, name = lib_id.split(":")
    root = sexp.parse(open(os.path.join(SYMDIR, lib + ".kicad_sym")).read())
    for s in sexp.findall(root, "symbol"):
        if str(s[1]) == name:
            sym = copy.deepcopy(s)
            sym[1] = Str(lib_id)
            return sym
    raise KeyError(lib_id)

libsyms = {}
for ref, part in D.PARTS.items():
    if part["lib_id"] not in libsyms:
        libsyms[part["lib_id"]] = load_symbol(part["lib_id"])

def sym_pins(lib_id):
    """[(number, x, y, angle)] in symbol coordinates."""
    out = []
    for sub in sexp.findall(libsyms[lib_id], "symbol"):
        for p in sexp.findall(sub, "pin"):
            at = sexp.find(p, "at")
            num = str(sexp.find(p, "number")[1])
            out.append((num, float(at[1]), float(at[2]), float(at[3])))
    return out

# ------------------------------------------------- emit
out = []
out.append('(kicad_sch (version 20230121) (generator eeschema)')
out.append('  (uuid "%s")' % ROOT)
out.append('  (paper "A3")')
out.append('  (title_block (title "%s") (rev "%s")' % (TITLE, REV))
out.append('    (comment 1 "Plug-on carrier PCB for CANduino v4/v4.5 + 1.3 inch SH1106 OLED")')
out.append('    (comment 2 "Gear / temperature display, MaxxECU CAN package 0x700")')
out.append('  )')
out.append('  (lib_symbols')
for lib_id in sorted(libsyms):
    out.append("    " + sexp.dumps(libsyms[lib_id]))
out.append('  )')

STUB = 5.08

def wire(x1, y1, x2, y2):
    out.append('  (wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
               % (n(x1), n(y1), n(x2), n(y2), uid()))

def label(t, x, y, ang, just):
    out.append('  (label "%s" (at %s %s %s) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s"))'
               % (t, n(x), n(y), n(ang), just, uid()))

def text(t, x, y, size=1.27, bold=False):
    out.append('  (text "%s" (at %s %s 0) (effects (font (size %s %s)%s) (justify left bottom)) (uuid "%s"))'
               % (t, n(x), n(y), n(size), n(size), " bold" if bold else "", uid()))

for (x, y, t, s) in SECTIONS:
    text(t, x, y, s, bold=True)
for (x, y, t) in NOTES:
    text(t, x, y, 1.6)

nolabel = set()
for ref in SCH:
    part = D.PARTS[ref]
    sx, sy = part["sx"], part["sy"]
    lib_id = part["lib_id"]
    pins = sym_pins(lib_id)
    # ---- symbol instance
    out.append('  (symbol (lib_id "%s") (at %s %s 0) (unit 1)' % (lib_id, n(sx), n(sy)))
    out.append('    (in_bom yes) (on_board yes) (dnp no)')
    out.append('    (uuid "%s")' % uid())
    ys = [sy - p[2] for p in pins]
    top, bot = min(ys), max(ys)
    out.append('    (property "Reference" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left)))'
               % (ref, n(sx + 1.27), n(top - 4.5)))
    out.append('    (property "Value" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left)))'
               % (part["value"], n(sx + 1.27), n(top - 2.4)))
    out.append('    (property "Footprint" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) hide))'
               % (part["fp"], n(sx), n(sy)))
    out.append('    (property "Datasheet" "~" (at %s %s 0) (effects (font (size 1.27 1.27)) hide))'
               % (n(sx), n(sy)))
    if part["desc"]:
        out.append('    (property "Description" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) hide))'
                   % (part["desc"], n(sx), n(sy)))
    for (num, px, py, a) in pins:
        out.append('    (pin "%s" (uuid "%s"))' % (num, uid()))
    out.append('    (instances (project "%s" (path "/%s" (reference "%s") (unit 1))))'
               % (PROJECT, ROOT, ref))
    out.append('  )')
    # ---- stubs + labels
    for (num, px, py, a) in pins:
        net = part["nets"].get(int(num)) if num.isdigit() else None
        gx, gy = sx + px, sy - py
        ox, oy = -math.cos(math.radians(a)), math.sin(math.radians(a))
        ex, ey = gx + ox * STUB, gy + oy * STUB
        if not net:
            out.append('  (no_connect (at %s %s) (uuid "%s"))' % (n(gx), n(gy), uid()))
            continue
        wire(gx, gy, ex, ey)
        if abs(ox) > 0.5:
            ang, just = (0, "left bottom") if ox > 0 else (180, "right bottom")
        else:
            ang, just = (90, "left bottom") if oy < 0 else (270, "right bottom")
        label(net, ex, ey, ang, just)

out.append('  (sheet_instances (path "/" (page "1")))')
out.append(')')
open(PROJECT + ".kicad_sch", "w").write("\n".join(out) + "\n")
print("wrote %s.kicad_sch" % PROJECT)

# ------------------------------------------------- project file
pro = '''{
  "board": {"design_settings": {"defaults": {"board_outline_line_width": 0.1,
    "copper_line_width": 0.4, "silk_line_width": 0.15, "silk_text_size_h": 1.0,
    "silk_text_size_v": 1.0, "silk_text_thickness": 0.15},
    "rules": {"min_clearance": 0.2, "min_track_width": 0.25, "min_via_diameter": 0.6,
              "min_through_hole_diameter": 0.3, "min_hole_to_hole": 0.25}},
    "layer_presets": [], "viewports": []},
  "boards": [],
  "cvpcb": {"equivalence_files": []},
  "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
  "meta": {"filename": "%s.kicad_pro", "version": 1},
  "net_settings": {"classes": [{"bus_width": 12, "clearance": 0.25, "diff_pair_gap": 0.25,
      "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3,
      "microvia_drill": 0.1, "name": "Default", "pcb_color": "rgba(0, 0, 0, 0.000)",
      "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.4, "via_diameter": 0.8,
      "via_drill": 0.4, "wire_width": 6}], "meta": {"version": 3}, "net_colors": null},
  "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "specctra_dsn": "",
      "step": "", "vrml": ""}, "page_layout_descr_file": ""},
  "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
  "sheets": [["%s", ""]],
  "text_variables": {}
}
''' % (PROJECT, ROOT)
open(PROJECT + ".kicad_pro", "w").write(pro)
print("wrote %s.kicad_pro" % PROJECT)
