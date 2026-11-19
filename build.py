"""Build every design: export STL and STEP files and run the fit checks.

Usage:
    python build.py            build and check every design
    python build.py --check    check only, write no files

A check fails when a part is not one valid solid, when two parts of a case
overlap, or when a case overlaps the board proxy. A design that defines
fit_checks() runs its own checks instead of the case checks.
"""

import argparse
import importlib.util
import os
import sys

import cadquery as cq

ROOT = os.path.dirname(os.path.abspath(__file__))
DESIGNS = os.path.join(ROOT, "designs")
OVERLAP_LIMIT_MM3 = 0.01


def design_file(name):
    """designs/<name>/design.py, or case.py for the older designs."""
    for file in ("design.py", "case.py"):
        path = os.path.join(DESIGNS, name, file)
        if os.path.exists(path):
            return path
    return None


def load_design(name):
    path = design_file(name)
    spec = importlib.util.spec_from_file_location(f"design_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def solid_of(part):
    shape = part.val()
    if not shape.isValid():
        raise ValueError("shape is not valid")
    solids = part.solids().vals()
    if len(solids) != 1:
        raise ValueError(f"expected 1 solid, found {len(solids)}")
    return shape


def overlap(a, b):
    common = a.intersect(b)
    return common.Volume() if common.Solids() else 0.0


def check(name, module, parts):
    failures = []
    shapes = {}
    for key, part in parts.items():
        try:
            shapes[key] = solid_of(part)
        except ValueError as error:
            failures.append(f"{name}/{key}: {error}")
    if hasattr(module, "fit_checks"):
        def report(label, ok, text):
            print(f"  {label:34s} {text:28s} {'ok' if ok else 'FAIL'}")
            if not ok:
                failures.append(f"{name}: {label} {text}")
        module.fit_checks(shapes, overlap, report)
        print_sizes(shapes)
        return failures
    proxy = module.build_board_proxy().val()
    for variant in ("store", "branded"):
        base, lid = shapes.get(f"base-{variant}"), shapes.get(f"lid-{variant}")
        if base is None or lid is None:
            continue
        pairs = {"base/lid": (base, lid), "base/board": (base, proxy),
                 "lid/board": (lid, proxy)}
        for label, (a, b) in pairs.items():
            volume = overlap(a, b)
            status = "ok" if volume <= OVERLAP_LIMIT_MM3 else "FAIL"
            print(f"  {variant:8s} {label:11s} overlap {volume:8.3f} mm3  {status}")
            if status == "FAIL":
                failures.append(f"{name}/{variant}: {label} overlap {volume:.3f} mm3")
    print_sizes(shapes)
    return failures


def print_sizes(shapes):
    for key, shape in shapes.items():
        bb = shape.BoundingBox()
        print(f"  {key:17s} {bb.xlen:6.2f} x {bb.ylen:6.2f} x {bb.zlen:6.2f} mm"
              f"  volume {shape.Volume() / 1000:6.2f} cm3")


def export(name, parts):
    out = os.path.join(DESIGNS, name, "files")
    os.makedirs(out, exist_ok=True)
    for key, part in parts.items():
        stem = os.path.join(out, f"{name}-{key}")
        cq.exporters.export(part, stem + ".stl", tolerance=0.02,
                            angularTolerance=0.1)
        cq.exporters.export(part, stem + ".step")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    failures = []
    for name in sorted(os.listdir(DESIGNS)):
        if design_file(name) is None:
            continue
        print(name)
        module = load_design(name)
        parts = module.build_all()
        failures += check(name, module, parts)
        if not args.check:
            export(name, parts)
    if failures:
        print("FAILED:")
        for line in failures:
            print("  " + line)
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
