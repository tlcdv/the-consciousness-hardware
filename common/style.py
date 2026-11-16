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

# Recommended material colours. The brand tokens of the project.
COLOURS = {
    "cream": "#f3ead8",
    "coral": "#f58c6e",
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


def circled_dot(outer_diameter=12.0, ring_width=1.2, dot_diameter=3.6,
                depth=ENGRAVE_DEPTH):
    """A cutting solid for the circled-dot project mark (branded variants only).

    Centred on the origin, from z = 0 to z = depth.
    """
    ring = (
        cq.Workplane("XY")
        .circle(outer_diameter / 2)
        .circle(outer_diameter / 2 - ring_width)
        .extrude(depth)
    )
    dot = cq.Workplane("XY").circle(dot_diameter / 2).extrude(depth)
    return ring.union(dot)
