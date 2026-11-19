"""Make the demo data of the Open EEG Viewer from PhysioNet EEGMMIDB S001R01 (eyes open) and S001R02
(eyes closed): the 16 frame channels, int16 little endian, sample major (t, ch), 0.1 uV per unit,
plus a JSON meta file. Usage: python make_demo_data.py <folder with the two EDF files> data
The EDF files: https://physionet.org/files/eegmmidb/1.0.0/S001/ (ODC-By 1.0)."""
import json, sys, struct
from pathlib import Path
import numpy as np
src, out = Path(sys.argv[1]), Path(sys.argv[2])
WANT = ["Fp1","Fp2","F7","F3","F4","F8","T7","C3","C4","T8","P7","P3","P4","P8","O1","O2"]
def read_edf(p):
    b = p.read_bytes()
    nrec = int(b[236:244]); dur = float(b[244:252]); ns = int(b[252:256])
    off = 256
    def field(w):
        nonlocal off
        v = [b[off+i*w: off+(i+1)*w].decode().strip() for i in range(ns)]; off += w*ns; return v
    lab = field(16); field(80); dim = field(8)
    pmin = list(map(float, field(8))); pmax = list(map(float, field(8)))
    dmin = list(map(float, field(8))); dmax = list(map(float, field(8)))
    field(80); nsr = list(map(int, field(8))); field(32)
    raw = np.frombuffer(b[off:], dtype="<i2")
    rl = sum(nsr); raw = raw[: nrec*rl].reshape(nrec, rl)
    n = nsr[0]; sig = [k for k in range(ns) if nsr[k] == n]
    starts = np.cumsum([0]+nsr[:-1])
    raw = np.stack([raw[:, starts[k]:starts[k]+n].reshape(-1) for k in sig]).astype(np.float64)
    lab = [lab[k] for k in sig]; dim = [dim[k] for k in sig]
    pmin = [pmin[k] for k in sig]; pmax = [pmax[k] for k in sig]; dmin = [dmin[k] for k in sig]; dmax = [dmax[k] for k in sig]
    gain = (np.array(pmax)-np.array(pmin))/(np.array(dmax)-np.array(dmin))
    x = (raw - np.array(dmin)[:,None])*gain[:,None] + np.array(pmin)[:,None]
    lab = [l.rstrip(".").replace(".", "") for l in lab]
    return lab, dim, n/dur, x
parts = []
for r in ("S001R01.edf", "S001R02.edf"):
    lab, dim, fs, x = read_edf(src / r)
    norm = {l.lower(): i for i, l in enumerate(lab)}
    idx = [norm[w.lower()] for w in WANT]
    print(r, fs, dim[idx[0]], x.shape)
    parts.append(x[idx])
x = np.concatenate(parts, axis=1)
q = np.clip(np.round(x*10), -32768, 32767).astype("<i2")
out.mkdir(parents=True, exist_ok=True)
(out/"physionet-s001-r01-r02.bin").write_bytes(q.T.copy().tobytes())
meta = {"fs": fs, "channels": WANT, "scale_uv": 0.1, "samples": int(x.shape[1]),
        "segments": [{"label": "Eyes open", "start_s": 0, "end_s": parts[0].shape[1]/fs},
                     {"label": "Eyes closed", "start_s": parts[0].shape[1]/fs, "end_s": x.shape[1]/fs}],
        "source": "PhysioNet EEG Motor Movement/Imagery Dataset v1.0.0, subject S001, runs 1 and 2",
        "doi": "10.13026/C28G6P", "license": "ODC-By 1.0"}
(out/"physionet-s001-r01-r02.json").write_text(json.dumps(meta, indent=1))
# quick alpha check O1/O2
from numpy.fft import rfft, rfftfreq
for k, seg in enumerate(parts):
    o = seg[-2:].mean(0); f = rfftfreq(len(o), 1/fs); p = np.abs(rfft(o-o.mean()))**2
    a = p[(f>=8)&(f<=12)].sum()/p[(f>=1)&(f<=30)].sum()
    print("segment", k, "alpha share O1/O2", round(a,3))
