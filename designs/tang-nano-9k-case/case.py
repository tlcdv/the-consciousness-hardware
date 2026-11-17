"""Two-part case for the Sipeed Tang Nano 9K FPGA board.

Base and lid. Two M2 screws go through the lid, through the two board holes,
into the base. The split line is the top face of the PCB.

Variants:
  store     no name, no logo, no brand text. For print services.
  branded   compass mark on the lid and the source URL under the base.
            Personal prints only, never sold (see NOTICE).

All dimensions in millimetres. Board coordinates: see board.py.
"""

import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

import board as b  # noqa: E402
from common import style  # noqa: E402

DESIGN_ID = "TN9K-CASE"
VERSION = "0.1.1"
SOURCE_URL = "github.com/tlcdv/the-hardware"
# Camera for the close-up render of the compass mark (render.py).
MARK_VIEW = [(-45, -40, 70), (-25, 0, 11), (0, 0, 1)]

WALL = style.WALL
CLEARANCE = style.BOARD_CLEARANCE
INNER_L = b.LENGTH + 2 * CLEARANCE
INNER_W = b.WIDTH + 2 * CLEARANCE
OUTER_L = INNER_L + 2 * WALL
OUTER_W = INNER_W + 2 * WALL

PCB_TOP = b.PCB_THICKNESS
STANDOFF = 3.0                  # space under the PCB: header spacer 2.5 mm
FLOOR = 2.0
TOP = 2.0
HEADROOM = b.HDMI_HEIGHT + 2.0  # space above the PCB top
Z_FLOOR_TOP = -STANDOFF
Z_BOTTOM = Z_FLOOR_TOP - FLOOR
Z_LID_INNER = PCB_TOP + HEADROOM
Z_TOP = Z_LID_INNER + TOP

LIP_WIDTH = 0.8
LIP_HEIGHT = 1.5
LIP_GAP = 0.2

POST_D = 4.6
PILOT_D = 1.7                   # M2 self-tapping into plastic
SCREW_CLEAR_D = 2.4
SCREW_HEAD_D = 4.2

USB_OPENING = (12.0, 7.0)       # width, height. Room for a USB-C plug body
HDMI_OPENING = (20.0, 10.0)     # room for a common HDMI plug body

END_SUPPORT_X = (-INNER_L / 2, b.HEADER_FIRST_X - 1.45)
END_SUPPORT_Y = (9.0, INNER_W / 2)


def _rounded_block(length, width, z0, z1, radius):
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .rect(length, width)
        .extrude(z1 - z0)
        .edges("|Z")
        .fillet(radius)
    )


def _box(x0, x1, y0, y1, z0, z1):
    return (
        cq.Workplane("XY")
        .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
        .translate((x0, y0, z0))
    )


def _end_openings():
    """Cutters for the USB-C and HDMI openings in the two end walls."""
    usb_w, usb_h = USB_OPENING
    usb_z = PCB_TOP + b.USB_C_HEIGHT / 2
    usb = (
        cq.Workplane("YZ")
        .workplane(offset=-OUTER_L / 2 - 1)
        .center(0, usb_z)
        .slot2D(usb_w, usb_h)
        .extrude(WALL + 2)
    )
    hdmi_w, hdmi_h = HDMI_OPENING
    hdmi_z = PCB_TOP + b.HDMI_HEIGHT / 2
    hdmi = (
        cq.Workplane("YZ")
        .workplane(offset=INNER_L / 2 - 1)
        .center(0, hdmi_z)
        .rect(hdmi_w, hdmi_h)
        .extrude(WALL + 2)
        .edges("|X")
        .fillet(2.0)
    )
    return usb.union(hdmi)


def _engrave_bottom(part, lines, size):
    """Cut text lines into the bottom face, readable from below."""
    # One workplane for every line, taken before any cut. A new workplane per line
    # follows the bounding box of the already cut face and moves the lines (v0.1 bug).
    wp = part.faces("<Z").workplane(centerOption="CenterOfBoundBox")
    step = size * 1.6
    y0 = step * (len(lines) - 1) / 2
    for i, line in enumerate(lines):
        text = wp.center(0, y0 - i * step).text(
            line, size, -style.ENGRAVE_DEPTH, combine=False,
            halign="center", valign="center")
        part = part.cut(text)
    return part


def build_base(variant="store"):
    outer = _rounded_block(OUTER_L, OUTER_W, Z_BOTTOM, PCB_TOP,
                           style.EDGE_RADIUS)
    cavity = _rounded_block(INNER_L, INNER_W, Z_FLOOR_TOP, PCB_TOP + 1,
                            style.EDGE_RADIUS - WALL)
    base = outer.cut(cavity)
    base = base.faces("<Z").edges().chamfer(style.EDGE_CHAMFER)

    # Lip on the inner part of the wall, above the split line.
    lip_outer = _rounded_block(INNER_L + 2 * LIP_WIDTH,
                               INNER_W + 2 * LIP_WIDTH,
                               PCB_TOP, PCB_TOP + LIP_HEIGHT,
                               style.EDGE_RADIUS - WALL + LIP_WIDTH)
    lip_inner = _rounded_block(INNER_L, INNER_W, PCB_TOP - 1,
                               PCB_TOP + LIP_HEIGHT + 1,
                               style.EDGE_RADIUS - WALL)
    base = base.union(lip_outer.cut(lip_inner))

    # Standoffs at the two board holes, with M2 pilot holes.
    for y in (-b.HOLE_Y, b.HOLE_Y):
        post = (
            cq.Workplane("XY").workplane(offset=Z_FLOOR_TOP)
            .center(b.HOLE_X, y).circle(POST_D / 2).extrude(STANDOFF)
        )
        base = base.union(post)
        pilot = (
            cq.Workplane("XY").workplane(offset=Z_BOTTOM + 0.4)
            .center(b.HOLE_X, y).circle(PILOT_D / 2)
            .extrude(PCB_TOP - Z_BOTTOM)
        )
        base = base.cut(pilot)

    # Supports under the USB-C end, outside the header spacer.
    for sign in (-1, 1):
        y0, y1 = sorted((sign * END_SUPPORT_Y[0], sign * END_SUPPORT_Y[1]))
        base = base.union(_box(END_SUPPORT_X[0] - 0.5, END_SUPPORT_X[1],
                               y0, y1, Z_FLOOR_TOP, 0.0))

    # Slots in the floor so soldered header pins pass through.
    xs = b.header_x_positions()
    slot_len = xs[-1] - xs[0] + 3.4
    for y in (-b.HEADER_ROW_Y, b.HEADER_ROW_Y):
        slot = (
            cq.Workplane("XY").workplane(offset=Z_BOTTOM - 1)
            .center((xs[0] + xs[-1]) / 2, y)
            .slot2D(slot_len, 3.4)
            .extrude(FLOOR + 2)
        )
        base = base.cut(slot)

    base = base.cut(_end_openings())

    lines = [f"{DESIGN_ID} v{VERSION}", "CERN-OHL-S-2.0"]
    if variant == "branded":
        lines.append(SOURCE_URL)
    return _engrave_bottom(base, lines, 2.6 if variant == "store" else 2.2)


def build_lid(variant="store"):
    outer = _rounded_block(OUTER_L, OUTER_W, PCB_TOP, Z_TOP,
                           style.EDGE_RADIUS)
    cavity = _rounded_block(INNER_L, INNER_W, PCB_TOP - 1, Z_LID_INNER,
                            style.EDGE_RADIUS - WALL)
    lid = outer.cut(cavity)
    lid = lid.faces(">Z").edges().chamfer(style.EDGE_CHAMFER)

    # Recess for the base lip.
    recess = _rounded_block(INNER_L + 2 * (LIP_WIDTH + LIP_GAP),
                            INNER_W + 2 * (LIP_WIDTH + LIP_GAP),
                            PCB_TOP - 1, PCB_TOP + LIP_HEIGHT + LIP_GAP,
                            style.EDGE_RADIUS - WALL + LIP_WIDTH + LIP_GAP)
    lid = lid.cut(recess)

    # Screw posts that press the board at its holes.
    for y in (-b.HOLE_Y, b.HOLE_Y):
        post = (
            cq.Workplane("XY").workplane(offset=PCB_TOP)
            .center(b.HOLE_X, y).circle(POST_D / 2)
            .extrude(Z_LID_INNER - PCB_TOP + 0.01)
        )
        lid = lid.union(post)
    lid = (
        lid.faces(">Z").workplane(origin=(0, 0, Z_TOP))
        .pushPoints([(b.HOLE_X, -b.HOLE_Y), (b.HOLE_X, b.HOLE_Y)])
        .cboreHole(SCREW_CLEAR_D, SCREW_HEAD_D, TOP)
    )

    # Bars that press the USB-C end of the board. They stay 0.2 mm inside
    # the inner wall face and clear of the rounded lip corner.
    corner = style.EDGE_RADIUS - WALL
    for sign in (-1, 1):
        y0, y1 = sorted((sign * END_SUPPORT_Y[0],
                         sign * (END_SUPPORT_Y[1] - corner - LIP_GAP)))
        lid = lid.union(_box(END_SUPPORT_X[0] + LIP_GAP, END_SUPPORT_X[1],
                             y0, y1, PCB_TOP, Z_LID_INNER + 0.01))

    # Poke holes for the S1 and S2 buttons.
    lid = lid.cut(
        cq.Workplane("XY").workplane(offset=PCB_TOP + 2)
        .pushPoints([(b.BUTTON_X, -b.BUTTON_Y), (b.BUTTON_X, b.BUTTON_Y)])
        .circle(1.6).extrude(Z_TOP)
    )

    # Window over the six user LEDs.
    lid = lid.cut(
        cq.Workplane("XY").workplane(offset=Z_LID_INNER - 0.5)
        .center(b.LED_X, 0)
        .slot2D(b.LED_ROW_LENGTH + 3.0, 3.6, angle=90)
        .extrude(TOP + 1)
    )

    # Signature vents over the FPGA side of the board.
    vents = style.boltzmann_vents(count=11, max_length=16.0, min_length=5.0,
                                  depth=TOP + 1)
    lid = lid.cut(vents.translate((4.0, 0, Z_LID_INNER - 0.5)))

    lid = lid.cut(_end_openings())

    if variant == "branded":
        mark = style.compass_mark(diameter=13.0)
        lid = lid.cut(mark.translate((-25.0, 0,
                                      Z_TOP - style.ENGRAVE_DEPTH)))
    return lid


def build_board_proxy():
    """Simple solid of the board and its tallest parts, for fit checks."""
    pcb = _rounded_block(b.LENGTH, b.WIDTH, 0, b.PCB_THICKNESS,
                         b.CORNER_RADIUS)
    hdmi = _box(b.LENGTH / 2 - 11.0, b.LENGTH / 2, -b.HDMI_WIDTH / 2,
                b.HDMI_WIDTH / 2, PCB_TOP, PCB_TOP + b.HDMI_HEIGHT)
    usb = _box(-b.LENGTH / 2, -b.LENGTH / 2 + 7.3, -b.USB_C_WIDTH / 2,
               b.USB_C_WIDTH / 2, PCB_TOP, PCB_TOP + b.USB_C_HEIGHT)
    spacers = None
    xs = b.header_x_positions()
    for y in (-b.HEADER_ROW_Y, b.HEADER_ROW_Y):
        s = _box(xs[0] - 1.27, xs[-1] + 1.27, y - 1.27, y + 1.27, -2.5, 0)
        spacers = s if spacers is None else spacers.union(s)
    return pcb.union(hdmi).union(usb).union(spacers)


def build_all():
    parts = {}
    for variant in ("store", "branded"):
        parts[f"base-{variant}"] = build_base(variant)
        parts[f"lid-{variant}"] = build_lid(variant)
    return parts
