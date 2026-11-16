# Contributing

## Rules for every design

1. One folder per design in `designs/<name>/`, with `case.py` (or the main model file), a README
   with the test table, and `renders/`.
2. Use `common/style.py` for edge radius, chamfer, wall, clearance and vents.
3. Each design builds two variants: `store` (part number and license name only) and `branded`
   (project mark). Only `store` files and the logo-free renders in `renders/listing/` ever go to a
   print service. `branded` is for personal prints only. See NOTICE, "Names and logos".
4. Board measurements come from the manufacturer's drawing. Name the drawing in the code.
   Mark every other measurement as an estimate.
5. Run `python render.py <design>` and commit the renders. Every design README shows all renders
   in an "Images" table. Renders use the house look in `render.py` (near black background,
   orange `#ff6f40`, cream, near white edge lines, main logo at the bottom right).
6. `python build.py` must print "all checks passed" before a pull request.
7. The test table says only what was really done. "Printed" and "Fit tested" need a photo in the
   pull request.
8. Brain-signal designs are for recording only. No stimulation parts. No medical claims.

## Pull requests

Write "I agree to the Contributor License Agreement in CLA.md" in the description. See
[CLA.md](CLA.md).
