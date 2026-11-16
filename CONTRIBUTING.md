# Contributing

## Rules for every design

1. One folder per design in `designs/<name>/`, with `case.py` (or the main model file), a README
   with the test table, and `renders/`.
2. Use `common/style.py` for edge radius, chamfer, wall, clearance and vents.
3. Each design builds two variants: `store` (part number and license name only) and `branded`.
4. Board measurements come from the manufacturer's drawing. Name the drawing in the code.
   Mark every other measurement as an estimate.
5. `python build.py` must print "all checks passed" before a pull request.
6. The test table says only what was really done. "Printed" and "Fit tested" need a photo in the
   pull request.
7. Brain-signal designs are for recording only. No stimulation parts. No medical claims.

## Pull requests

Write "I agree to the Contributor License Agreement in CLA.md" in the description. See
[CLA.md](CLA.md).
