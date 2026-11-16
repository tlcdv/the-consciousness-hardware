"""Render PNG previews of a design with pyvista (VTK), off screen.

Usage: python render.py tang-nano-9k-case
Writes designs/<name>/renders/*.png. These are renders of the CAD model,
not photos of a print.
"""

import importlib.util
import os
import sys

import numpy as np
import pyvista as pv

ROOT = os.path.dirname(os.path.abspath(__file__))
CREAM = "#f3ead8"
CORAL = "#f58c6e"
BOARD = "#1f6b3a"


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
    return pv.PolyData(points, faces).compute_normals(feature_angle=30)


def draw(items, path, position, title):
    plotter = pv.Plotter(off_screen=True, window_size=(1400, 900))
    plotter.set_background("white")
    for surface, colour in items:
        plotter.add_mesh(surface, color=colour, smooth_shading=True,
                         specular=0.2, ambient=0.25)
    plotter.add_text(title, font_size=11, color="black")
    plotter.camera_position = position
    plotter.camera.zoom(1.3)
    plotter.enable_anti_aliasing("ssaa")
    plotter.screenshot(path)
    plotter.close()


def main(name):
    module = load(name)
    out = os.path.join(ROOT, "designs", name, "renders")
    os.makedirs(out, exist_ok=True)
    above = [(-90, -120, 110), (0, 0, 2), (0, 0, 1)]
    below = [(-90, -120, -110), (0, 0, 0), (0, 0, 1)]
    for variant in ("store", "branded"):
        colour = CORAL if variant == "branded" else CREAM
        lid, base = module.build_lid(variant), module.build_base(variant)
        draw([(mesh(lid), colour)], os.path.join(out, f"lid-{variant}.png"),
             above, f"Lid, {variant} variant (render)")
        draw([(mesh(base), CREAM), (mesh(module.build_board_proxy()), BOARD),
              (mesh(lid, (0, 0, 24)), colour)],
             os.path.join(out, f"exploded-{variant}.png"),
             [(-110, -140, 120), (0, 0, 8), (0, 0, 1)],
             f"Exploded view, {variant} variant (simplified board in green)")
        draw([(mesh(base), CREAM)], os.path.join(out, f"base-bottom-{variant}.png"),
             below, f"Base from below, {variant} variant (render)")
    draw([(mesh(module.build_base("store")), CREAM),
          (mesh(module.build_board_proxy()), BOARD)],
         os.path.join(out, "base-with-board.png"), above,
         "Base with the simplified board (render)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tang-nano-9k-case")
