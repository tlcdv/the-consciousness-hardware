"""Tang Nano 9K board geometry used by the case.

Source: Sipeed dimensional drawing Tang_Nano_9K_3672_size (DXF and PDF,
2022-01-11), https://dl.sipeed.com/shareURL/TANG/Nano%209K/4_Dimensional_drawing
Outline, holes and header positions are read from the DXF. Component
heights are NOT in the drawing. They are estimates and are marked so.

Coordinates: origin at the board centre. X runs along the board, from the
USB-C end (x = -35) to the HDMI end (x = +35). Y runs across. z = 0 is the
bottom face of the PCB. All dimensions in millimetres.
"""

# From the drawing.
LENGTH = 70.0
WIDTH = 26.0
CORNER_RADIUS = 2.5          # read from the PDF outline, not dimensioned
HOLE_DIAMETER = 2.2
HOLE_X = LENGTH / 2 - 2.65   # 2.65 mm from the HDMI end (DXF)
HOLE_Y = 10.4                # 20.8 mm apart (drawing)
HEADER_ROW_Y = 11.41         # rows 22.82 mm apart (DXF)
HEADER_PITCH = 2.54
HEADER_PINS = 24             # per row (2x24P, Sipeed wiki)
HEADER_FIRST_X = -LENGTH / 2 + 2.55   # first pin, USB-C end (DXF)

# Read from the PDF drawing (pad positions), +-0.3 mm.
BUTTON_X = -LENGTH / 2 + 3.5           # S1 and S2, next to USB-C
BUTTON_Y = 8.15
LED_X = -LENGTH / 2 + 19.0             # row of 6 user LEDs
LED_ROW_LENGTH = 8.0
USB_C_WIDTH = 8.9                      # receptacle shell, centred on y = 0
HDMI_WIDTH = 15.0                      # receptacle shell, centred on y = 0

# Estimates. Not in the drawing. Check with a real board before printing.
PCB_THICKNESS = 1.6
USB_C_HEIGHT = 3.3                     # above the PCB top
HDMI_HEIGHT = 6.0                      # above the PCB top, tallest part
BOTTOM_COMPONENT_HEIGHT = 1.5          # below the PCB


def header_x_positions():
    return [HEADER_FIRST_X + i * HEADER_PITCH for i in range(HEADER_PINS)]
