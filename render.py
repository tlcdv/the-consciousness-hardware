"""Render PNG previews of a design with pyvista (VTK), off screen.

House look, the same as the project's films and banners: near black
background, parts in the brand orange and cream, thin near white edge lines,
no text in the image, and the main logo at the bottom right. The page or
README carries the caption.

Each render is written twice:
  renders/<view>.png          with the logo, for the repository, the website
                              and social posts
  renders/listing/<view>.png  without the logo, for print service listings
                              (no brand mark on what a print service sells)

Usage: python render.py tang-nano-9k-case
Writes designs/<name>/renders/*.png. These are renders of the CAD model,
not photos of a print.
"""

import importlib.util
import os
import sys

import numpy as np
import pyvista as pv
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from common.style import COLOURS  # noqa: E402

BACKGROUND = COLOURS["background"]
CORAL = COLOURS["coral"]
CREAM = COLOURS["cream"]
LINE = COLOURS["near_white"]
BOARD = "#1b1d22"          # dark board, read through its edge lines
LOGO = os.path.join(ROOT, "assets", "logo-main.png")
LOGO_HEIGHT = 0.12         # share of the image height
LOGO_MARGIN = 0.035        # share of the image height


def load(name):
    path = os.path.join(ROOT, "designs", name, "case.py")
    spec = importlib.util.spec_from_file_location(f"design_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mesh(part, offset=(0, 0, 0)):
    verts, tris = part.val().tessellate(0.03, 0.15)
    points = np.array([(p.x, p.y, p.z) for p in verts]) + np.array(offset)
    faces = np.hstack([np.full((len(tris), 1), 3), np.array(tris)]).ravel()
    return pv.PolyData(points, faces).clean().compute_normals(
        feature_angle=25, split_vertices=True, auto_orient_normals=True)


def add_part(plotter, surface, colour, line_opacity=0.55):
    plotter.add_mesh(surface, color=colour, smooth_shading=True,
                     ambient=0.18, diffuse=0.8, specular=0.35,
                     specular_power=30)
    edges = surface.extract_feature_edges(feature_angle=35,
                                          boundary_edges=True,
                                          non_manifold_edges=False,
                                          manifold_edges=False)
    plotter.add_mesh(edges, color=LINE, line_width=1.6, opacity=line_opacity)


def draw(items, path, position, zoom=1.35):
    plotter = pv.Plotter(off_screen=True, window_size=(1600, 1000),
                         lighting="none")
    plotter.set_background(BACKGROUND)
    plotter.add_light(pv.Light(position=(-150, -200, 260), intensity=0.85,
                               light_type="scene light"))
    plotter.add_light(pv.Light(position=(220, 120, 120), intensity=0.35,
                               light_type="scene light"))
    plotter.add_light(pv.Light(position=(0, 260, -80), intensity=0.25,
                               light_type="scene light"))
    for surface, colour, *rest in items:
        add_part(plotter, surface, colour, *rest)
    plotter.camera_position = position
    plotter.camera.zoom(zoom)
    plotter.enable_anti_aliasing("ssaa")
    folder, name = os.path.split(path)
    listing = os.path.join(folder, "listing")
    os.makedirs(listing, exist_ok=True)
    plain = os.path.join(listing, name)
    plotter.screenshot(plain)
    plotter.close()
    add_logo(plain, path)


def add_logo(source, target):
    """Paste the main logo at the bottom right of a render."""
    image = Image.open(source).convert("RGBA")
    size = int(image.height * LOGO_HEIGHT)
    margin = int(image.height * LOGO_MARGIN)
    logo = Image.open(LOGO).convert("RGBA").resize((size, size),
                                                   Image.LANCZOS)
    image.alpha_composite(logo, (image.width - size - margin,
                                 image.height - size - margin))
    image.convert("RGB").save(target, optimize=True)


def main(name):
    module = load(name)
    out = os.path.join(ROOT, "designs", name, "renders")
    os.makedirs(out, exist_ok=True)
    above = [(-90, -120, 110), (0, 0, 2), (0, 0, 1)]
    below = [(-90, -120, -110), (0, 0, 0), (0, 0, 1)]
    exploded = [(-110, -140, 120), (0, 0, 8), (0, 0, 1)]
    board = mesh(module.build_board_proxy())
    for variant in ("store", "branded"):
        lid, base = module.build_lid(variant), module.build_base(variant)
        draw([(mesh(lid), CORAL)], os.path.join(out, f"lid-{variant}.png"),
             above)
        draw([(mesh(base), CREAM), (board, BOARD, 0.9),
              (mesh(lid, (0, 0, 24)), CORAL)],
             os.path.join(out, f"exploded-{variant}.png"), exploded,
             zoom=1.25)
        draw([(mesh(base), CREAM)],
             os.path.join(out, f"base-bottom-{variant}.png"), below)
    draw([(mesh(module.build_base("store")), CREAM), (board, BOARD, 0.9)],
         os.path.join(out, "base-with-board.png"), above)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tang-nano-9k-case")
