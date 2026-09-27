import math, heapq, os, sys, uuid, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp
from sexp import Str
import design as D

FPDIR = "/usr/share/kicad/footprints"
NETNUM = {"": 0}
for _i, _n in enumerate(D.NETS):
    NETNUM[_n] = _i + 1
random.seed(7)

def uid():
    return Str(str(uuid.UUID(int=random.getrandbits(128), version=4)))

# ------------------------------------------------------------ transforms
def rot_pt(x, y, a):
    r = math.radians(a)
    c, s = math.cos(r), math.sin(r)
    return (x * c + y * s, -x * s + y * c)

def flip_layer(l):
    if l.startswith("F."):
        return "B." + l[2:]
    if l.startswith("B."):
        return "F." + l[2:]
    return l

# ------------------------------------------------------------ footprints
class Pad:
    __slots__ = ("ref", "num", "net", "x", "y", "w", "h", "rot", "layers", "drill", "thru")
    def __init__(s, **kw):
        for k, v in kw.items():
            setattr(s, k, v)
    def rect(s):
        """Axis-aligned bounding box (pads here are at 0/90 deg only)."""
        if abs((s.rot % 180)) < 1e-6:
            w, h = s.w, s.h
        else:
            w, h = s.h, s.w
        return (s.x - w / 2, s.y - h / 2, s.x + w / 2, s.y + h / 2)

def load_fp(path):
    return sexp.parse(open(path).read())

def place(part):
    """Return (fp_node, pads) with everything transformed into board coords."""
    lib, name = part["fp"].split(":")
    node = load_fp(os.path.join(FPDIR, lib + ".pretty", name + ".kicad_mod"))
    back = part["layer"] == "B.Cu"
    rot = part["rot"]
    fx, fy = part["x"], part["y"]
    pads = []

    def mirror_xy(n):
        """Mirror local X in place (for back-side footprints)."""
        for item in n:
            if isinstance(item, list) and item:
                k = item[0]
                if k in ("at", "start", "end", "center", "mid", "xy"):
                    item[1] = sexp.fmt(-float(item[1]))
                    if k == "at" and len(item) > 3:
                        item[3] = sexp.fmt(-float(item[3]) % 360)
                elif k == "layer":
                    item[1] = Str(flip_layer(str(item[1])))
                elif k == "layers":
                    for i in range(1, len(item)):
                        item[i] = Str(flip_layer(str(item[i])))
                elif k == "pts":
                    mirror_xy(item)
                else:
                    mirror_xy(item)

    if back:
        for item in node:
            if isinstance(item, list):
                mirror_xy([item])

    # strip tstamps / models, set layer + position
    out = ["footprint", Str(part["fp"])]
    out.append(["layer", Str(part["layer"] if back else "F.Cu")])
    out.append(["uuid", uid()] if False else ["tstamp", uid()])
    out.append(["at", sexp.fmt(fx), sexp.fmt(fy)] + ([sexp.fmt(rot)] if rot else []))
    if part["desc"]:
        out.append(["descr", Str(part["desc"])])
    out.append(["attr", "through_hole"] if False else None)
    out = [o for o in out if o is not None]

    # properties
    def prop(name, value, y_off, layer, hide=False):
        e = ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]
        if hide:
            e.append("hide")
        return ["fp_text", name, Str(value), ["at", "0", sexp.fmt(y_off), sexp.fmt(-rot % 360)],
                ["layer", Str(layer)], ["tstamp", uid()], e]

    silk = "B.SilkS" if back else "F.SilkS"
    fab = "B.Fab" if back else "F.Fab"
    reflayer = silk if part.get("silk_ref", True) else fab
    out.append(prop("reference", part["ref"], part.get("ref_off", -3.2), reflayer))
    out.append(prop("value", part["value"], 3.2, fab, hide=True))

    for item in node[2:]:
        if not isinstance(item, list):
            continue
        k = item[0]
        if k in ("tedit", "tstamp", "at", "descr", "tags", "attr", "model", "layer"):
            continue
        if k == "fp_text" and item[1] in ("reference", "value"):
            continue
        if k == "property":
            continue
        out.append(item)
        if k == "pad":
            num = str(item[1])
            at = sexp.find(item, "at")
            px, py = float(at[1]), float(at[2])
            prot = float(at[3]) if len(at) > 3 else 0.0
            size = sexp.find(item, "size")
            pw, ph = float(size[1]), float(size[2])
            dr = sexp.find(item, "drill")
            drill = float(dr[1]) if dr else None
            lays = [str(x) for x in sexp.find(item, "layers")[1:]]
            gx, gy = rot_pt(px, py, rot)
            gx, gy = gx + fx, gy + fy
            net = part["nets"].get(int(num)) if num.isdigit() else None
            thru = str(item[2]) == "thru_hole"
            pl = ["F.Cu", "B.Cu"] if thru else [l for l in lays if l.endswith(".Cu")]
            p = Pad(ref=part["ref"], num=num, net=net, x=gx, y=gy, w=pw, h=ph,
                    rot=(prot + rot) % 180, layers=pl, drill=drill, thru=thru)
            pads.append(p)
            if net:
                item.append(["net", str(NETNUM[net]), Str(net)])
            item.append(["tstamp", uid()])
    return out, pads

# ------------------------------------------------------------ build parts
footprints = []
allpads = []
for ref in ["P1", "P2", "J1", "J2", "F1", "D1", "D2", "C1", "C2",
            "C3", "C4", "RV1", "RV2", "R1", "D3", "U1", "R2", "C5"]:
    part = D.PARTS[ref]
    fp, pads = place(part)
    footprints.append((ref, fp))
    allpads.extend(pads)

# sanity: no two pads of different refs overlapping
def overlap(a, b, gap=0.0):
    ax0, ay0, ax1, ay1 = a.rect(); bx0, by0, bx1, by1 = b.rect()
    return not (ax1 + gap <= bx0 or bx1 + gap <= ax0 or ay1 + gap <= by0 or by1 + gap <= ay0)

problems = []
for i in range(len(allpads)):
    for j in range(i + 1, len(allpads)):
        a, b = allpads[i], allpads[j]
        if a.ref == b.ref:
            continue
        if not (set(a.layers) & set(b.layers)):
            continue
        if overlap(a, b, D.CLEAR):
            problems.append((a.ref, a.num, b.ref, b.num,
                             round(a.x, 2), round(a.y, 2), round(b.x, 2), round(b.y, 2)))
if problems:
    print("PAD CLEARANCE PROBLEMS:")
    for p in problems:
        print("  ", p)
else:
    print("pad clearance: OK  (%d pads)" % len(allpads))

# board extents check
for p in allpads:
    x0, y0, x1, y1 = p.rect()
    if x0 < D.BX0 + 0.3 or x1 > D.BX1 - 0.3 or y0 < D.BY0 + 0.3 or y1 > D.BY1 - 0.3:
        print("  PAD OUTSIDE BOARD:", p.ref, p.num, round(p.x, 2), round(p.y, 2))

# courtyard collision (component bodies, top side only)
def crtyd(part):
    lib, name = part["fp"].split(":")
    node = load_fp(os.path.join(FPDIR, lib + ".pretty", name + ".kicad_mod"))
    xs, ys = [], []
    for it in node:
        if isinstance(it, list) and it[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle"):
            lay = sexp.find(it, "layer")
            if not lay or "CrtYd" not in str(lay[1]):
                continue
            for key in ("start", "end", "center"):
                e = sexp.find(it, key)
                if e:
                    xs.append(float(e[1])); ys.append(float(e[2]))
    if not xs:
        return None
    pts = [(x, y) for x in (min(xs), max(xs)) for y in (min(ys), max(ys))]
    g = [rot_pt(x, y, part["rot"]) for x, y in pts]
    return (min(p[0] for p in g) + part["x"], min(p[1] for p in g) + part["y"],
            max(p[0] for p in g) + part["x"], max(p[1] for p in g) + part["y"])

tops = [r for r in D.PARTS if D.PARTS[r]["layer"] == "F.Cu"]
boxes = {r: crtyd(D.PARTS[r]) for r in tops}
for i, a in enumerate(tops):
    for b in tops[i + 1:]:
        A, B = boxes[a], boxes[b]
        if A and B and not (A[2] <= B[0] or B[2] <= A[0] or A[3] <= B[1] or B[3] <= A[1]):
            print("  COURTYARD OVERLAP: %s %s  %s %s" %
                  (a, [round(v, 2) for v in A], b, [round(v, 2) for v in B]))
print("courtyards checked")
for r in tops:
    A = boxes[r]
    if A:
        print("   %-4s %6.2f %6.2f  %6.2f %6.2f" % (r, A[0], A[1], A[2], A[3]))

# ====================================================================
#                          MAZE  ROUTER
# ====================================================================
STEP = 0.2
NX = int(round(D.BW / STEP))
NY = int(round(D.BH / STEP))
LAYERS = ["F.Cu", "B.Cu"]
VIA_COST = 160          # in grid units (0.2 mm)
LAYER_COST = [1.0, 1.0]

def cx(i): return D.BX0 + (i + 0.5) * STEP
def cy(j): return D.BY0 + (j + 0.5) * STEP
def ci(x): return int((x - D.BX0) / STEP)
def cj(y): return int((y - D.BY0) / STEP)

HARD = "#"
occ = [[[None] * NX for _ in range(NY)] for _ in LAYERS]

def mark_rect(l, x0, y0, x1, y1, owner):
    i0, i1 = max(0, ci(x0)), min(NX - 1, ci(x1) + 1)
    j0, j1 = max(0, cj(y0)), min(NY - 1, cj(y1) + 1)
    for j in range(j0, j1 + 1):
        yy = cy(j)
        if yy < y0 or yy > y1:
            continue
        row = occ[l][j]
        for i in range(i0, i1 + 1):
            xx = cx(i)
            if xx < x0 or xx > x1:
                continue
            cur = row[i]
            if cur is None:
                row[i] = owner
            elif cur != owner:
                row[i] = HARD

def mark_disc(l, x, y, r, owner):
    i0, i1 = max(0, ci(x - r)), min(NX - 1, ci(x + r) + 1)
    j0, j1 = max(0, cj(y - r)), min(NY - 1, cj(y + r) + 1)
    for j in range(j0, j1 + 1):
        row = occ[l][j]
        dy = cy(j) - y
        for i in range(i0, i1 + 1):
            if (cx(i) - x) ** 2 + dy ** 2 <= r * r:
                cur = row[i]
                if cur is None:
                    row[i] = owner
                elif cur != owner:
                    row[i] = HARD

EXP = D.CLEAR + D.POWER_W / 2          # 0.55  (worst-case trace half-width)

# board edge keep-out
edge = D.EDGE_KEEPOUT + D.POWER_W / 2
for l in range(2):
    for j in range(NY):
        y = cy(j)
        for i in range(NX):
            x = cx(i)
            if (x < D.BX0 + edge or x > D.BX1 - edge or
                    y < D.BY0 + edge or y > D.BY1 - edge):
                occ[l][j][i] = HARD

for p in allpads:
    x0, y0, x1, y1 = p.rect()
    owner = p.net if p.net else HARD
    for lname in p.layers:
        l = LAYERS.index(lname)
        mark_rect(l, x0 - EXP, y0 - EXP, x1 + EXP, y1 + EXP, owner)

tracks = []      # (x1,y1,x2,y2,layer,width,net)
vias = []        # (x,y,net)

def add_track(x1, y1, x2, y2, l, net, w=None):
    w = w or D.TRACE_W
    tracks.append((x1, y1, x2, y2, LAYERS[l], w, net))

CLAIM_R = D.POWER_W / 2 + D.CLEAR + D.POWER_W / 2      # 0.85
VIA_CLAIM_R = D.VIA_D / 2 + D.CLEAR + D.POWER_W / 2    # 0.95
VIA_OK_R = 0.21                                        # extra room a via needs

def claim_path(cells, net):
    for (i, j, l) in cells:
        mark_disc(l, cx(i), cy(j), CLAIM_R, net)

def claim_via(x, y, net):
    for l in range(2):
        mark_disc(l, x, y, VIA_CLAIM_R, net)

def via_ok(i, j, net):
    n = int(VIA_OK_R / STEP)
    for dj in range(-n, n + 1):
        for di in range(-n, n + 1):
            if di * di + dj * dj > n * n + 0.5:
                continue
            for l in range(2):
                if not passable(i + di, j + dj, l, net):
                    return False
    return True

def pad_cells(p):
    out = []
    x0, y0, x1, y1 = p.rect()
    for lname in p.layers:
        l = LAYERS.index(lname)
        for j in range(max(0, cj(y0)), min(NY - 1, cj(y1) + 1) + 1):
            if not (y0 <= cy(j) <= y1):
                continue
            for i in range(max(0, ci(x0)), min(NX - 1, ci(x1) + 1) + 1):
                if x0 <= cx(i) <= x1:
                    out.append((i, j, l))
    return out

DIRS = [(1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10),
        (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14)]

def passable(i, j, l, net):
    if not (0 <= i < NX and 0 <= j < NY):
        return False
    v = occ[l][j][i]
    return v is None or v == net

def astar(sources, targets, net):
    tset = set(targets)
    if not tset:
        return None
    tx = sum(cx(t[0]) for t in targets) / len(targets)
    ty = sum(cy(t[1]) for t in targets) / len(targets)

    def h(i, j):
        return int(10 * math.hypot(cx(i) - tx, cy(j) - ty) / STEP * 0.9)

    openh = []
    came = {}
    g = {}
    for s in sources:
        if passable(*s, net):
            g[s] = 0
            heapq.heappush(openh, (h(s[0], s[1]), 0, s))
    while openh:
        f, gc, cur = heapq.heappop(openh)
        if gc > g.get(cur, 1 << 30):
            continue
        if cur in tset:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1]
        i, j, l = cur
        for di, dj, c in DIRS:
            ni, nj = i + di, j + dj
            if not passable(ni, nj, l, net):
                continue
            if di and dj:
                if not (passable(i + di, j, l, net) and passable(i, j + dj, l, net)):
                    continue
            ng = gc + int(c * LAYER_COST[l])
            nxt = (ni, nj, l)
            if ng < g.get(nxt, 1 << 30):
                g[nxt] = ng
                came[nxt] = cur
                heapq.heappush(openh, (ng + h(ni, nj), ng, nxt))
        ol = 1 - l
        if passable(i, j, ol, net) and via_ok(i, j, net):
            ng = gc + VIA_COST
            nxt = (i, j, ol)
            if ng < g.get(nxt, 1 << 30):
                g[nxt] = ng
                came[nxt] = cur
                heapq.heappush(openh, (ng + h(i, j), ng, nxt))
    return None

def emit_path(path, net, width):
    """Turn a cell path into board segments + vias, straighten, then claim."""
    claimed = []
    run = [path[0]]
    for k in range(1, len(path)):
        a, b = path[k - 1], path[k]
        if a[2] != b[2]:
            claimed += flush(run, net, width)
            vias.append((cx(a[0]), cy(a[1]), net))
            claim_via(cx(a[0]), cy(a[1]), net)
            run = [b]
        else:
            run.append(b)
    claimed += flush(run, net, width)
    return claimed

def line_clear(a, b, l, net):
    di = (b[0] > a[0]) - (b[0] < a[0])
    dj = (b[1] > a[1]) - (b[1] < a[1])
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    i, j = a[0], a[1]
    for _ in range(n):
        ni, nj = i + di, j + dj
        if not passable(ni, nj, l, net):
            return False
        if di and dj and not (passable(i + di, j, l, net) and passable(i, j + dj, l, net)):
            return False
        i, j = ni, nj
    return True


def sgn(v):
    return (v > 0) - (v < 0)


def two_seg(a, b):
    """Candidate 1- or 2-segment 45-degree connections between a and b."""
    di, dj = b[0] - a[0], b[1] - a[1]
    if di == 0 or dj == 0 or abs(di) == abs(dj):
        return [[a, b]]
    out = []
    if abs(di) > abs(dj):
        d = abs(di) - abs(dj)
        out.append([a, (a[0] + sgn(di) * d, a[1], a[2]), b])
        out.append([a, (b[0] - sgn(di) * d, b[1], b[2]), b])
    else:
        d = abs(dj) - abs(di)
        out.append([a, (a[0], a[1] + sgn(dj) * d, a[2]), b])
        out.append([a, (b[0], b[1] - sgn(dj) * d, b[2]), b])
    return out


def straighten(seg, net):
    l = seg[0][2]
    pts = [seg[0]]
    k = 0
    while k < len(seg) - 1:
        best, bestpts = None, None
        for m in range(len(seg) - 1, k, -1):
            for cand in two_seg(seg[k], seg[m]):
                if all(line_clear(cand[t], cand[t + 1], l, net)
                       for t in range(len(cand) - 1)):
                    best, bestpts = m, cand
                    break
            if best is not None:
                break
        if best is None:
            best, bestpts = k + 1, [seg[k], seg[k + 1]]
        pts.extend(bestpts[1:])
        k = best
    return pts


def flush(run, net, width):
    if len(run) < 2:
        return list(run)
    l = run[0][2]
    pts = [run[0]]
    for k in range(1, len(run) - 1):
        d1 = (run[k][0] - run[k - 1][0], run[k][1] - run[k - 1][1])
        d2 = (run[k + 1][0] - run[k][0], run[k + 1][1] - run[k][1])
        if d1 != d2:
            pts.append(run[k])
    pts.append(run[-1])
    pts = straighten(pts, net)
    cells = []
    for k in range(1, len(pts)):
        a, b = pts[k - 1], pts[k]
        add_track(cx(a[0]), cy(a[1]), cx(b[0]), cy(b[1]), l, net, width)
        di, dj = sgn(b[0] - a[0]), sgn(b[1] - a[1])
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        for t in range(n + 1):
            cells.append((a[0] + di * t, a[1] + dj * t, l))
    claim_path(cells, net)
    return cells

ROUTE_ORDER = ["CAN_H", "CAN_L", "VIN", "V_FUSED", "+12V_IN", "SPARE_A2",
               "SPARE_D6", "LIGHT_IN", "LIGHT_A", "LIGHT_D5", "SCL", "SDA",
               "BRIGHT_DAY", "BRIGHT_NIGHT", "+5V", "GND"]
POWER_NETS = {"VIN", "V_FUSED", "+12V_IN", "+5V", "GND"}

bynet = {}
for p in allpads:
    if p.net:
        bynet.setdefault(p.net, []).append(p)

fails = []
for net in ROUTE_ORDER:
    pads = bynet.get(net, [])
    if len(pads) < 2:
        continue
    width = D.POWER_W if net in POWER_NETS else D.TRACE_W
    LAYER_COST[0], LAYER_COST[1] = ((1.6, 1.0) if net == D.GND_NET else (1.0, 1.45))
    connected = list(pad_cells(pads[0]))
    todo = pads[1:]
    while todo:
        todo.sort(key=lambda p: min(math.hypot(cx(c[0]) - p.x, cy(c[1]) - p.y)
                                    for c in connected))
        nxtpad = todo.pop(0)
        tgt = pad_cells(nxtpad)
        path = astar(connected, tgt, net)
        if path is None:
            fails.append((net, nxtpad.ref, nxtpad.num))
            connected.extend(tgt)
            continue
        connected.extend(emit_path(path, net, width))
        connected.extend(tgt)

print("\nrouting: %d tracks, %d vias" % (len(tracks), len(vias)))
if fails:
    print("ROUTING FAILURES:", fails)
else:
    print("all signal nets routed")

# ====================================================================
#                    GND POUR  (B.Cu)  +  DRC  +  OUTPUT
# ====================================================================
from shapely.geometry import box, Point, LineString, Polygon, MultiPolygon
from shapely.ops import unary_union

ZC = 0.3            # zone clearance to other nets
TH_GAP = 0.4        # thermal relief gap
TH_SPOKE = 0.6      # thermal spoke width

def pad_box(p, grow=0.0):
    x0, y0, x1, y1 = p.rect()
    return box(x0 - grow, y0 - grow, x1 + grow, y1 + grow)

board_poly = box(D.BX0, D.BY0, D.BX1, D.BY1).buffer(-0.35, join_style=2)

obst = []
for p in allpads:
    if "B.Cu" not in p.layers:
        continue
    if p.net == D.GND_NET:
        outer = pad_box(p, TH_GAP)
        ox0, oy0, ox1, oy1 = outer.bounds
        spokes = unary_union([
            box(p.x - TH_SPOKE / 2, oy0 - 1, p.x + TH_SPOKE / 2, oy1 + 1),
            box(ox0 - 1, p.y - TH_SPOKE / 2, ox1 + 1, p.y + TH_SPOKE / 2)])
        obst.append(outer.difference(spokes))
    else:
        obst.append(pad_box(p, ZC))
for p in allpads:
    if p.drill and p.net != D.GND_NET:
        obst.append(Point(p.x, p.y).buffer(p.drill / 2 + ZC))
for (x1, y1, x2, y2, lay, w, net) in tracks:
    if lay == "B.Cu" and net != D.GND_NET:
        obst.append(LineString([(x1, y1), (x2, y2)]).buffer(w / 2 + ZC, cap_style=1))
for (x, y, net) in vias:
    if net != D.GND_NET:
        obst.append(Point(x, y).buffer(D.VIA_D / 2 + ZC))

pour = board_poly.difference(unary_union(obst))
pieces = list(pour.geoms) if isinstance(pour, MultiPolygon) else [pour]

# keep only islands that actually touch GND copper
gnd_anchor = []
for p in allpads:
    if p.net == D.GND_NET and "B.Cu" in p.layers:
        gnd_anchor.append(pad_box(p, 0.05))
for (x, y, net) in vias:
    if net == D.GND_NET:
        gnd_anchor.append(Point(x, y).buffer(D.VIA_D / 2))
for (x1, y1, x2, y2, lay, w, net) in tracks:
    if lay == "B.Cu" and net == D.GND_NET:
        gnd_anchor.append(LineString([(x1, y1), (x2, y2)]).buffer(w / 2, cap_style=1))
anchors = unary_union(gnd_anchor)
kept = [pc for pc in pieces if pc.area > 1.0 and pc.intersects(anchors)]
dropped = [pc for pc in pieces if pc not in kept]
print("pour: %d islands kept (%.1f mm2), %d dropped"
      % (len(kept), sum(p.area for p in kept), len(pieces) - len(kept)))

from shapely.ops import nearest_points

def defracture(poly):
    """Turn a polygon with holes into one ring by cutting the shortest slits."""
    guard = 0
    while poly.interiors and guard < 200:
        guard += 1
        ring = Polygon(poly.interiors[0])
        a, b = nearest_points(ring.exterior, poly.exterior)
        dx, dy = b.x - a.x, b.y - a.y
        L = math.hypot(dx, dy) or 1.0
        ax, ay = a.x - dx / L * 0.05, a.y - dy / L * 0.05
        bx, by = b.x + dx / L * 0.05, b.y + dy / L * 0.05
        cut = LineString([(ax, ay), (bx, by)]).buffer(0.0015, cap_style=1)
        new = poly.difference(cut)
        if isinstance(new, MultiPolygon):
            new = max(new.geoms, key=lambda g: g.area)
        if len(new.interiors) >= len(poly.interiors):
            break
        poly = new
    return poly

fills = [defracture(pc.simplify(0.002)) for pc in kept]

# ------------------------------------------------------------- DRC
def copper_shapes(layer):
    out = []
    for p in allpads:
        if layer in p.layers:
            out.append((p.net, pad_box(p), "%s.%s" % (p.ref, p.num)))
    for (x1, y1, x2, y2, lay, w, net) in tracks:
        if lay == layer:
            out.append((net, LineString([(x1, y1), (x2, y2)]).buffer(w / 2, cap_style=1),
                        "track"))
    for (x, y, net) in vias:
        out.append((net, Point(x, y).buffer(D.VIA_D / 2), "via"))
    if layer == "B.Cu":
        for f in fills:
            out.append((D.GND_NET, f, "pour"))
    return out

viol = 0
for layer in ("F.Cu", "B.Cu"):
    sh = copper_shapes(layer)
    for a in range(len(sh)):
        for b in range(a + 1, len(sh)):
            na, ga, la = sh[a]
            nb, gb, lb = sh[b]
            if na == nb and na is not None:
                continue
            d = ga.distance(gb)
            if d < D.CLEAR - 1e-6:
                viol += 1
                if viol < 25:
                    print("  DRC %s: %s(%s) <-> %s(%s)  %.3f mm"
                          % (layer, la, na, lb, nb, d))
print("DRC clearance violations:", viol)

# hole-to-hole / hole-to-copper
for i, p in enumerate(allpads):
    if not p.drill:
        continue
    for q in allpads[i + 1:]:
        if not q.drill:
            continue
        d = math.hypot(p.x - q.x, p.y - q.y) - p.drill / 2 - q.drill / 2
        if d < 0.3:
            print("  HOLE-HOLE %s.%s %s.%s %.3f" % (p.ref, p.num, q.ref, q.num, d))

# net connectivity sanity: every pad of a net must be reachable
print("nets:", len(D.NETS), " pads with net:", sum(1 for p in allpads if p.net))

# ====================================================================
#                        WRITE  .kicad_pcb
# ====================================================================
PROJECT = "canduino_oled_shield_V001"
TITLE = "CANduino OLED gear display shield"
REV = "V001"

LAYER_DEFS = """  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )"""

def n(v):
    return sexp.fmt(round(float(v), 4))

out = []
out.append('(kicad_pcb (version 20221018) (generator pcbnew)')
out.append('  (general (thickness 1.6))')
out.append('  (paper "A4")')
out.append('  (title_block (title "%s") (rev "%s") (company "")' % (TITLE, REV))
out.append('    (comment 1 "Plug-on carrier for CANduino v4/v4.5 + 1.3in SH1106 OLED")')
out.append('    (comment 2 "2 layer, 1.6 mm, 28 x 62 mm")')
out.append('  )')
out.append(LAYER_DEFS)
out.append('''  (setup
    (pad_to_mask_clearance 0.05)
    (allow_soldermask_bridges_in_footprints no)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros false) (usegerberextensions false) (usegerberattributes true)
      (usegerberadvancedattributes true) (creategerberjobfile true)
      (dashed_line_dash_ratio 12.000000) (dashed_line_gap_ratio 3.000000)
      (svgprecision 4) (plotframeref false) (viasonmask false) (mode 1)
      (useauxorigin false) (hpglpennumber 1) (hpglpenspeed 20) (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups true) (pdf_back_fp_property_popups true)
      (dxfpolygonmode true) (dxfimperialunits true) (dxfusepcbnewfont true)
      (psnegative false) (psa4output false) (plotreference true) (plotvalue false)
      (plotinvisibletext false) (sketchpadsonfab false) (subtractmaskfromsilk true)
      (outputformat 1) (mirror false) (drillshape 0) (scaleselection 1)
      (outputdirectory "gerbers/"))
  )''')
out.append('  (net 0 "")')
for i, nm in enumerate(D.NETS):
    out.append('  (net %d "%s")' % (i + 1, nm))

for ref, fp in footprints:
    out.append("  " + sexp.dumps(fp))

# ---- board outline + silkscreen -------------------------------------
def gr(kind, *args):
    out.append("  " + kind % args)

E = "Edge.Cuts"
c = [(D.BX0, D.BY0), (D.BX1, D.BY0), (D.BX1, D.BY1), (D.BX0, D.BY1)]
R = 2.0
for k in range(4):
    a, b = c[k], c[(k + 1) % 4]
    dx, dy = sexp, None
    ax, ay = a; bx, by = b
    ux = (bx - ax); uy = (by - ay)
    L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
    sx, sy = ax + ux * R, ay + uy * R
    ex, ey = bx - ux * R, by - uy * R
    out.append('  (gr_line (start %s %s) (end %s %s) (stroke (width 0.1) (type default)) (layer "%s") (tstamp %s))'
               % (n(sx), n(sy), n(ex), n(ey), E, uid()))
# rounded corners
for (px, py, sa) in [(D.BX0 + R, D.BY0 + R, 180), (D.BX1 - R, D.BY0 + R, 270),
                     (D.BX1 - R, D.BY1 - R, 0), (D.BX0 + R, D.BY1 - R, 90)]:
    a0 = math.radians(sa)
    a1 = a0 + math.radians(90)
    am = (a0 + a1) / 2
    out.append('  (gr_arc (start %s %s) (mid %s %s) (end %s %s) (stroke (width 0.1) (type default)) (layer "%s") (tstamp %s))'
               % (n(px + R * math.cos(a0)), n(py + R * math.sin(a0)),
                  n(px + R * math.cos(am)), n(py + R * math.sin(am)),
                  n(px + R * math.cos(a1)), n(py + R * math.sin(a1)), E, uid()))

def text(s, x, y, rot=0, size=1.0, layer="F.SilkS", mirror=False):
    j = ' (justify mirror)' if mirror else ''
    out.append('  (gr_text "%s" (at %s %s %s) (layer "%s") (tstamp %s)'
               ' (effects (font (size %s %s) (thickness %s))%s))'
               % (s, n(x), n(y), n(rot), layer, uid(), n(size), n(size), n(size * 0.15), j))

def tw(s, size):
    return len(s) * size * 0.85

# left strip: J1 legend (two vertical columns, centred)
text("J1  1:+12V 2:GND 3:CAN-H 4:CAN-L", 101.6, 80.0, 90, 0.9)
text("5:LIGHT 6:GND 7:A2 8:D6", 103.4, 80.0, 90, 0.9)
# right strip: J2 legend + board name
text("J2  1:GND 2:+5V 3:SCL 4:SDA", 126.8, 61.0, 90, 0.9)
text("RV2=DIM  RV1=spare", 123.4, 61.0, 90, 0.75)
text("GEAR DISPLAY %s" % REV, 125.1, 61.0, 90, 0.85)
# OLED connector pin letters
for lbl, px in (("G", 110.19), ("V", 112.73), ("C", 115.27), ("D", 117.81)):
    text(lbl, px, 57.3, 0, 0.9)
text("OLED", 114.0, 51.3, 0, 0.9)
# trimmer legend
text("RV1 A0", 108.3, 64.7, 90, 0.9)
text("DIM A1", 108.3, 73.7, 90, 0.9)
# component identification on the fab layer is handled per footprint;
# add the full title on the back silkscreen (hidden under the CANduino)
text("%s %s" % (TITLE, REV), 114.0, 78.0, 90, 1.0, layer="B.SilkS", mirror=True)

# ---- tracks / vias ---------------------------------------------------
for (x1, y1, x2, y2, lay, w, net) in tracks:
    out.append('  (segment (start %s %s) (end %s %s) (width %s) (layer "%s") (net %d) (tstamp %s))'
               % (n(x1), n(y1), n(x2), n(y2), n(w), lay, NETNUM[net], uid()))
for (x, y, net) in vias:
    out.append('  (via (at %s %s) (size %s) (drill %s) (layers "F.Cu" "B.Cu") (net %d) (tstamp %s))'
               % (n(x), n(y), n(D.VIA_D), n(D.VIA_DRILL), NETNUM[net], uid()))

# ---- GND pour --------------------------------------------------------
def pts_block(coords, ind):
    s = []
    line = []
    for (px, py) in coords:
        line.append("(xy %s %s)" % (n(px), n(py)))
        if len(line) == 6:
            s.append(ind + " ".join(line)); line = []
    if line:
        s.append(ind + " ".join(line))
    return "\n".join(s)

zone = []
zone.append('  (zone (net %d) (net_name "GND") (layers "B.Cu") (tstamp %s) (hatch edge 0.5)'
            % (NETNUM["GND"], uid()))
zone.append('    (connect_pads (clearance %s))' % n(TH_GAP))
zone.append('    (min_thickness 0.2) (filled_areas_thickness no)')
zone.append('    (fill yes (thermal_gap %s) (thermal_bridge_width %s))' % (n(TH_GAP), n(TH_SPOKE)))
zone.append('    (polygon (pts')
zone.append(pts_block(list(box(D.BX0, D.BY0, D.BX1, D.BY1).exterior.coords)[:-1], "      "))
zone.append('    ))')
for f in fills:
    zone.append('    (filled_polygon (layer "B.Cu") (pts')
    zone.append(pts_block(list(f.exterior.coords)[:-1], "      "))
    zone.append('    ))')
zone.append('  )')
out.append("\n".join(zone))
out.append(')')

pcb = "\n".join(out) + "\n"
open(PROJECT + ".kicad_pcb", "w").write(pcb)
print("wrote %s.kicad_pcb  (%d bytes)" % (PROJECT, len(pcb)))
