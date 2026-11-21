"""Open EEG band v0.2, 3 channels, wireless, side pods, sizes S, M and L.

A closed ring on the circumference line of the 10-20 map (10 % above the
nasion and the inion). It is the low-cost sister of the 16-channel EEG
headset frame in ../eeg-headset-frame and uses the same head model, the
same hub and the same electrode carrier.

The whole ring is one smooth loft. Its cross-section is a superellipse (a
rounded lens) whose width, thickness and height change along the ring: wide
and thin at the forehead, a collar at each joint, two pods above and behind
the ears, a firm arc at the back. The ring is cut into four printed parts:

  front           soft band (TPU 95A), Fp1, Fpz and Fp2 sockets for snap
                  electrodes, a lead channel inside, a tongue at each end.
  pod-board       left pod (PETG): the board. Sockets for the two tongues,
                  the earclip lead hole.
  pod-battery     right pod (PETG): the LiPo cell.
  rear            rigid arc (PETG) with hubs at O1 and O2, a lead channel to
                  both pods, a tongue at each end.
  cover-board-*   pod covers. The board cover has the Boltzmann vents (and the
  cover-battery   compass mark on the branded variant).
  carrier         the electrode carrier of the EEG frame. Print 2.

Each tongue sits in a socket of the pod and is held by one M3 bolt across
the band. The battery lead runs from the right pod through the rear arc to
the board in the left pod, inside the channel.

Board: Upside Down Labs Neuro PlayGround Lite (NPG Lite), 3 channels,
ESP32-C6, Bluetooth LE, Adafruit Feather form factor. The maker publishes no
drawing: the outline and holes are the Feather standard (ESTIMATE). The
room above the board is 7 mm (ESTIMATE): base board only, no Playmate.
The maker says the battery input has no polarity protection.

Variant B (wired): an Arduino Nano ESP32 in the left pod and 3 BioAmp EXG
Pill boards in the right pod, on foam tape. Outline proxies only.

Recording only. Battery only. Not a medical device. No stimulation.

Coordinates: x to the front, y to the left, z up, millimetres. The origin
is the centre of the reference plane.
"""

import importlib.util
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from common import style  # noqa: E402


def _load_frame():
    path = os.path.join(HERE, "..", "eeg-headset-frame", "design.py")
    spec = importlib.util.spec_from_file_location("eeg_frame_design", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


frame = _load_frame()

DESIGN_ID = "EEGB"
VERSION = "0.2.0"
SOURCE_URL = "github.com/tlcdv/the-hardware"

SIZES = frame.SIZES
V = cq.Vector

RING_THETA = 72.0
ELECTRODES = {"Fp1": 18.0, "Fpz": 0.0, "Fp2": -18.0,
              "O1": 162.0, "O2": 198.0}
FRONT_SITES = ("Fp1", "Fpz", "Fp2")
REAR_SITES = ("O1", "O2")

# Ring shape, as functions of the angle from the front (degrees).
POD_PHI = 100.0          # pod centres, left (+) board, right (-) battery
POD_HALF = 36.0          # pod influence, centre to zero
POD_PLATEAU = 21.0       # full pod size, centre to edge
SPLIT_FRONT = 64.0       # front | pod
SPLIT_REAR = 136.0       # pod | rear
COLLAR_HALF = 9.0
COLLAR_T = 3.0           # extra thickness at a joint
COLLAR_W = 3.0           # extra width at a joint
FRONT_W, SIDE_W, REAR_W = 25.0, 17.0, 16.0
FRONT_T, REAR_T = 4.6, 6.0
FRONT_GAP, REAR_GAP = 0.5, 3.0   # inner face above the scalp
POD_W, POD_T, POD_GAP, POD_LIFT = 36.0, 19.0, 2.0, 5.0
SUPER = 3.2              # superellipse exponent of the cross-section
STEP = 3.0               # degrees between loft sections
NPTS = 40                # points per section

# Joints.
TONGUE_INSET = 1.3
TONGUE_LEN = 8.0         # degrees
JOINT_CLEAR = 0.2
BOLT_CLEAR_D = 3.4       # M3

# Lead channel.
CHANNEL_D = 2.4

# Front sockets for snap electrodes.
STUD_D = 4.6             # 4 mm snap stud
SNAP_CB = (12.0, 2.0)    # lead snap connector, counterbore d, depth
PAD_RECESS = (20.0, 0.6)  # inner recess for the electrode disc

# Board pod (left), local frame at the pod centre: x along the ring,
# y up across the band, z out of the head (z = 0 on the scalp).
INCH = 25.4
BOARD = (2.0 * INCH, 0.9 * INCH, 1.6)       # Feather 50.8 x 22.86
BOARD_HOLES = (2.0 * INCH / 2 - 0.1 * INCH, 0.9 * INCH / 2 - 0.1 * INCH)
POD_FLOOR_TOP = POD_GAP + 2.0
POST_H = 2.0
POST_D, POST_PILOT_D = 4.5, 2.1
COMPONENT_SPACE = 7.0    # ESTIMATE
BOARD_CAVITY = (58.0, 26.0)
COVER_PLANE = 15.0       # covers are the part of the pod above this
COVER_LEDGE = 6.0        # cover overlaps the wall at both ends
COVER_SCREW = (2.4, 1.7)  # M2: clearance, pilot
EAR_LEAD_D = 3.5
# Battery pod (right): 1S pouch cell up to 8 x 30 x 40 mm (503035 to 803040).
BATTERY = (35.0, 30.0, 5.0)                 # model: 503035
BATTERY_CAVITY = (42.0, 31.0)
BATTERY_FLOOR = 1.0      # foam pad under the cell
# Variant B proxies.
PILL = (25.4, 10.0, 4.0)      # BioAmp EXG Pill 2.54 x 1.00 cm (maker README)
NANO = (45.0, 18.0, 6.0)      # Arduino Nano ESP32 outline, ESTIMATE


# ---------------------------------------------------------------- shape

def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _bump(d, half, plateau):
    """1 inside the plateau, smooth fall to 0 at `half`."""
    d = abs(d)
    if d <= plateau:
        return 1.0
    return 1.0 - _smooth((d - plateau) / (half - plateau))


def _wrap(phi):
    return (phi + 180.0) % 360.0 - 180.0


def profile(phi, pods=True):
    """(width, thickness, gap, lift) of the ring at `phi`."""
    a = abs(_wrap(phi))
    back = _smooth((a - 60.0) / 80.0)
    w = FRONT_W + (SIDE_W - FRONT_W) * _smooth(a / 60.0)
    w += (REAR_W - SIDE_W) * back
    t = FRONT_T + (REAR_T - FRONT_T) * back
    gap = FRONT_GAP + (REAR_GAP - FRONT_GAP) * back
    c = max(_bump(a - SPLIT_FRONT, COLLAR_HALF, 1.5),
            _bump(a - SPLIT_REAR, COLLAR_HALF, 1.5))
    w += COLLAR_W * c
    t += COLLAR_T * c
    lift = 0.0
    if pods:
        p = _bump(a - POD_PHI, POD_HALF, POD_PLATEAU)
        w += (POD_W - w) * p
        t += (POD_T - t) * p
        gap += (POD_GAP - gap) * p
        lift = POD_LIFT * p
    return w, t, gap, lift


def surface(size, phi, theta=RING_THETA):
    return frame.surface(size, theta, phi)


def ring_frame(size, phi):
    """Scalp point, outward normal, tangent (toward larger phi), up."""
    p, n = surface(size, phi)
    q, _ = surface(size, phi + 0.5)
    t = q - p
    t = (t - n * t.dot(n)).normalized()
    up = n.cross(t).normalized()
    if up.z < 0:
        up = up * -1
    return p, n, t, up


def _section(size, phi, inset=0.0, pods=True, extra=0.0):
    w, t, gap, lift = profile(phi, pods)
    w, t, gap = w - 2 * inset + 2 * extra, t - 2 * inset + 2 * extra, \
        gap + inset - extra
    p, n, _, up = ring_frame(size, phi)
    c = p + up * lift + n * (gap + t / 2)
    pts = []
    for k in range(NPTS):
        ang = 2 * math.pi * k / NPTS
        cu, su = math.cos(ang), math.sin(ang)
        u = math.copysign(abs(cu) ** (2 / SUPER), cu) * w / 2
        v = math.copysign(abs(su) ** (2 / SUPER), su) * t / 2
        pts.append(c + up * u + n * v)
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(pts, periodic=True)])


def _loft(size, phi0, phi1, **kw):
    count = max(2, int(round(abs(phi1 - phi0) / STEP)) + 1)
    wires = [_section(size, phi0 + (phi1 - phi0) * i / (count - 1), **kw)
             for i in range(count)]
    return cq.Solid.makeLoft(wires, False)


def _centre_path(size, phi0, phi1):
    count = max(2, int(round(abs(phi1 - phi0) / 2.0)) + 1)
    pts = []
    for i in range(count):
        phi = phi0 + (phi1 - phi0) * i / (count - 1)
        w, t, gap, lift = profile(phi)
        p, n, _, up = ring_frame(size, phi)
        pts.append(p + up * lift + n * (gap + t / 2))
    return pts


def _channel(size, phi0, phi1, d=CHANNEL_D):
    pts = _centre_path(size, phi0, phi1)
    path = cq.Wire.assembleEdges([cq.Edge.makeSpline(pts)])
    t0 = (pts[1] - pts[0]).normalized()
    circle = cq.Wire.makeCircle(d / 2, pts[0], t0)
    return cq.Solid.sweep(circle, [], path, True, True)


def _wp(shape):
    return cq.Workplane("XY").add(shape.clean())


# ----------------------------------------------------------------- joints

def _tongue(size, split, toward, extra=0.0):
    """Tongue from the part on one side of `split`, reaching TONGUE_LEN
    degrees into the pod in direction `toward` (+1 or -1)."""
    start = split - toward * 2.0
    end = split + toward * (TONGUE_LEN + (1.0 if extra else 0.0))
    return _loft(size, start, end, inset=TONGUE_INSET, pods=False,
                 extra=extra)


def _bolt(size, phi):
    p, n, _, up = ring_frame(size, phi)
    w, t, gap, lift = profile(phi)
    c = p + up * lift + n * (gap + t / 2)
    return cq.Solid.makeCylinder(BOLT_CLEAR_D / 2, w + 20,
                                 c - up * (w / 2 + 10), up)


JOINTS = ((SPLIT_FRONT, 1), (-SPLIT_FRONT, -1),
          (SPLIT_REAR, -1), (-SPLIT_REAR, 1))


def _bolt_phi(split, toward):
    return split + toward * TONGUE_LEN / 2


# ------------------------------------------------------------------ parts

def _pod_plane(size, side):
    phi = side * POD_PHI
    p, n, t, up = ring_frame(size, phi)
    _, _, _, lift = profile(phi)
    return cq.Plane(origin=p + up * lift, xDir=t, normal=n)


def _local(shape, plane):
    return shape.moved(cq.Location(plane))


def _box(x, y, z0, z1):
    return (cq.Workplane("XY").workplane(offset=z0).rect(x, y)
            .extrude(z1 - z0).val())


def _rbox(x, y, z0, z1, r=3.0):
    return (cq.Workplane("XY").workplane(offset=z0).rect(x, y)
            .extrude(z1 - z0).edges("|Z").fillet(r).val())


def _cavity(side):
    cx, cy = BOARD_CAVITY if side == 1 else BATTERY_CAVITY
    return _rbox(cx, cy, POD_FLOOR_TOP, 60.0)


def _cover_region(side):
    cx, cy = BOARD_CAVITY if side == 1 else BATTERY_CAVITY
    return _rbox(cx + 2 * COVER_LEDGE, cy - 2 * JOINT_CLEAR, COVER_PLANE,
                 60.0, r=2.0)


def _cover_cut(side):
    cx, cy = BOARD_CAVITY if side == 1 else BATTERY_CAVITY
    return _rbox(cx + 2 * COVER_LEDGE + 2 * JOINT_CLEAR, cy, COVER_PLANE,
                 60.0, r=2.0)


def _cover_screws(side, pilot):
    cx, _ = BOARD_CAVITY if side == 1 else BATTERY_CAVITY
    d = COVER_SCREW[1] if pilot else COVER_SCREW[0]
    z0 = COVER_PLANE - 6 if pilot else COVER_PLANE - 1
    out = []
    for sx in (1, -1):
        out.append(cq.Solid.makeCylinder(d / 2, 40, V(sx * (cx / 2 + COVER_LEDGE / 2), 0, z0),
                                         V(0, 0, 1)))
    return out


def _pod_raw(size, side):
    a0, a1 = (SPLIT_FRONT, SPLIT_REAR)
    if side == 1:
        return _loft(size, a0, a1)
    return _loft(size, -a1, -a0)


def build_pod(size, side):
    plane = _pod_plane(size, side)
    shape = _pod_raw(size, side)
    shape = shape.cut(_local(_cover_cut(side), plane))
    shape = shape.cut(_local(_cavity(side), plane))
    for split, toward in JOINTS:
        if (split > 0) == (side == 1):
            shape = shape.cut(_tongue(size, split, toward,
                                      extra=JOINT_CLEAR))
            shape = shape.cut(_bolt(size, _bolt_phi(split, toward)))
    shape = shape.cut(_channel(size, side * (SPLIT_FRONT - 1),
                               side * (SPLIT_REAR + 1)))
    for s in _cover_screws(side, True):
        shape = shape.cut(_local(s, plane))
    if side == 1:
        hx, hy = BOARD_HOLES
        posts = []
        for sx in (1, -1):
            for sy in (1, -1):
                post = (cq.Workplane("XY").workplane(offset=POD_FLOOR_TOP - 0.5)
                        .center(sx * hx, sy * hy).circle(POST_D / 2)
                        .extrude(POST_H + 0.5)
                        .faces(">Z").workplane().circle(POST_PILOT_D / 2)
                        .cutBlind(-(POST_H - 0.3)).val())
                shape = shape.fuse(_local(post, plane))
        lead = cq.Solid.makeCylinder(EAR_LEAD_D / 2, 30,
                                     V(14.0, 0, POD_FLOOR_TOP + 3.5),
                                     V(0, -1, 0))
        shape = shape.cut(_local(lead, plane))
        label = (cq.Workplane("XY").workplane(offset=POD_FLOOR_TOP - 0.6)
                 .center(0, 0)
                 .text(f"{DESIGN_ID}-{VERSION} CERN-OHL-S-2.0", 2.6, 0.7,
                       combine=False, halign="center", valign="center")
                 .val())
        shape = shape.cut(_local(label, plane))
    return _wp(shape)


def _outer_z(shape, plane, x, y):
    """Height of the outer surface above local (x, y)."""
    probe = cq.Solid.makeCylinder(0.3, 60, V(x, y, 0), V(0, 0, 1))
    common = shape.intersect(_local(probe, plane))
    bb = common.BoundingBox()
    centre = plane.toLocalCoords(V((bb.xmin + bb.xmax) / 2,
                                   (bb.ymin + bb.ymax) / 2, bb.zmax))
    top = 0.0
    for v in common.Vertices():
        top = max(top, plane.toLocalCoords(v.Center()).z)
    return top if top else centre.z


def build_cover(size, side, variant="store"):
    plane = _pod_plane(size, side)
    raw = _pod_raw(size, side)
    cover = raw.intersect(_local(_cover_region(side), plane))
    for s in _cover_screws(side, False):
        cover = cover.cut(_local(s, plane))
    if side == 1:
        shift = -7.0 if variant == "branded" else 0.0
        vents = style.boltzmann_vents(count=11, pitch=3.0, slot_width=1.6,
                                      max_length=18.0, min_length=7.0,
                                      depth=40).val()
        cover = cover.cut(_local(vents.translate(V(shift, 0, COVER_PLANE - 1)),
                                 plane))
        if variant == "branded":
            x = BOARD_CAVITY[0] / 2 - 8.0
            top = _outer_z(raw, plane, x, 0.0)
            mark = style.compass_mark(diameter=13.0, depth=20).val()
            mark = mark.translate(V(x, 0, top - style.ENGRAVE_DEPTH))
            cover = cover.cut(_local(mark, plane))
    return _wp(cover)


def build_front(size):
    shape = _loft(size, -SPLIT_FRONT, SPLIT_FRONT)
    for split, toward in JOINTS[:2]:
        shape = shape.fuse(_tongue(size, split, toward))
        shape = shape.cut(_bolt(size, _bolt_phi(split, toward)))
    shape = shape.cut(_channel(size, -SPLIT_FRONT - 7, SPLIT_FRONT + 7))
    for name in FRONT_SITES:
        p, n, t, up = ring_frame(size, ELECTRODES[name])
        w, th, gap, _ = profile(ELECTRODES[name])
        plane = cq.Plane(origin=p, xDir=t, normal=n)
        stud = cq.Solid.makeCylinder(STUD_D / 2, 20, V(0, 0, -2), V(0, 0, 1))
        cb = cq.Solid.makeCylinder(SNAP_CB[0] / 2, 20,
                                   V(0, 0, gap + th - SNAP_CB[1]), V(0, 0, 1))
        pad = cq.Solid.makeCylinder(PAD_RECESS[0] / 2, PAD_RECESS[1] + 2,
                                    V(0, 0, gap + PAD_RECESS[1] - 2 - 0.01),
                                    V(0, 0, 1))
        for c in (stud, cb, pad):
            shape = shape.cut(_local(c, plane))
    return _wp(shape)


def build_rear(size):
    shape = _loft(size, SPLIT_REAR, 360.0 - SPLIT_REAR)
    hubs, cuts = [], []
    for name in REAR_SITES:
        c, n = frame.hub_frame(size, RING_THETA, ELECTRODES[name])
        hubs.append(frame._hub(c, n))
        cuts.append(frame._cyl(frame.BORE_D,
                               frame.HUB_OFFSET + frame.HUB_LENGTH / 2 + 4,
                               c - n * (frame.HUB_OFFSET + 2), n))
        cuts.append(frame._cyl(frame.SET_SCREW_PILOT_D, 10,
                               c + V(0, 0, frame.HUB_D / 2 + 3),
                               V(0, 0, -1)))
        # lead hole from the outer face into the channel, beside the hub
        phi = ELECTRODES[name] + (8.0 if name == "O1" else -8.0)
        p, nn, _, _ = ring_frame(size, phi)
        _, t, gap, _ = profile(phi)
        cuts.append(cq.Solid.makeCylinder(1.4, t, p + nn * (gap + t / 2), nn))
    for h in hubs:
        shape = shape.fuse(h)
    for split, toward in JOINTS[2:]:
        shape = shape.fuse(_tongue(size, split, toward))
        shape = shape.cut(_bolt(size, _bolt_phi(split, toward)))
    shape = shape.cut(_channel(size, SPLIT_REAR - 7, 360.0 - SPLIT_REAR + 7))
    for c in cuts:
        shape = shape.cut(c)
    shape = _engrave_hub_names(shape, size)
    return _wp(shape)


def _engrave_hub_names(shape, size):
    for name in REAR_SITES:
        c, n = frame.hub_frame(size, RING_THETA, ELECTRODES[name])
        top = c + n * (frame.HUB_LENGTH / 2)
        plane = cq.Plane(origin=top, xDir=V(0, 1, 0).cross(n).normalized()
                         if abs(n.y) < 0.99 else V(1, 0, 0), normal=n)
        text = (cq.Workplane("XY").workplane(offset=-frame.LABEL_SIZE * 0.2)
                .center(0, frame.LABEL_RADIUS)
                .text(name, frame.LABEL_SIZE, 1.0, combine=False,
                      halign="center", valign="center").val())
        shape = shape.cut(_local(text, plane))
    return shape


def build_board_proxy(size):
    z = POD_FLOOR_TOP + POST_H
    bx, by, bt = BOARD
    board = _box(bx, by, z, z + bt).fuse(
        _box(bx - 8.0, by - 4.0, z + bt, z + bt + COMPONENT_SPACE - 0.5))
    return _wp(_local(board, _pod_plane(size, 1)))


def build_battery_proxy(size):
    bx, by, bz = BATTERY
    z = POD_FLOOR_TOP + BATTERY_FLOOR
    return _wp(_local(_box(bx, by, z, z + bz),
                      _pod_plane(size, -1)))


def build_variant_b_proxies(size):
    px, py, pz = PILL
    pills = None
    for i in (-1, 0, 1):
        p = _box(px, py, POD_FLOOR_TOP, POD_FLOOR_TOP + pz).translate(
            V(0, i * (py + 0.4), 0))
        pills = p if pills is None else pills.fuse(p)
    nx, ny, nz = NANO
    z = POD_FLOOR_TOP + POST_H
    nano = _box(nx, ny, z, z + nz)
    return (_wp(_local(pills, _pod_plane(size, -1))),
            _wp(_local(nano, _pod_plane(size, 1))))


def build_carrier():
    return frame.build_carrier()


def place_carrier(size, name):
    return frame.place_carrier(size, RING_THETA, ELECTRODES[name])


def build_cover_print(side, variant="store"):
    """A cover for the print file, outer face up, in its own frame."""
    cover = build_cover("M", side, variant).val()
    plane = _pod_plane("M", side)
    inv = cq.Location(plane).inverse
    return _wp(cover.moved(inv))


def build_all():
    parts = {"carrier": build_carrier()}
    for variant in ("store", "branded"):
        parts[f"cover-board-{variant}"] = build_cover_print(1, variant)
    parts["cover-battery"] = build_cover_print(-1)
    for size in SIZES:
        parts[f"{size}-front"] = build_front(size)
        parts[f"{size}-pod-board"] = build_pod(size, 1)
        parts[f"{size}-pod-battery"] = build_pod(size, -1)
        parts[f"{size}-rear"] = build_rear(size)
    return parts


# -------------------------------------------------------------- fit checks

BED = 250.0
MIN_POD_CLEAR = 0.3     # the pod ends meet the front band, which touches
MIN_REAR_CLEAR = 2.5
MIN_WALL = 1.2


def _grown(shape, d):
    bb = shape.BoundingBox()
    return cq.Solid.makeBox(bb.xlen + 2 * d, bb.ylen + 2 * d, bb.zlen + 2 * d,
                            V(bb.xmin - d, bb.ymin - d, bb.zmin - d))


def fit_checks(shapes, overlap, report):
    for size in SIZES:
        front = shapes[f"{size}-front"]
        pb, pc = shapes[f"{size}-pod-board"], shapes[f"{size}-pod-battery"]
        rear = shapes[f"{size}-rear"]
        cb = build_cover(size, 1, "branded").val()
        cc = build_cover(size, -1).val()
        head = frame.build_head(size).val()
        board = build_board_proxy(size).val()
        battery = build_battery_proxy(size).val()
        pills, nano = (p.val() for p in build_variant_b_proxies(size))
        print(f"  size {size}: circumference {SIZES[size]:.0f} mm")
        pairs = {"front/pod-board": (front, pb), "front/pod-battery": (front, pc),
                 "rear/pod-board": (rear, pb), "rear/pod-battery": (rear, pc),
                 "cover-board/pod": (cb, pb), "cover-battery/pod": (cc, pc),
                 "board/pod": (board, pb), "board/cover": (board, cb),
                 "battery/pod": (battery, pc), "battery/cover": (battery, cc),
                 "B nano/pod": (nano, pb), "B nano/cover": (nano, cb),
                 "B pills/pod": (pills, pc), "B pills/cover": (pills, cc)}
        for label, (x, y) in pairs.items():
            v = overlap(x, y)
            report(f"{size} {label} overlap", v <= 0.01, f"{v:.3f} mm3")
        # The board and the battery stay inside the closed pod (pod + cover).
        for label, proxy, pod, cov in (("board", board, pb, cb),
                                       ("battery", battery, pc, cc)):
            raw = _pod_raw(size, 1 if label == "board" else -1)
            outside = proxy.cut(raw).Volume()
            report(f"{size} {label} inside the pod", outside <= 0.01,
                   f"{outside:.3f} mm3 outside")
        g = front.distance(head)
        report(f"{size} front to scalp", g >= 0.3, f"{g:.2f} mm")
        for label, part, lim in (("pod-board", pb, MIN_POD_CLEAR),
                                 ("pod-battery", pc, MIN_POD_CLEAR),
                                 ("rear", rear, MIN_REAR_CLEAR)):
            g = part.distance(head)
            report(f"{size} {label} to scalp", g >= lim,
                   f"{g:.1f} mm (min {lim})")
        zmin = min(pb.BoundingBox().zmin, pc.BoundingBox().zmin)
        print(f"  size {size}: lowest point of the pods z = {zmin:.1f} mm "
              "(ear canal level is about z = 0 on this head model)")
        for key in (f"{size}-front", f"{size}-rear", f"{size}-pod-board"):
            bb = shapes[key].BoundingBox()
            dims = sorted((bb.xlen, bb.ylen, bb.zlen))
            report(f"{key} in {BED:.0f} mm volume", dims[-1] <= BED,
                   " x ".join(f"{d:.0f}" for d in dims) + " mm")
        for name in REAR_SITES:
            carrier = place_carrier(size, name).val()
            v = overlap(carrier, rear)
            report(f"{size} carrier {name} / rear", v <= 0.01, f"{v:.3f} mm3")
            g = carrier.distance(head)
            report(f"{size} carrier {name} / scalp", g > 0, f"{g:.1f} mm")


# ----------------------------------------------------------------- renders

def assembly(size="M", variant="branded"):
    """Every part in place, for renders: name -> (shape, colour key)."""
    parts = {
        "front": (build_front(size), "pink"),
        "pod_board": (build_pod(size, 1), "glass"),
        "pod_battery": (build_pod(size, -1), "glass"),
        "rear": (build_rear(size), "pink"),
        "cover_board": (build_cover(size, 1, variant), "pink"),
        "cover_battery": (build_cover(size, -1), "pink"),
        "board": (build_board_proxy(size), "board"),
        "battery": (build_battery_proxy(size), "board"),
    }
    for name in REAR_SITES:
        parts[f"carrier_{name}"] = (place_carrier(size, name), "glass")
    return parts


def render_views():
    m = "M"
    parts = assembly(m)
    head = frame.build_head(m)
    items = list(parts.values())
    hero = [(430, 330, 240), (0, 0, 55), (0, 0, 1)]
    back = [(-470, 300, 260), (-20, 0, 50), (0, 0, 1)]
    side = [(30, 520, 120), (0, 0, 40), (0, 0, 1)]
    return [("band-branded.png", items, hero, 1.3),
            ("on-head-front.png", [(head, "head")] + items, hero, 1.15),
            ("on-head-back.png", [(head, "head")] + items, back, 1.15),
            ("on-head-side.png", [(head, "head")] + items, side, 1.2)]
