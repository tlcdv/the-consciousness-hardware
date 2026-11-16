"""Shared shape language for every design in this repository.

Every part uses the same edge radius, the same chamfer and the same vent
pattern, so the parts look like one family without a logo. The vent pattern
is a row of slots whose lengths follow a Boltzmann distribution: the slot for
energy level E has a length proportional to exp(-E / T).

All dimensions are in millimetres.
"""

import math

import cadquery as cq

# Outer vertical edges of every enclosure.
EDGE_RADIUS = 3.0
# Top and bottom outer edges.
EDGE_CHAMFER = 0.8
# Default wall and floor thickness for printed nylon (MJF or SLS) and PETG.
WALL = 2.0
# Clearance between a board edge and the inner wall.
BOARD_CLEARANCE = 0.4
# Engraving depth for text and marks.
ENGRAVE_DEPTH = 0.6

# Brand tokens for renders and recommended material colours. The same values
# as the project's films and banners: near black background, near white, and
# the orange used for 3D and video (never the lighter web orange in renders).
COLOURS = {
    "background": "#050506",
    "near_white": "#f5f5f2",
    "cream": "#f3ead8",
    "coral": "#ff6f40",
}


def boltzmann_lengths(count, max_length, min_length, temperature=1.0):
    """Return slot lengths for `count` slots, symmetric around the centre.

    The centre slot is energy 0. Slot i is energy (i - centre)^2 / 2, a
    harmonic well, so the lengths trace exp(-E / T), a Gaussian bell.
    Lengths are scaled into [min_length, max_length].
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    if not 0 < min_length <= max_length:
        raise ValueError("need 0 < min_length <= max_length")
    centre = (count - 1) / 2
    spread = max(centre, 1.0)
    weights = []
    for i in range(count):
        energy = ((i - centre) / spread) ** 2 * 2.0
        weights.append(math.exp(-energy / temperature))
    low, high = min(weights), max(weights)
    span = high - low
    lengths = []
    for w in weights:
        fraction = 1.0 if span == 0 else (w - low) / span
        lengths.append(min_length + fraction * (max_length - min_length))
    return lengths


def boltzmann_vents(count=11, pitch=2.6, slot_width=1.4, max_length=16.0,
                    min_length=5.0, depth=10.0, temperature=1.0):
    """A cutting solid for the signature vent pattern.

    The slots run along Y and are spaced along X. The solid is centred on
    the origin in X and Y and extends from z = 0 to z = depth. Subtract it
    from a part after you move it into place.
    """
    lengths = boltzmann_lengths(count, max_length, min_length, temperature)
    x0 = -pitch * (count - 1) / 2
    cutter = None
    for i, length in enumerate(lengths):
        slot = (
            cq.Workplane("XY")
            .center(x0 + i * pitch, 0)
            .slot2D(length, slot_width, angle=90)
            .extrude(depth)
        )
        cutter = slot if cutter is None else cutter.union(slot)
    return cutter


# Thinnest engraved line a nylon print service (MJF, SLS) keeps.
MIN_LINE = 0.6


def _ring(r_out, width, depth):
    return (cq.Workplane("XY").circle(r_out).circle(r_out - width)
            .extrude(depth))


def compass_mark(diameter=13.0, depth=ENGRAVE_DEPTH):
    """A cutting solid for the project mark (branded variants only).

    A simplified engraving of the main logo, the compass dial in
    assets/logo-main.png: outer rim, second ring, eight point star, hub ring,
    centre dot and a shallow sweep sector from 0 to 60 degrees. The degree
    numbers and the fine ticks are left out because they are thinner than
    MIN_LINE at this size. Never put this mark on a `store` variant (NOTICE).

    Centred on the origin, from z = 0 to z = depth.
    """
    r = diameter / 2
    cut = _ring(r, 0.8, depth)
    cut = cut.union(_ring(r - 1.6, MIN_LINE, depth))
    cut = cut.union(_ring(2.0, MIN_LINE, depth))
    cut = cut.union(cq.Workplane("XY").circle(0.6).extrude(depth))
    for i in range(8):
        angle = math.radians(90 - i * 45)
        length = (r - 1.8) if i % 2 == 0 else (r - 3.2)
        half = 0.55 if i % 2 == 0 else 0.45
        tip = (length * math.cos(angle), length * math.sin(angle))
        bx, by = 2.0 * math.cos(angle), 2.0 * math.sin(angle)
        px, py = -math.sin(angle) * half, math.cos(angle) * half
        kite = (cq.Workplane("XY")
                .polyline([(bx + px, by + py), tip, (bx - px, by - py)])
                .close().extrude(depth))
        cut = cut.union(kite)
    points = [(0, 0)]
    for k in range(13):
        angle = math.radians(90 - k * 5)
        points.append(((r - 1.6) * math.cos(angle),
                       (r - 1.6) * math.sin(angle)))
    sweep = (cq.Workplane("XY").polyline(points).close()
             .extrude(depth / 2).translate((0, 0, depth / 2)))
    return cut.union(sweep)
