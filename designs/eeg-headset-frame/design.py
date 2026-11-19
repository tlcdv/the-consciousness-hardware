"""Open EEG headset frame, 16 electrode positions, sizes S, M and L.

The frame holds 16 electrodes at 10-20 positions (Fp1 Fp2 F3 F4 F7 F8 C3
C4 T7 T8 P3 P4 P7 P8 O1 O2), the 16 channels of an OpenBCI Cyton board with
the Daisy module. It is our own design, made from scratch in this file. It
uses no shapes or code from other headsets.

Parts for one size:
  left, right     the two halves of the frame (mirror images). Each half has
                  8 hubs, the struts between them, and joint bosses on the
                  midline.
  spine-store     the rear joint between the halves, with a plate for the
  spine-branded   board. M3 bolts go through the joint bosses.
  carrier         electrode carrier, the same for all sizes. Print 16.
                  It slides in a hub, an M3 self-tapping screw locks it, and
                  a cup at the bottom holds an OpenBCI 5 mm dry comb electrode.

Variants of the spine:
  store     part number and license only. For print services.
  branded   compass mark on the plate and the source URL. Personal prints
            only, never sold (see NOTICE).

Head model. The head is an ellipsoid. Width is 0.8 of length, height above
the reference plane (nasion, inion, preauricular points) is 1.33 of half
length. The 10-20 positions are angles on a sphere, stretched onto the
ellipsoid. They are near the measured 10-20 positions, not equal to them.

Coordinates: x to the front, y to the left, z up, millimetres. The origin
is the centre of the reference plane.
"""

import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from common import style  # noqa: E402

DESIGN_ID = "EEGF"
VERSION = "0.1.0"
SOURCE_URL = "github.com/tlcdv/the-hardware"

# Head circumference in mm for each size. Design values: measure the head
# around the forehead and the back of the head and take the nearest size.
SIZES = {"S": 540.0, "M": 570.0, "L": 600.0}
WIDTH_RATIO = 0.80
HEIGHT_RATIO = 1.33

# Hubs.
HUB_OFFSET = 15.0        # scalp to hub centre, along the surface normal
HUB_LENGTH = 14.0
HUB_D = 20.0
BORE_D = 12.5
SET_SCREW_PILOT_D = 2.6  # M3 self-tapping into plastic
STRUT_SAMPLES = 9         # points on each rib
RIB_W = 9.0               # rib width along the head
RIB_T = 5.0               # rib thickness across the head
FLANGE_D = 23.0           # hub top flange, carries the position name
FLANGE_T = 3.0
LABEL_SIZE = 3.0          # height of the engraved names
LABEL_RADIUS = 8.9        # name centre from the hub axis

# Strap tabs with the ear-clip lead hole (REF on one side, BIAS on the other) and
# cable clips. Positions as sphere angles, like the electrodes.
LEAD_HOLE_D = 4.0               # ear-clip lead, in the strap tab
STRAP_TAB = (75.0, 108.0)
STRAP_TAB_SIZE = (30.0, 22.0)
STRAP_SLOT = (22.0, 4.0)        # for a 20 mm elastic strap
CLIP_R_OUT = 4.2
CLIP_R_IN = 2.7
CLIP_LENGTH = 6.0
CLIP_GAP = 3.0

# Midline joints.
BOSS_D = 16.0
BOSS_LENGTH = 4.0        # each half, front joints
SPINE_HALF_WIDTH = 10.0  # the spine fills y = -10 .. 10 at the rear joints
BOLT_CLEAR_D = 3.4       # M3

# Electrode carrier.
CARRIER_D = 12.0
CARRIER_LENGTH = 30.0
CAP_D = 16.0
CAP_T = 2.0
# OpenBCI 5 mm dry comb electrode: "Top diameter 1/4", bottom diameter
# 13/32"" (shop.openbci.com). It mounts with a screw; OpenBCI does not
# publish the screw size (the Mark III used 2-56 screws), so the centre
# hole takes 2-56 or M2. NOT VERIFIED with a real electrode.
SCREW_HOLE_D = 2.3
CUP_D = 13 / 32 * 25.4 + 0.4   # 10.7 mm, 0.2 mm clearance each side
CUP_DEPTH = 3.0
GRIP_COUNT = 18          # grip grooves around the cap
GRIP_D = 1.6
ELECTRODE_PROTRUSION = 4.0   # electrode face below the carrier bottom

# OpenBCI Cyton board: "2.41 x 2.41 (octagon has 1 edges)", "Mount holes
# are 1/16 ID, 0.8 x 2.166 on center" (docs.openbci.com/Cyton/CytonSpecs).
INCH = 25.4
BOARD_W = 2.41 * INCH
BOARD_T = 1.6            # standard PCB thickness, not in the Cyton docs
HOLE_DX = 2.166 * INCH
HOLE_DY = 0.8 * INCH
POST_D = 4.5
POST_H = 8.0             # room under the board for the battery
POST_PILOT_D = 1.3       # M1.6 self-tapping, from the 1/16 inch hole

# Board pod on the spine (local frame, see _spine_local). The pod is an
# octagon like the board. Its cover carries the vent slots.
PLATE_Z0 = BOSS_D / 2 + 1.0   # pod floor: 1 mm above the joint bosses
POD_FLOOR = 2.5
POD_WALL = 2.0
POD_CLEAR = 1.0               # board edge to inner wall
POD_ACROSS = BOARD_W + 2 * (POD_CLEAR + POD_WALL)
COMPONENT_SPACE = 18.0        # above the board. Estimate for Cyton + Daisy
COVER_T = 2.5
COVER_LIP = 2.0
LIP_GAP = 0.2
EAR_D = 8.0
COVER_SCREW_PILOT_D = 1.7     # M2 self-tapping
COVER_SCREW_CLEAR_D = 2.4
CABLE_SLOT = (26.0, 8.0)      # width, height, in the wall at the Oz end
MARK_X = 18.0                 # compass mark on the branded cover
# Battery bay under the board: a 1S LiPo pouch cell, 503035 type
# (5 x 30 x 35 mm). The Cyton docs say "Power with 3-6V DC Battery ONLY".
BATTERY = (35.0, 30.0, 5.0)
BATTERY_CLEAR = 0.5
BATTERY_RIB_H = 3.0


# 10-20 positions on a unit sphere: (angle from the vertex, azimuth from the
# front, left positive), in degrees. 10 % of an arc is 18 degrees.
_LEFT_BASE = {
    "Fp1": (72.0, 18.0),
    "F7": (72.0, 54.0),
    "T7": (72.0, 90.0),
    "P7": (72.0, 126.0),
    "O1": (72.0, 162.0),
    "C3": (36.0, 90.0),
}
MIDLINE = {
    "Fpz": (72.0, 0.0),
    "Fz": (36.0, 0.0),
    "Cz": (0.0, 0.0),
    "Pz": (36.0, 180.0),
    "Oz": (72.0, 180.0),
}
LEFT_STRUTS = [
    ("Fp1", "F7"), ("F7", "T7"), ("T7", "P7"), ("P7", "O1"),
    ("Fp1", "F3"), ("F3", "F7"), ("F3", "C3"), ("C3", "T7"),
    ("C3", "P3"), ("P3", "P7"), ("P3", "O1"),
]
# Electrode -> midline joint. The rear joints (Pz, Oz) go to the spine.
LEFT_JOINTS = [("Fp1", "Fpz"), ("F3", "Fz"), ("C3", "Cz"),
               ("P3", "Pz"), ("O1", "Oz")]
FRONT_JOINTS = ("Fpz", "Fz", "Cz")
REAR_JOINTS = ("Pz", "Oz")

V = cq.Vector


# ---------------------------------------------------------------- geometry

def _unit(theta, phi):
    t, p = math.radians(theta), math.radians(phi)
    return (math.sin(t) * math.cos(p), math.sin(t) * math.sin(p),
            math.cos(t))


def _slerp_mid(a, b):
    """Great-circle midpoint of two sphere positions given as angles."""
    pa, pb = _unit(*a), _unit(*b)
    m = [x + y for x, y in zip(pa, pb)]
    n = math.sqrt(sum(x * x for x in m))
    m = [x / n for x in m]
    return (math.degrees(math.acos(m[2])),
            math.degrees(math.atan2(m[1], m[0])))


def left_positions():
    pos = dict(_LEFT_BASE)
    # F3 is midway between Fz and F7, P3 midway between Pz and P7.
    pos["F3"] = _slerp_mid(MIDLINE["Fz"], pos["F7"])
    pos["P3"] = _slerp_mid(MIDLINE["Pz"], pos["P7"])
    return pos


def right_name(name):
    """Fp1 -> Fp2, F3 -> F4, T7 -> T8, O1 -> O2."""
    digit = int(name[-1])
    return name[:-1] + str(digit + 1)


ELECTRODES = sorted(list(left_positions()) +
                    [right_name(n) for n in left_positions()])


def _perimeter(a, b):
    """Ramanujan's approximation of the perimeter of an ellipse."""
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))


def head_axes(size):
    circ = SIZES[size]
    a = circ / _perimeter(1.0, WIDTH_RATIO)
    return a, WIDTH_RATIO * a, HEIGHT_RATIO * a


def surface(size, theta, phi):
    """Point on the head surface and the outward unit normal there."""
    a, b, c = head_axes(size)
    u = _unit(theta, phi)
    p = V(a * u[0], b * u[1], c * u[2])
    n = V(p.x / a ** 2, p.y / b ** 2, p.z / c ** 2).normalized()
    return p, n


def hub_frame(size, theta, phi):
    p, n = surface(size, theta, phi)
    return p + n * HUB_OFFSET, n


def arcs(size):
    """Nasion-inion and preauricular arcs over the vertex, mm."""
    a, b, c = head_axes(size)
    return _perimeter(a, c) / 2, _perimeter(b, c) / 2


def build_head(size):
    """The head ellipsoid as a solid, for fit checks and renders."""
    a, b, c = head_axes(size)
    sphere = cq.Solid.makeSphere(100.0, angleDegrees1=-90, angleDegrees2=90)
    scale = cq.Matrix([[a / 100, 0, 0, 0], [0, b / 100, 0, 0],
                       [0, 0, c / 100, 0]])
    return cq.Workplane("XY").add(sphere.transformGeometry(scale))


# ------------------------------------------------------------------- parts

def _cyl(d, length, start, direction):
    return cq.Solid.makeCylinder(d / 2, length, start, direction.normalized())


def _rod(d, p1, p2):
    return _cyl(d, (p2 - p1).Length, p1, p2 - p1)


def _fuse(solids):
    """Fuse one solid at a time. One boolean with many swept ribs gives an
    invalid shape in OCCT; step by step gives a valid one."""
    shape = solids[0]
    for solid in solids[1:]:
        shape = shape.fuse(solid).clean()
    return cq.Workplane("XY").add(shape)


def _perpendicular(n):
    d = n.cross(V(0, 0, 1))
    if d.Length < 1e-6:
        d = n.cross(V(1, 0, 0))
    return d.normalized()


def _joint_y(name):
    return SPINE_HALF_WIDTH if name in REAR_JOINTS else 0.0


def _slerp(a, b, t):
    pa, pb = _unit(*a), _unit(*b)
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(pa, pb))))
    om = math.acos(dot)
    if om < 1e-9:
        u = pa
    else:
        s1 = math.sin((1 - t) * om) / math.sin(om)
        s2 = math.sin(t * om) / math.sin(om)
        u = [s1 * x + s2 * y for x, y in zip(pa, pb)]
    return (math.degrees(math.acos(max(-1.0, min(1.0, u[2])))),
            math.degrees(math.atan2(u[1], u[0])))


def _rib(size, a, b, end=None, samples=STRUT_SAMPLES):
    """A flat rib that follows the head surface at hub height, from sphere
    position a to b. The profile is an ellipse, wide along the head and
    thin across it. `end` replaces the last point (joint bosses)."""
    pts, aux = [], []
    for i in range(samples):
        theta, phi = _slerp(a, b, i / (samples - 1))
        p, n = surface(size, theta, phi)
        c = p + n * HUB_OFFSET
        pts.append(c)
        aux.append(c + n * 5.0)
    if end is not None:
        # Move the rib to `end` smoothly over its length, not in one step.
        shift = end - pts[-1]
        for i in range(samples):
            w = (i / (samples - 1)) ** 2
            pts[i] = pts[i] + shift * w
            aux[i] = aux[i] + shift * w
    edge = cq.Edge.makeSpline(pts)
    path = cq.Wire.assembleEdges([edge])
    guide = cq.Wire.assembleEdges([cq.Edge.makeSpline(aux)])
    t = edge.tangentAt(0)
    n0 = (aux[0] - pts[0]).normalized()
    lateral = t.cross(n0).normalized()
    profile = cq.Wire.makeEllipse(RIB_W / 2, RIB_T / 2, pts[0], t, lateral)
    return cq.Solid.sweep(profile, [], path, True, False, guide)


def _lateral(size, joint, y_target):
    """Sphere angles near a midline joint where the hub-height point has
    y = y_target (left side)."""
    theta, phi0 = MIDLINE[joint]
    lo, hi = 0.0, 30.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if theta == 0.0:
            t2, p2 = mid, 90.0
        else:
            t2, p2 = theta, (phi0 + mid if phi0 == 0.0 else phi0 - mid)
        y = hub_frame(size, t2, p2)[0].y
        lo, hi = (mid, hi) if y < y_target else (lo, mid)
    if theta == 0.0:
        return lo, 90.0
    return theta, (phi0 + lo if phi0 == 0.0 else phi0 - lo)


def _hub(centre, n):
    """Tapered hub with a flat flange on top for the position name."""
    bottom = centre - n * (HUB_LENGTH / 2)
    cone = cq.Solid.makeCone(HUB_D / 2, HUB_D / 2 - 1.5,
                             HUB_LENGTH - FLANGE_T, bottom, n)
    flange = cq.Solid.makeCylinder(FLANGE_D / 2, FLANGE_T,
                                   centre + n * (HUB_LENGTH / 2 - FLANGE_T), n)
    return cone.fuse(flange)


def _local_plane(origin, n, along):
    """Plane with normal n, x axis = `along` made perpendicular to n."""
    x = (along - n * along.dot(n)).normalized()
    return cq.Plane(origin=origin, xDir=x, normal=n)


def _strap_tab(size):
    """Tab below the T7-P7 ring, behind the ear. A slot for a 20 mm
    elastic strap and a hole that holds the lead of the ear-clip electrode
    (reference or bias). Both stay above and behind the ear."""
    p, n = surface(size, *STRAP_TAB)
    centre = p + n * HUB_OFFSET
    _, n_up = surface(size, STRAP_TAB[0] - 5.0, STRAP_TAB[1])
    p_up = surface(size, STRAP_TAB[0] - 5.0, STRAP_TAB[1])[0] + n_up * HUB_OFFSET
    up = p_up - centre
    plane = _local_plane(centre, n, n.cross(up))
    tab = (cq.Workplane(plane).rect(STRAP_TAB_SIZE[0], STRAP_TAB_SIZE[1])
           .extrude(RIB_T / 2, both=True)
           .edges(cq.selectors.ParallelDirSelector(n)).fillet(4.0))
    slot = (cq.Workplane(plane).center(0, -2.0)
            .slot2D(STRAP_SLOT[0], STRAP_SLOT[1]).extrude(5, both=True))
    lead = (cq.Workplane(plane).center(0, 6.0)
            .circle(LEAD_HOLE_D / 2).extrude(5, both=True))
    return tab.val(), slot.union(lead).val()


def _cable_clip(size, a, b):
    """Open C clip on the outer side of a rib, at its middle."""
    theta, phi = _slerp(a, b, 0.5)
    p, n = surface(size, theta, phi)
    centre = p + n * (HUB_OFFSET + RIB_T / 2 + CLIP_R_OUT - 0.6)
    t0, p0 = _slerp(a, b, 0.45)
    t1, p1 = _slerp(a, b, 0.55)
    tangent = (hub_frame(size, t1, p1)[0] - hub_frame(size, t0, p0)[0])
    tangent = tangent.normalized()
    start = centre - tangent * (CLIP_LENGTH / 2)
    ring = cq.Solid.makeCylinder(CLIP_R_OUT, CLIP_LENGTH, start, tangent).cut(
        cq.Solid.makeCylinder(CLIP_R_IN, CLIP_LENGTH + 2,
                              start - tangent, tangent))
    plane = _local_plane(centre + n * CLIP_R_OUT, n, tangent)
    gap = (cq.Workplane(plane).rect(CLIP_LENGTH + 2, CLIP_GAP)
           .extrude(CLIP_R_OUT * 1.2, both=True)).val()
    return ring.cut(gap)


def _hub_frames(size, side):
    """Hub centre and normal for each electrode on one side."""
    out = {}
    for name, (theta, phi) in left_positions().items():
        centre, n = hub_frame(size, theta, phi)
        if side == "right":
            name = right_name(name)
            centre, n = V(centre.x, -centre.y, centre.z), V(n.x, -n.y, n.z)
        out[name] = (centre, n)
    return out


def _body_left(size):
    """The left half without the position names."""
    pos = left_positions()
    hubs = {k: hub_frame(size, *v) for k, v in pos.items()}
    joints = {k: hub_frame(size, *v) for k, v in MIDLINE.items()}
    solids = [_hub(c, n) for c, n in hubs.values()]
    for a, b in LEFT_STRUTS:
        solids.append(_rib(size, pos[a], pos[b]))
        solids.append(_cable_clip(size, pos[a], pos[b]))
    for electrode, joint in LEFT_JOINTS:
        j, nj = joints[joint]
        y0 = _joint_y(joint)
        y_mid = y0 + BOSS_LENGTH / 2
        solids.append(_cyl(BOSS_D, BOSS_LENGTH, V(j.x, y0, j.z), V(0, 1, 0)))
        target = _lateral(size, joint, y_mid)
        # The rib meets the top edge of the boss. The centre of the boss
        # face stays free for the bolt head or the nut.
        up = V(nj.x, 0, nj.z).normalized() * (BOSS_D / 2 - 1.5)
        solids.append(_rib(size, pos[electrode], target,
                           end=V(j.x, y_mid, j.z) + up))
    tab, slot = _strap_tab(size)
    solids.append(tab)
    frame = _fuse(solids)
    cuts = [slot]
    for centre, n in hubs.values():
        cuts.append(_cyl(BORE_D, HUB_LENGTH + 20, centre - n * (
            HUB_LENGTH / 2 + 10), n))
        side = _perpendicular(n)
        cuts.append(_cyl(SET_SCREW_PILOT_D, HUB_D / 2 + 2,
                         centre - n * 2.0, side))
    for joint in MIDLINE:
        j = joints[joint][0]
        y0 = _joint_y(joint)
        cuts.append(_cyl(BOLT_CLEAR_D, BOSS_LENGTH + 2, V(j.x, y0 - 1, j.z),
                         V(0, 1, 0)))
        # Flat joint face: nothing of this half past the face at y0.
        cuts.append(cq.Solid.makeBox(30, 50 + y0, 30,
                                     V(j.x - 15, -50, j.z - 15)))
    return _cut_all(frame, cuts)


def _cut_all(frame, cuts):
    """Cut one solid at a time, for the same reason as _fuse."""
    shape = frame.val()
    for cut in cuts:
        shape = shape.cut(cut).clean()
    return cq.Workplane("XY").add(shape)


def _engrave_names(frame, size, side):
    """Cut the 10-20 name of each electrode into its hub flange."""
    top = HUB_LENGTH / 2
    for name, (centre, n) in _hub_frames(size, side).items():
        up = V(0, 0, 1) - n * n.dot(V(0, 0, 1))
        if up.Length < 1e-6:
            up = V(1, 0, 0) - n * n.x
        up = up.normalized()
        origin = centre + n * top + up * LABEL_RADIUS
        x = up.cross(n)
        plane = cq.Plane(origin=origin, xDir=x, normal=n)
        text = cq.Workplane(plane).text(name, LABEL_SIZE,
                                        -style.ENGRAVE_DEPTH, combine=False,
                                        halign="center", valign="center")
        frame = frame.cut(text)
    return frame


def build_left(size):
    return _engrave_names(_body_left(size), size, "left")


def build_right(size):
    return _engrave_names(_body_left(size).mirror("XZ"), size, "right")


def _spine_axes(size):
    jp, _ = hub_frame(size, *MIDLINE["Pz"])
    jo, _ = hub_frame(size, *MIDLINE["Oz"])
    ex = (jp - jo).normalized()
    ey = V(0, 1, 0)
    ez = ex.cross(ey)
    mid = (jp + jo) * 0.5
    if ez.dot(mid) < 0:   # point away from the head centre
        ez, ey = ez * -1, ey * -1   # flip two axes: still a rotation
    return mid, ex, ey, ez, (jp - jo).Length


def _octagon(width):
    r = width / 2 / math.cos(math.radians(22.5))
    return [(r * math.cos(math.radians(22.5 + 45 * i)),
             r * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]


def _oct_prism(width, z0, height):
    return (cq.Workplane("XY").workplane(offset=z0)
            .polyline(_octagon(width)).close().extrude(height))


def _pod_levels():
    floor_top = PLATE_Z0 + POD_FLOOR
    board_z = floor_top + POST_H
    wall_top = board_z + BOARD_T + COMPONENT_SPACE
    return floor_top, board_z, wall_top


def _ear_positions():
    y = POD_ACROSS / 2 + EAR_D / 2 - 1.0
    return [(0.0, y), (0.0, -y)]


def _spine_local(size, variant):
    """The spine in its own frame: x from Oz to Pz, z away from the head.
    A bar between the two rear joints carries the board pod."""
    _, _, _, _, dist = _spine_axes(size)
    half = dist / 2
    w = SPINE_HALF_WIDTH
    floor_top, _, wall_top = _pod_levels()
    bar = (cq.Workplane("XY").box(dist, 2 * w, PLATE_Z0 + 5.0)
           .translate((0, 0, (PLATE_Z0 - 5.0) / 2))
           .edges("|Y").fillet(3.0))
    for x in (-half, half):
        boss = (cq.Workplane("XZ").workplane(offset=-w).center(x, 0)
                .circle(BOSS_D / 2).extrude(2 * w))
        bar = bar.union(boss)
    outer = _oct_prism(POD_ACROSS, PLATE_Z0, wall_top - PLATE_Z0)
    outer = outer.edges("|Z").fillet(2.0)
    inner = _oct_prism(POD_ACROSS - 2 * POD_WALL, floor_top, wall_top)
    pod = outer.cut(inner)
    for x, y in _ear_positions():
        ear = (cq.Workplane("XY").workplane(offset=wall_top - 6.0)
               .center(x, y).circle(EAR_D / 2).extrude(6.0))
        pod = pod.union(ear)
        pilot = (cq.Workplane("XY").workplane(offset=wall_top - 6.5)
                 .center(x, y).circle(COVER_SCREW_PILOT_D / 2).extrude(7))
        pod = pod.cut(pilot)
    slot_w, slot_h = CABLE_SLOT
    slot = (cq.Workplane("YZ").workplane(offset=-POD_ACROSS / 2 - 1)
            .center(0, floor_top + slot_h / 2 + 1.0).rect(slot_w, slot_h)
            .extrude(POD_WALL + 2))
    pod = pod.cut(slot)
    spine = bar.union(pod)
    bx, by, _ = BATTERY
    hx, hy = bx / 2 + BATTERY_CLEAR, by / 2 + BATTERY_CLEAR
    for sx in (-1, 1):
        for sy in (-1, 1):
            for w, h, cx, cy in ((8.0, 1.5, sx * (hx - 3.0), sy * (hy + 0.75)),
                                 (1.5, 8.0, sx * (hx + 0.75), sy * (hy - 3.0))):
                rib = (cq.Workplane("XY").workplane(offset=floor_top)
                       .center(cx, cy).rect(w, h).extrude(BATTERY_RIB_H))
                spine = spine.union(rib)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * HOLE_DX / 2, sy * HOLE_DY / 2
            post = (cq.Workplane("XY").workplane(offset=floor_top)
                    .center(x, y).circle(POST_D / 2).extrude(POST_H))
            spine = spine.union(post)
            pilot = (cq.Workplane("XY").workplane(offset=floor_top - 1.5)
                     .center(x, y).circle(POST_PILOT_D / 2)
                     .extrude(POST_H + 2))
            spine = spine.cut(pilot)
    for x in (-half, half):
        bolt = (cq.Workplane("XZ").workplane(offset=-w - 1).center(x, 0)
                .circle(BOLT_CLEAR_D / 2).extrude(2 * w + 2))
        spine = spine.cut(bolt)
    lines = [f"{DESIGN_ID}-{size} v{VERSION}", "CERN-OHL-S-2.0"]
    if variant == "branded":
        lines.append(SOURCE_URL)
    wp = spine.faces("<Z").workplane(centerOption="CenterOfBoundBox")
    step = 2.2 * 1.6
    y0 = step * (len(lines) - 1) / 2
    for i, line in enumerate(lines):
        text = wp.center(0, y0 - i * step).text(
            line, 2.2, -style.ENGRAVE_DEPTH, combine=False,
            halign="center", valign="center")
        spine = spine.cut(text)
    return spine


def _cover_local(variant):
    """Pod cover in the spine frame, with Boltzmann vents and a lip."""
    _, _, wall_top = _pod_levels()
    cover = _oct_prism(POD_ACROSS, wall_top, COVER_T)
    cover = cover.edges("|Z").fillet(2.0)
    for x, y in _ear_positions():
        ear = (cq.Workplane("XY").workplane(offset=wall_top).center(x, y)
               .circle(EAR_D / 2).extrude(COVER_T))
        cover = cover.union(ear)
    lip_out = POD_ACROSS - 2 * POD_WALL - 2 * LIP_GAP
    lip = _oct_prism(lip_out, wall_top - COVER_LIP, COVER_LIP).cut(
        _oct_prism(lip_out - 2 * 1.2, wall_top - COVER_LIP - 1,
                   COVER_LIP + 1))
    cover = cover.union(lip)
    for x, y in _ear_positions():
        hole = (cq.Workplane("XY").workplane(offset=wall_top - 3)
                .center(x, y).circle(COVER_SCREW_CLEAR_D / 2)
                .extrude(COVER_T + 6))
        cover = cover.cut(hole)
    vents = style.boltzmann_vents(count=11, pitch=3.0, slot_width=1.6,
                                  max_length=34.0, min_length=12.0,
                                  depth=COVER_T + 2)
    shift = -8.0 if variant == "branded" else 0.0
    cover = cover.cut(vents.translate((shift, 0, wall_top - 1)))
    if variant == "branded":
        mark = style.compass_mark(diameter=13.0).translate(
            (MARK_X, 0, wall_top + COVER_T - style.ENGRAVE_DEPTH))
        cover = cover.cut(mark)
    return cover


def _place(shape_wp, size):
    mid, ex, _, ez, _ = _spine_axes(size)
    loc = cq.Location(cq.Plane(origin=mid, xDir=ex, normal=ez))
    return cq.Workplane("XY").add(shape_wp.val().moved(loc))


def build_spine(size, variant="store"):
    return _place(_spine_local(size, variant), size)


def build_cover(size, variant="store"):
    return _place(_cover_local(variant), size)


def build_cover_print(variant="store"):
    """The cover alone, top face on the bed, for the print file."""
    _, _, wall_top = _pod_levels()
    return (_cover_local(variant)
            .translate((0, 0, -wall_top - COVER_T))
            .rotate((0, 0, 0), (1, 0, 0), 180))


def build_board_proxy(size):
    """Simplified Cyton board with the space for the parts on it."""
    _, board_z, _ = _pod_levels()
    board = _oct_prism(BOARD_W, board_z, BOARD_T)
    parts = _oct_prism(BOARD_W - 8.0, board_z + BOARD_T,
                       COMPONENT_SPACE - 1.0)
    return _place(board.union(parts), size)


def build_battery_proxy(size):
    """The LiPo cell on the pod floor, for the checks and renders."""
    floor_top, _, _ = _pod_levels()
    bx, by, bz = BATTERY
    cell = (cq.Workplane("XY").workplane(offset=floor_top).rect(bx, by)
            .extrude(bz))
    return _place(cell, size)


def build_carrier():
    """Electrode carrier, axis along z, bottom at z = 0."""
    tube = cq.Workplane("XY").circle(CARRIER_D / 2).extrude(CARRIER_LENGTH)
    cap = (cq.Workplane("XY").workplane(offset=CARRIER_LENGTH)
           .circle(CAP_D / 2).extrude(CAP_T))
    carrier = tube.union(cap)
    carrier = carrier.faces(">Z").edges().chamfer(0.6)
    wire = (cq.Workplane("XY").workplane(offset=-1).circle(SCREW_HOLE_D / 2)
            .extrude(CARRIER_LENGTH + CAP_T + 2))
    cup = (cq.Workplane("XY").workplane(offset=-1).circle(CUP_D / 2)
           .extrude(CUP_DEPTH + 1))
    carrier = carrier.cut(wire).cut(cup)
    for i in range(GRIP_COUNT):
        angle = 2 * math.pi * i / GRIP_COUNT
        groove = (cq.Workplane("XY").workplane(offset=CARRIER_LENGTH - 1)
                  .center(CAP_D / 2 * math.cos(angle),
                          CAP_D / 2 * math.sin(angle))
                  .circle(GRIP_D / 2).extrude(CAP_T + 2))
        carrier = carrier.cut(groove)
    return carrier


def place_carrier(size, theta, phi):
    """The carrier in a hub, at the contact position: the electrode face on
    the scalp, the carrier bottom ELECTRODE_PROTRUSION above it."""
    p, n = surface(size, theta, phi)
    start = p + n * ELECTRODE_PROTRUSION
    z = V(0, 0, 1)
    axis = z.cross(n)
    shape = build_carrier().val()
    if axis.Length > 1e-9:
        angle = math.degrees(math.acos(max(-1.0, min(1.0, z.dot(n)))))
        shape = shape.rotate(V(0, 0, 0), axis, angle)
    return cq.Workplane("XY").add(shape.translate(start))


def build_all():
    parts = {"carrier": build_carrier()}
    for variant in ("store", "branded"):
        parts[f"cover-{variant}"] = build_cover_print(variant)
    for size in SIZES:
        parts[f"{size}-left"] = build_left(size)
        parts[f"{size}-right"] = build_right(size)
        for variant in ("store", "branded"):
            parts[f"{size}-spine-{variant}"] = build_spine(size, variant)
    return parts


# -------------------------------------------------------------- fit checks

BED = 250.0              # print bed, mm (cube)
MIN_CLEARANCE = 3.0      # frame to scalp, mm
MIN_ENGAGEMENT = 8.0     # carrier length inside the hub at contact, mm


def fit_checks(shapes, overlap, report):
    """Design checks, called by build.py. `report(label, ok, text)`."""
    for size in SIZES:
        left, right = shapes[f"{size}-left"], shapes[f"{size}-right"]
        spine = shapes[f"{size}-spine-store"]
        cover = build_cover(size, "branded").val()
        battery = build_battery_proxy(size).val()
        head = build_head(size).val()
        board = build_board_proxy(size).val()
        nasion, preaur = arcs(size)
        print(f"  size {size}: circumference {SIZES[size]:.0f} mm, "
              f"nasion-inion arc {nasion:.0f} mm, "
              f"preauricular arc {preaur:.0f} mm")
        pairs = {"left/right": (left, right), "left/spine": (left, spine),
                 "right/spine": (right, spine), "spine/board": (spine, board),
                 "cover/spine": (cover, spine), "cover/board": (cover, board),
                 "cover/left": (cover, left),
                 "battery/spine": (battery, spine),
                 "battery/board": (battery, board)}
        for label, (a, b) in pairs.items():
            v = overlap(a, b)
            report(f"{size} {label} overlap", v <= 0.01, f"{v:.3f} mm3")
        for label, part in (("left", left), ("right", right),
                            ("spine", spine)):
            gap = part.distance(head)
            report(f"{size} {label} to scalp", gap >= MIN_CLEARANCE,
                   f"{gap:.1f} mm (min {MIN_CLEARANCE:.0f})")
        for key in (f"{size}-left", f"{size}-spine-store"):
            bb = shapes[key].BoundingBox()
            dims = sorted((bb.xlen, bb.ylen, bb.zlen))
            report(f"{key} in {BED:.0f} mm volume", dims[-1] <= BED,
                   " x ".join(f"{d:.0f}" for d in dims) + " mm")
        worst_engage = 1e9
        for name, (theta, phi) in left_positions().items():
            carrier = place_carrier(size, theta, phi).val()
            v = overlap(carrier, left)
            report(f"{size} carrier {name} / frame", v <= 0.01,
                   f"{v:.3f} mm3")
            gap = carrier.distance(head)
            report(f"{size} carrier {name} / scalp", gap > 0,
                   f"{gap:.1f} mm")
            top = ELECTRODE_PROTRUSION + CARRIER_LENGTH
            hub_lo = HUB_OFFSET - HUB_LENGTH / 2
            hub_hi = HUB_OFFSET + HUB_LENGTH / 2
            engage = min(top, hub_hi) - max(ELECTRODE_PROTRUSION, hub_lo)
            worst_engage = min(worst_engage, engage)
        report(f"{size} carrier engagement", worst_engage >= MIN_ENGAGEMENT,
               f"{worst_engage:.1f} mm (min {MIN_ENGAGEMENT:.0f})")


# ----------------------------------------------------------------- renders

def render_views():
    """Views for render.py: (file, [(part, colour key)], camera, zoom).
    Frame and cover in the film coral, pod in clear glass."""
    m = "M"
    left, right = build_left(m), build_right(m)
    head, board = build_head(m), build_board_proxy(m)
    battery = build_battery_proxy(m)
    carriers = [place_carrier(m, *v) for v in left_positions().values()]
    carriers += [c.mirror("XZ") for c in carriers]
    hero = [(430, 330, 240), (0, 0, 55), (0, 0, 1)]
    back = [(-470, 300, 260), (-20, 0, 50), (0, 0, 1)]
    side = [(30, 520, 120), (0, 0, 40), (0, 0, 1)]
    inside = [(board, "board"), (battery, "board")]
    views = []
    for variant in ("store", "branded"):
        pod = [(build_spine(m, variant), "glass"),
               (build_cover(m, variant), "pink")] + inside
        frame = [(left, "pink"), (right, "pink")] + pod
        views.append((f"frame-{variant}.png", frame, hero, 1.3))
        views.append((f"on-head-{variant}.png",
                      [(head, "head")] + frame +
                      [(c, "glass") for c in carriers], back, 1.15))
    branded = [(left, "pink"), (right, "pink"),
               (build_spine(m, "branded"), "glass"),
               (build_cover(m, "branded"), "pink")] + inside
    views.append(("on-head-front.png", [(head, "head")] + branded +
                  [(c, "glass") for c in carriers], hero, 1.15))
    views.append(("on-head-side.png", [(head, "head")] + branded +
                  [(c, "glass") for c in carriers], side, 1.2))
    mid, ex, ey, ez, _ = _spine_axes(m)
    exploded = [(left.translate((0, 70, 0)), "pink"),
                (right.translate((0, -70, 0)), "pink"),
                (build_spine(m, "branded").translate((ez * 50).toTuple()),
                 "glass"),
                (battery.translate((ez * 50).toTuple()), "board"),
                (board.translate((ez * 85).toTuple()), "board"),
                (build_cover(m, "branded").translate((ez * 120).toTuple()),
                 "pink")]
    for name, (theta, phi) in left_positions().items():
        _, n = surface(m, theta, phi)
        for c, sign in ((place_carrier(m, theta, phi), 1),
                        (place_carrier(m, theta, phi).mirror("XZ"), -1)):
            out = n * 40 if sign == 1 else V(n.x, -n.y, n.z) * 40
            out = out + V(0, sign * 70, 0)
            exploded.append((c.translate(out.toTuple()), "glass"))
    views.append(("exploded.png", exploded,
                  [(-430, 520, 380), (-20, 0, 60), (0, 0, 1)], 1.05))
    views.append(("carrier.png", [(build_carrier(), "glass")],
                  [(90, -110, 70), (0, 0, 18), (0, 0, 1)], 1.3))
    centre = mid + ez * 22
    eye = centre + ez * 240 + ey * 110 - ex * 90
    views.append(("pod-branded.png",
                  [(build_spine(m, "branded"), "glass"),
                   (build_cover(m, "branded"), "pink")] + inside,
                  [eye.toTuple(), centre.toTuple(), ex.toTuple()], 1.2))
    views.append(("pod-open.png",
                  [(build_spine(m, "store"), "glass")] + inside,
                  [eye.toTuple(), centre.toTuple(), ex.toTuple()], 1.2))
    hub_c, hub_n = hub_frame(m, *left_positions()["C3"])
    eye = hub_c + hub_n * 120 + V(0, 0, 30)
    views.append(("hub-names.png", [(left, "pink")],
                  [eye.toTuple(), hub_c.toTuple(), (0, 0, 1)], 1.0))
    return views
