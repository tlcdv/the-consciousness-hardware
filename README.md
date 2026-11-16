# the-consciousness-hardware

Open, 3D-printable parts for thermodynamic computing, neuromorphic engineering, brain-signal
recording and small-satellite education. Every part is generated from code (CadQuery), so you can
read it, change a parameter and build it again.

License: [CERN-OHL-S v2](LICENSE). Attribution is required. If you share a changed design or
sell a product made from it, you must publish your changed source under the same license.

## Designs

| Design | For | State |
|---|---|---|
| [tang-nano-9k-case](designs/tang-nano-9k-case/) | Sipeed Tang Nano 9K FPGA board, used by the [thermospike](https://github.com/tlcdv/thermospike) FPGA reference design | v0.1. Fit checked in CAD only. **Not printed yet.** |

## Two variants of each part

| Variant | Marks on the part | Use |
|---|---|---|
| `store` | Part number and license name only | Print services |
| `branded` | Circled-dot mark and the source URL | Print it yourself |

The shape is the same. All parts share one shape language (`common/style.py`): the same edge
radius and chamfer, and a row of vent slots whose lengths follow a Boltzmann distribution,
exp(-E / T).

## Build

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # Linux, macOS
python build.py           # STL and STEP into designs/<name>/files/, plus fit checks
python build.py --check   # fit checks only
python render.py tang-nano-9k-case
```

The fit checks fail when a part is not one valid solid, when two parts of a case overlap, or when a
case overlaps the simplified board model.

Ready STL and STEP files are attached to each [release](https://github.com/tlcdv/the-consciousness-hardware/releases).

## Honest test state

Each design README has a test table. A design is "printed" only after a real print, and "fit
tested" only after a real board was mounted in it. Until then, measurements that are not in the
manufacturer's drawing are marked as estimates.

## Source location

The source of every design is this repository:
https://github.com/tlcdv/the-consciousness-hardware. See [NOTICE](NOTICE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Outside contributions need a signed
[contributor license agreement](CLA.md).
