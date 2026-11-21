/* Open EEG Viewer, theconsciousness.ai/hardware/eeg-viewer/
   MIT licence. One file, no dependencies, no server. EEG never leaves the browser.

   Sources
   - Demo: PhysioNet EEG Motor Movement/Imagery Dataset v1.0.0, subject S001, runs 1 (eyes open)
     and 2 (eyes closed), the 16 frame channels, ODC-By 1.0, doi 10.13026/C28G6P.
   - Muse: Web Bluetooth. Protocol as in muse-js by Uri Shaked (MIT), github.com/urish/muse-js.
     Service 0xfe8d, control 273e0001, EEG 273e0003..0006 (TP9, AF7, AF8, TP10), 12 samples of
     12 bit per notification, uV = 0.48828125 * (n - 0x800), 256 Hz. Commands h, p21, s, d.
   - Cyton: Web Serial, 115200 baud. Packet 33 bytes, 0xA0 header, 8 channels of 24 bit signed
     big endian, footer 0xCX. uV per count = 4.5 / 24 / (2^23 - 1) * 1e6 (gain 24).
     With the Daisy, odd sample numbers carry channels 1 to 8 and even ones 9 to 16, so each
     channel arrives at 125 Hz. Source: docs.openbci.com/Cyton/CytonDataFormat/. Commands s, v, C, b.
     The reply to C tells 8 from 16 channels (docs.openbci.com/Cyton/CytonSDK/).
   - NPG Lite (Upside Down Labs Neuro PlayGround Lite): Web Bluetooth. Layout read from the maker's
     firmware Chords-Arduino-Firmware/NPG-LITE-BLE (GPL-3.0, read for the facts only, no code copied):
     service 4fafc201-1fb5-459e-8fcc-c5c9c331914b, data beb5483e-36e1-4688-b7f5-ea07361b26a8 (notify),
     control 0000ff01-0000-1000-8000-00805f9b34fb (text commands START, STOP), battery
     f633d0ec-46b4-43c1-a39f-1ca06d0602e1 (one byte, percent). 500 Hz, 10 samples per notification,
     each sample = 1 counter byte + 2 bytes per channel, 12 bit ADC value, most significant byte first.
     Device name NPG-Lite-3CH or NPG-Lite-6CH. The analog gain is not published, so values are ADC
     counts centred on 2048, not microvolts. NOT tested with a real board.
   The decoders are checked against the test vectors of muse-js and OpenBCI_NodeJS_Utilities,
   see test/codec-test.js in the source folder.
*/
// ---------- decoders, kept apart from the page so they can be tested against reference data ----------
var EEGVCodec = (function () {
  "use strict";
  var MUSE_UV = 0.48828125;                                  // muse-js decodeEEGSamples
  var CYTON_UV = 4.5 / 24 / (Math.pow(2, 23) - 1) * 1e6;     // OpenBCI scale factor, gain 24
  // Muse control command: length byte, ASCII command, newline (muse-js encodeCommand)
  function museCmd(s) {
    var e = new Uint8Array(s.length + 2); e[0] = s.length + 1;
    for (var i = 0; i < s.length; i++) e[i + 1] = s.charCodeAt(i);
    e[s.length + 1] = 10; return e;
  }
  // 12 bit unsigned samples, packed two in three bytes (muse-js decodeUnsigned12BitData)
  function muse12(b) {
    var out = [];
    for (var i = 0; i < b.length; i++) {
      if (i % 3 === 0) out.push((b[i] << 4) | (b[i + 1] >> 4));
      else { out.push(((b[i] & 0xf) << 8) | b[i + 1]); i++; }
    }
    return out;
  }
  // one EEG notification: 2 byte sequence number, then 18 bytes of 12 samples, to microvolts
  function museDecode(bytes) {
    return muse12(bytes.subarray(2)).map(function (n) { return MUSE_UV * (n - 0x800); });
  }
  // 24 bit two's complement, most significant byte first (OpenBCI interpret24bitAsInt32)
  function int24(b, o) {
    var v = (b[o] << 16) | (b[o + 1] << 8) | b[o + 2];
    return (v & 0x800000) ? v - 0x1000000 : v;
  }
  // Cyton stream parser. With the Daisy, an odd sample number holds channels 1 to 8 and the next
  // even one channels 9 to 16, as in OpenBCI _finalizeNewSampleForDaisy. An unpaired packet is
  // dropped and counted.
  function cytonParser(daisy) {
    var buf = new Uint8Array(0), pend = null, st = { packets: 0, missed: 0, skippedBytes: 0 };
    function feed(chunk) {
      var nb = new Uint8Array(buf.length + chunk.length); nb.set(buf); nb.set(chunk, buf.length); buf = nb;
      var frames = [], i = 0;
      while (i + 33 <= buf.length) {
        if (buf[i] !== 0xa0 || (buf[i + 32] & 0xf0) !== 0xc0) { i++; st.skippedBytes++; continue; }
        var sn = buf[i + 1], ch = new Array(8);
        for (var k = 0; k < 8; k++) ch[k] = int24(buf, i + 2 + k * 3) * CYTON_UV;
        st.packets++;
        if (!daisy) frames.push(ch);
        else if (sn % 2 === 1) { if (pend) st.missed++; pend = ch; }
        else if (pend) { frames.push(pend.concat(ch)); pend = null; }
        else st.missed++;
        i += 33;
      }
      buf = buf.slice(i);
      return frames;
    }
    return { feed: feed, stats: st };
  }
  // reply to the C command (Cyton SDK): "16$$$" or "daisy attached16$$$" means 16 channels,
  // "no daisy to attach!8$$$" means 8. null when the reply is not there yet.
  function daisyFromReply(t) {
    if (/no daisy to attach/i.test(t) || /(^|[^0-9])8\$\$\$/.test(t)) return false;
    if (/16\$\$\$/.test(t)) return true;
    return null;
  }
  // NPG Lite notification: NPG_BLOCK samples, each a counter byte and nch big endian 12 bit values.
  // The channel count follows from the length. Values come back centred on 2048 (ADC counts).
  // `state.last` keeps the last counter, so a gap between notifications is counted in `state.missed`.
  var NPG_BLOCK = 10;
  function npgChannels(len) {
    if (!len || len % NPG_BLOCK) return 0;
    var per = len / NPG_BLOCK;
    return per >= 3 && (per - 1) % 2 === 0 ? (per - 1) / 2 : 0;
  }
  function npgDecode(bytes, state) {
    var nch = npgChannels(bytes.length), per = 1 + 2 * nch, frames = [];
    if (!nch) { if (state) state.bad = (state.bad || 0) + 1; return frames; }
    for (var s = 0; s < NPG_BLOCK; s++) {
      var o = s * per, cnt = bytes[o];
      if (state) {
        if (state.last !== undefined && state.last !== null) state.missed = (state.missed || 0) + ((cnt - state.last - 1 + 256) % 256);
        state.last = cnt;
      }
      var fr = new Array(nch);
      for (var c = 0; c < nch; c++) fr[c] = ((bytes[o + 1 + 2 * c] << 8) | bytes[o + 2 + 2 * c]) - 2048;
      frames.push(fr);
    }
    return frames;
  }
  return { MUSE_UV: MUSE_UV, CYTON_UV: CYTON_UV, museCmd: museCmd, muse12: muse12, museDecode: museDecode,
    int24: int24, cytonParser: cytonParser, daisyFromReply: daisyFromReply,
    NPG_BLOCK: NPG_BLOCK, npgChannels: npgChannels, npgDecode: npgDecode };
})();
if (typeof module !== "undefined" && module.exports) module.exports = EEGVCodec;

(function () {
  "use strict";
  if (typeof document === "undefined") return;
  var root = document.getElementById("eegv");
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var BASE = root.getAttribute("data-base") || "/public/data/eeg-live/";

  // ---------- colours (the canvas paints its own dark panel, like every console) ----------
  var C = {
    ink: "#0a0b0d", line: "rgba(236,233,226,0.12)", line2: "rgba(236,233,226,0.26)",
    text: "#f0eee6", dim: "rgba(240,238,230,0.56)", coral: "#e64254", gold: "#d6ab71",
    live: "#6fbf73", bad: "#e2574c"
  };
  var MONO = '"IBM Plex Mono", ui-monospace, Menlo, monospace';

  // ---------- 10-20 positions on a sphere (polar from Cz, azimuth from the nose, + is left) ----------
  function sph(p, a) { p *= Math.PI / 180; a *= Math.PI / 180; return [Math.sin(p) * Math.cos(a), Math.sin(p) * Math.sin(a), Math.cos(p)]; }
  function mid(u, v) { var m = [u[0] + v[0], u[1] + v[1], u[2] + v[2]], n = Math.hypot(m[0], m[1], m[2]); return [m[0] / n, m[1] / n, m[2] / n]; }
  function toPA(v) { return [Math.acos(Math.max(-1, Math.min(1, v[2]))) * 180 / Math.PI, Math.atan2(v[1], v[0]) * 180 / Math.PI]; }
  var POS = {
    Fp1: [72, 18], Fp2: [72, -18], F7: [72, 54], F8: [72, -54], T7: [72, 90], T8: [72, -90],
    P7: [72, 126], P8: [72, -126], O1: [72, 162], O2: [72, -162], C3: [36, 90], C4: [36, -90],
    AF7: [72, 36], AF8: [72, -36], TP9: [100, 112], TP10: [100, -112],
    Fpz: [72, 0], Oz: [72, 180]
  };
  POS.F3 = toPA(mid(sph(36, 0), sph(72, 54)));
  POS.F4 = toPA(mid(sph(36, 0), sph(72, -54)));
  POS.P3 = toPA(mid(sph(36, 180), sph(72, 126)));
  POS.P4 = toPA(mid(sph(36, 180), sph(72, -126)));

  // Channel order for the frame on the Cyton: inputs 1 to 8 on the Cyton, 9 to 16 on the Daisy.
  // The first 8 cover front, centre, side and back, so the Cyton alone still gives a useful map.
  var CYTON_LABELS = ["Fp1", "Fp2", "C3", "C4", "P7", "P8", "O1", "O2", "F7", "F8", "F3", "F4", "T7", "T8", "P3", "P4"];
  var MUSE_LABELS = ["TP9", "AF7", "AF8", "TP10"];
  // Channel order for the open EEG band: input 1 on the forehead, 2 and 3 at the back.
  var NPG_LABELS = ["Fp1", "O1", "O2", "Fp2", "Fpz", "Oz"];
  var BANDS = [
    { k: "delta", n: "Delta", lo: 1, hi: 4 }, { k: "theta", n: "Theta", lo: 4, hi: 8 },
    { k: "alpha", n: "Alpha", lo: 8, hi: 13 }, { k: "beta", n: "Beta", lo: 13, hi: 30 },
    { k: "gamma", n: "Gamma", lo: 30, hi: 40 }
  ];

  // ---------- filters (RBJ biquads, direct form 1) ----------
  function biquad(type, f0, fs, q) {
    var w = 2 * Math.PI * f0 / fs, cw = Math.cos(w), al = Math.sin(w) / (2 * q), b0, b1, b2, a0, a1, a2;
    if (type === "hp") { b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = (1 + cw) / 2; }
    else if (type === "lp") { b0 = (1 - cw) / 2; b1 = 1 - cw; b2 = (1 - cw) / 2; }
    else { b0 = 1; b1 = -2 * cw; b2 = 1; }
    a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al;
    return { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: a1 / a0, a2: a2 / a0, x1: 0, x2: 0, y1: 0, y2: 0 };
  }
  function run(f, x) {
    var y = f.b0 * x + f.b1 * f.x1 + f.b2 * f.x2 - f.a1 * f.y1 - f.a2 * f.y2;
    f.x2 = f.x1; f.x1 = x; f.y2 = f.y1; f.y1 = y; return y;
  }

  // ---------- FFT (radix 2, in place) ----------
  function fft(re, im) {
    var n = re.length, i, j, k, l, t;
    for (i = 1, j = 0; i < n; i++) {
      var bit = n >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) { t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
    }
    for (l = 2; l <= n; l <<= 1) {
      var ang = -2 * Math.PI / l, wr = Math.cos(ang), wi = Math.sin(ang);
      for (i = 0; i < n; i += l) {
        var cr = 1, ci = 0;
        for (k = 0; k < l / 2; k++) {
          var ar = re[i + k + l / 2] * cr - im[i + k + l / 2] * ci, ai = re[i + k + l / 2] * ci + im[i + k + l / 2] * cr;
          re[i + k + l / 2] = re[i + k] - ar; im[i + k + l / 2] = im[i + k] - ai;
          re[i + k] += ar; im[i + k] += ai;
          t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
        }
      }
    }
  }

  // ---------- state ----------
  var S = {
    src: null, fs: 0, labels: [], nch: 0, buf: [], raw: [], head: 0, cap: 0, count: 0,
    filt: [], notch: 50, hp: true, scale: 100, paused: false, win: window.innerWidth < 700 ? 4 : 8,
    rec: null, marks: [], psd: null, freqs: null, chanPow: [], quality: [],
    focus: [], test: null, lastSpec: 0, unit: "\u00b5V"
  };
  try { var nv = localStorage.getItem("eegv-notch"); if (nv) S.notch = +nv; } catch (e) { /* storage off */ }

  function setup(fs, labels, unit) {
    S.unit = unit || "\u00b5V"; setScaleLabels();
    S.fs = fs; S.labels = labels.slice(); S.nch = labels.length; S.cap = Math.round(fs * 12);
    S.buf = []; S.raw = []; S.filt = [];
    for (var c = 0; c < S.nch; c++) { S.buf.push(new Float32Array(S.cap)); S.raw.push(new Float32Array(S.cap)); }
    S.head = 0; S.count = 0; S.psd = null; S.chanPow = []; S.quality = [];
    makeFilters();
    var back = labels.filter(function (l) { return l === "O1" || l === "O2"; });
    S.focus = back.length ? back : (labels.indexOf("TP9") >= 0 ? ["TP9", "TP10"] : labels.slice());
    $("eegv-fs").textContent = (Math.round(fs * 10) / 10) + " Hz";
    $("eegv-ch").textContent = String(S.nch);
    $("eegv-focus").textContent = S.focus.join(" + ");
    buildChannelList();
    resize();
  }
  function makeFilters() {
    S.filt = [];
    for (var c = 0; c < S.nch; c++) {
      var f = [];
      if (S.hp) f.push(biquad("hp", 1, S.fs, Math.SQRT1_2));
      f.push(biquad("lp", Math.min(45, S.fs * 0.45), S.fs, Math.SQRT1_2));
      if (S.notch && S.notch < S.fs / 2) f.push(biquad("notch", S.notch, S.fs, 20));
      S.filt.push(f);
    }
  }
  function push(frame) {
    var h = S.head;
    for (var c = 0; c < S.nch; c++) {
      var x = frame[c], y = x, f = S.filt[c];
      for (var i = 0; i < f.length; i++) y = run(f[i], y);
      S.raw[c][h] = x; S.buf[c][h] = y;
    }
    S.head = (h + 1) % S.cap; S.count++;
    if (S.rec) {
      if (S.rec.rows.length < S.rec.max) {
        var row = new Float32Array(S.nch);
        for (c = 0; c < S.nch; c++) row[c] = frame[c];
        S.rec.rows.push(row);
      } else stopRecord("Recording reached 30 minutes and stopped.");
    }
  }
  function lastN(c, n, which) {
    var a = which === "raw" ? S.raw[c] : S.buf[c], out = new Float32Array(n), start = (S.head - n + S.cap * 4) % S.cap;
    for (var i = 0; i < n; i++) out[i] = a[(start + i) % S.cap];
    return out;
  }

  // ---------- spectrum, band power, quality ----------
  function spectrum() {
    var fs = S.fs, N = 256;
    while (N * 2 <= fs * 2.2) N *= 2;
    var span = Math.min(S.count, Math.round(fs * 4), S.cap);
    if (span < N) { S.psd = null; return; }
    var hann = new Float32Array(N); for (var i = 0; i < N; i++) hann[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1));
    var nb = N / 2 + 1, df = fs / N;
    S.freqs = new Float32Array(nb); for (i = 0; i < nb; i++) S.freqs[i] = i * df;
    var mean = new Float32Array(nb), wsum = 0;
    S.chanPow = []; S.quality = [];
    for (var c = 0; c < S.nch; c++) {
      var x = lastN(c, span), p = new Float32Array(nb), segs = 0;
      for (var s0 = 0; s0 + N <= span; s0 += N / 2) {
        var re = new Float32Array(N), im = new Float32Array(N), m = 0;
        for (i = 0; i < N; i++) m += x[s0 + i]; m /= N;
        for (i = 0; i < N; i++) re[i] = (x[s0 + i] - m) * hann[i];
        fft(re, im);
        for (i = 0; i < nb; i++) p[i] += re[i] * re[i] + im[i] * im[i];
        segs++;
      }
      for (i = 0; i < nb; i++) p[i] /= segs;
      var tot = 0, bands = {};
      BANDS.forEach(function (b) { bands[b.k] = 0; });
      for (i = 0; i < nb; i++) {
        var f = S.freqs[i];
        if (f >= 1 && f < 40) tot += p[i];
        BANDS.forEach(function (b) { if (f >= b.lo && f < b.hi) bands[b.k] += p[i]; });
      }
      var rel = {};
      BANDS.forEach(function (b) { rel[b.k] = tot > 0 ? bands[b.k] / tot : 0; });
      S.chanPow.push(rel);
      // quality from the last 2 s of filtered signal, and of raw signal for a railed input
      var q = lastN(c, Math.min(span, Math.round(fs * 2))), r = lastN(c, Math.min(span, Math.round(fs * 2)), "raw"), ss = 0, rmax = 0;
      for (i = 0; i < q.length; i++) { ss += q[i] * q[i]; rmax = Math.max(rmax, Math.abs(r[i])); }
      var rms = Math.sqrt(ss / q.length), state = "ok";
      if (S.src && S.src.railed && rmax > S.src.railed) state = "railed";
      else if (rms < 0.3) state = "flat";
      else if (rms > ((S.src && S.src.noisy) || 100)) state = "noisy";
      S.quality.push({ rms: rms, state: state });
      if (S.focus.indexOf(S.labels[c]) >= 0) { for (i = 0; i < nb; i++) mean[i] += p[i]; wsum++; }
    }
    for (i = 0; i < nb; i++) mean[i] /= Math.max(1, wsum);
    S.psd = mean;
  }
  function focusBands() {
    var out = {}, n = 0;
    BANDS.forEach(function (b) { out[b.k] = 0; });
    S.labels.forEach(function (l, c) {
      if (S.focus.indexOf(l) < 0 || !S.chanPow[c]) return;
      BANDS.forEach(function (b) { out[b.k] += S.chanPow[c][b.k]; }); n++;
    });
    BANDS.forEach(function (b) { out[b.k] /= Math.max(1, n); });
    return out;
  }
  function alphaPeak() {
    if (!S.psd) return null;
    // a peak counts only when it is a local maximum inside 7 to 13 Hz, not the edge of a slope
    var best = -1, bi = -1, lo = -1, hi = -1;
    for (var i = 0; i < S.psd.length; i++) {
      if (S.freqs[i] < 7 || S.freqs[i] > 13) continue;
      if (lo < 0) lo = i; hi = i;
      if (S.psd[i] > best) { best = S.psd[i]; bi = i; }
    }
    if (bi <= lo || bi >= hi) return null;
    return S.freqs[bi];
  }

  // ---------- canvases ----------
  var cvT = $("eegv-traces"), cvS = $("eegv-spec"), cvH = $("eegv-head");
  var gT = cvT.getContext("2d"), gS = cvS.getContext("2d"), gH = cvH.getContext("2d");
  function fit(cv) {
    var r = cv.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1);
    var w = Math.max(1, Math.round(r.width * d)), h = Math.max(1, Math.round(r.height * d));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    return d;
  }
  function resize() { fit(cvT); fit(cvS); fit(cvH); }
  window.addEventListener("resize", resize);

  function drawTraces() {
    var d = fit(cvT), W = cvT.width, H = cvT.height, g = gT;
    g.fillStyle = C.ink; g.fillRect(0, 0, W, H);
    if (!S.nch) return;
    var labW = 46 * d, top = 6 * d, bot = 22 * d, rows = S.nch, rh = (H - top - bot) / rows;
    var n = Math.min(Math.round(S.fs * S.win), S.cap), avail = Math.min(S.count, n);
    // time grid, one line a second
    g.strokeStyle = C.line; g.lineWidth = 1;
    g.font = (10 * d) + "px " + MONO; g.fillStyle = C.dim; g.textBaseline = "middle";
    for (var s = 0; s <= S.win; s++) {
      var x = labW + (W - labW - 8 * d) * (s / S.win);
      g.beginPath(); g.moveTo(x, top); g.lineTo(x, H - bot); g.stroke();
      if (s < S.win - 1 && (s % 2 === 0 || W > 700 * d)) { g.textAlign = "left"; g.fillText((s - S.win) + " s", x + 3 * d, H - bot / 2); }
    }
    var px = (W - labW - 8 * d) / n;
    for (var c = 0; c < rows; c++) {
      var y0 = top + rh * (c + 0.5), q = S.quality[c], st = q ? q.state : "ok";
      var isFocus = S.focus.indexOf(S.labels[c]) >= 0;
      g.fillStyle = st === "ok" ? (isFocus ? C.coral : C.text) : C.gold;
      g.textAlign = "left"; g.font = (11 * d) + "px " + MONO;
      g.fillText(S.labels[c], 8 * d, y0);
      g.fillStyle = st === "ok" ? C.live : (st === "flat" || st === "railed" ? C.bad : C.gold);
      g.fillRect(labW - 10 * d, y0 - 2.5 * d, 5 * d, 5 * d);
      g.strokeStyle = C.line; g.beginPath(); g.moveTo(labW, y0); g.lineTo(W - 8 * d, y0); g.stroke();
      if (!avail) continue;
      var x0 = S.buf[c], k = S.scale, start = (S.head - avail + S.cap * 4) % S.cap, off = n - avail;
      g.save(); g.beginPath(); g.rect(labW, y0 - rh / 2, W - labW, rh); g.clip();
      g.strokeStyle = isFocus ? C.coral : "rgba(240,238,230,0.82)"; g.lineWidth = Math.max(1, 1.1 * d);
      g.beginPath();
      var step = Math.max(1, Math.floor(avail / ((W - labW) * 1.5)));
      for (var i = 0; i < avail; i += step) {
        var v = x0[(start + i) % S.cap], yy = y0 - (v / k) * (rh * 0.5);
        if (i === 0) g.moveTo(labW + (off + i) * px, yy); else g.lineTo(labW + (off + i) * px, yy);
      }
      g.stroke(); g.restore();
    }
    // scale bar
    g.fillStyle = C.dim; g.textAlign = "right"; g.font = (10 * d) + "px " + MONO;
    g.fillText("row = \u00b1" + S.scale + " " + S.unit, W - 8 * d, H - bot / 2);
    // segment label for the demo
    if (S.src && S.src.segmentLabel) {
      var lab = S.src.segmentLabel();
      g.font = "600 " + (12 * d) + "px " + MONO; g.textAlign = "right";
      var tw = g.measureText(lab.toUpperCase()).width;
      g.fillStyle = "rgba(10,11,13,0.88)"; g.fillRect(W - 20 * d - tw, top + 1 * d, tw + 14 * d, 19 * d);
      g.strokeStyle = C.coral; g.lineWidth = 1; g.strokeRect(W - 20 * d - tw, top + 1 * d, tw + 14 * d, 19 * d);
      g.fillStyle = C.coral; g.fillText(lab.toUpperCase(), W - 13 * d, top + 10.5 * d);
    }
  }

  function drawSpec() {
    var d = fit(cvS), W = cvS.width, H = cvS.height, g = gS;
    g.fillStyle = C.ink; g.fillRect(0, 0, W, H);
    var l = 30 * d, r = 8 * d, t = 8 * d, b = 20 * d, fmax = 40;
    g.font = (9 * d) + "px " + MONO; g.textBaseline = "middle"; g.textAlign = "center";
    // alpha band shade
    var xa = l + (W - l - r) * 8 / fmax, xb = l + (W - l - r) * 13 / fmax;
    g.fillStyle = "rgba(230, 66, 84,0.10)"; g.fillRect(xa, t, xb - xa, H - t - b);
    g.strokeStyle = C.line; g.lineWidth = 1;
    [0, 10, 20, 30, 40].forEach(function (f) {
      var x = l + (W - l - r) * f / fmax;
      g.beginPath(); g.moveTo(x, t); g.lineTo(x, H - b); g.stroke();
      g.fillStyle = C.dim; g.fillText(f + (f === 40 ? " Hz" : ""), Math.min(x, W - 18 * d), H - b / 2);
    });
    if (!S.psd) { g.fillStyle = C.dim; g.fillText("Collecting 4 s of signal", W / 2, H / 2); return; }
    var lo = Infinity, hi = -Infinity, i;
    for (i = 0; i < S.psd.length; i++) if (S.freqs[i] >= 1 && S.freqs[i] <= fmax) { var v = Math.log10(S.psd[i] + 1e-9); lo = Math.min(lo, v); hi = Math.max(hi, v); }
    if (hi - lo < 1) hi = lo + 1;
    g.save(); g.fillStyle = C.dim; g.translate(10 * d, (H - b + t) / 2); g.rotate(-Math.PI / 2); g.fillText("power, log", 0, 0); g.restore();
    g.strokeStyle = C.coral; g.lineWidth = 1.6 * d; g.beginPath();
    var first = true;
    for (i = 0; i < S.psd.length; i++) {
      var f = S.freqs[i]; if (f < 1 || f > fmax) continue;
      var x = l + (W - l - r) * f / fmax, y = H - b - (H - b - t) * ((Math.log10(S.psd[i] + 1e-9) - lo) / (hi - lo));
      if (first) { g.moveTo(x, y); first = false; } else g.lineTo(x, y);
    }
    g.stroke();
  }

  function drawHead() {
    var d = fit(cvH), W = cvH.width, H = cvH.height, g = gH;
    g.fillStyle = C.ink; g.fillRect(0, 0, W, H);
    var R = Math.min(W * 0.4, H * 0.38), cx = W / 2, cy = H / 2 + 2 * d;
    g.strokeStyle = C.line2; g.lineWidth = 1.2 * d;
    g.beginPath(); g.arc(cx, cy, R, 0, 2 * Math.PI); g.stroke();
    g.beginPath(); g.moveTo(cx - R * 0.12, cy - R * 0.99); g.lineTo(cx, cy - R * 1.14); g.lineTo(cx + R * 0.12, cy - R * 0.99); g.stroke();
    g.beginPath(); g.ellipse(cx - R * 1.03, cy, R * 0.06, R * 0.16, 0, 0, 2 * Math.PI); g.stroke();
    g.beginPath(); g.ellipse(cx + R * 1.03, cy, R * 0.06, R * 0.16, 0, 0, 2 * Math.PI); g.stroke();
    var maxA = 0.0001;
    S.labels.forEach(function (l, c) { if (S.chanPow[c]) maxA = Math.max(maxA, S.chanPow[c].alpha); });
    g.textAlign = "center"; g.textBaseline = "middle";
    S.labels.forEach(function (l, c) {
      var p = POS[l]; if (!p) return;
      var rr = Math.min(1.02, p[0] / 90) * R, a = p[1] * Math.PI / 180;
      var x = cx - rr * Math.sin(a), y = cy - rr * Math.cos(a);
      var v = S.chanPow[c] ? S.chanPow[c].alpha / maxA : 0, rad = Math.max(10 * d, R * 0.1);
      g.fillStyle = "rgba(230, 66, 84," + (0.08 + 0.88 * v).toFixed(3) + ")";
      g.beginPath(); g.arc(x, y, rad, 0, 2 * Math.PI); g.fill();
      g.strokeStyle = S.focus.indexOf(l) >= 0 ? C.coral : C.line2; g.lineWidth = 1 * d; g.stroke();
      g.fillStyle = v > 0.55 ? C.ink : C.text; g.font = "500 " + Math.round(Math.max(8.5 * d, rad * 0.62)) + "px " + MONO;
      g.fillText(l, x, y);
    });
    g.fillStyle = C.dim; g.font = (9 * d) + "px " + MONO; g.textAlign = "left";
    g.fillText("Alpha share per electrode", 6 * d, H - 8 * d);
    g.textAlign = "right"; g.fillText("nose up", W - 6 * d, 10 * d);
  }

  // ---------- readouts ----------
  function updateReadouts() {
    if (!S.psd) return;
    var fb = focusBands();
    BANDS.forEach(function (b) {
      var v = fb[b.k], el = $("eegv-b-" + b.k);
      if (el) { el.querySelector(".eegv-bar-fill").style.width = Math.round(v * 100) + "%"; el.querySelector(".eegv-bar-v").textContent = Math.round(v * 100) + "%"; }
    });
    $("eegv-alpha").textContent = Math.round(fb.alpha * 100) + "%";
    var pk = alphaPeak();
    $("eegv-peak").textContent = pk ? pk.toFixed(1) + " Hz" : "None";
    var good = S.quality.filter(function (q) { return q.state === "ok"; }).length;
    $("eegv-quality").textContent = good + " / " + S.nch;
    S.labels.forEach(function (l, c) {
      var li = document.querySelector('#eegv-chans [data-ch="' + c + '"]'); if (!li || !S.quality[c]) return;
      var q = S.quality[c];
      li.className = "eegv-chan is-" + q.state;
      li.querySelector(".eegv-chan-v").textContent = q.state === "ok" ? q.rms.toFixed(1) + " " + S.unit : q.state;
    });
    if (S.test) testTick(fb);
  }
  function buildChannelList() {
    var ul = $("eegv-chans"); ul.innerHTML = "";
    S.labels.forEach(function (l, c) {
      var li = document.createElement("li"); li.className = "eegv-chan"; li.setAttribute("data-ch", c);
      li.innerHTML = '<span class="eegv-led"></span><span class="eegv-chan-n"></span><span class="eegv-chan-v">\u2013</span>';
      li.querySelector(".eegv-chan-n").textContent = l;
      ul.appendChild(li);
    });
  }

  // ---------- status and log ----------
  function status(t, live) { $("eegv-status").textContent = t; root.classList.toggle("is-live", !!live); }
  function log(t) {
    var el = $("eegv-log"), p = document.createElement("p"), now = new Date();
    p.textContent = now.toTimeString().slice(0, 8) + "  " + t; el.insertBefore(p, el.firstChild);
    while (el.children.length > 30) el.removeChild(el.lastChild);
  }
  function setSourceButtons(name) {
    ["demo", "muse", "cyton", "npg"].forEach(function (k) { $("eegv-src-" + k).setAttribute("aria-pressed", k === name ? "true" : "false"); });
    $("eegv-demo-ctl").hidden = name !== "demo";
  }

  // ---------- source: demo ----------
  var demoData = null;
  function loadDemo() {
    if (demoData) return Promise.resolve(demoData);
    return Promise.all([
      fetch(BASE + "physionet-s001-r01-r02.json").then(function (r) { return r.json(); }),
      fetch(BASE + "physionet-s001-r01-r02.bin").then(function (r) { return r.arrayBuffer(); })
    ]).then(function (res) { demoData = { meta: res[0], data: new Int16Array(res[1]) }; return demoData; });
  }
  function startDemo(atSeconds) {
    stopSource();
    status("Loading", false);
    return loadDemo().then(function (dd) {
      var m = dd.meta, all = m.channels.length, total = m.samples, pos = Math.round((atSeconds || 0) * m.fs), t0 = performance.now(), sent = 0;
      // ?demo=band: only the three positions of the open EEG band (Fp1, O1, O2), the same recording
      var band = /[?&]demo=band\b/.test(window.location.search);
      var pick = band ? ["Fp1", "O1", "O2"].map(function (l) { return m.channels.indexOf(l); }) : m.channels.map(function (_, c) { return c; });
      var nch = pick.length;
      setup(m.fs, pick.map(function (c) { return m.channels[c]; }));
      var src = {
        name: "demo",
        tick: function () {
          if (S.paused) { t0 = performance.now() - sent / m.fs * 1000; return; }
          var due = Math.floor((performance.now() - t0) / 1000 * m.fs);
          var n = Math.min(due - sent, Math.round(m.fs));
          for (var i = 0; i < n; i++) {
            var fr = new Array(nch), b = pos * all;
            for (var c = 0; c < nch; c++) fr[c] = dd.data[b + pick[c]] * m.scale_uv;
            push(fr); pos = (pos + 1) % total; sent++;
          }
          if (due - sent > m.fs) sent = due;
        },
        seek: function (sec) { pos = Math.round(sec * m.fs) % total; },
        segmentLabel: function () {
          var t = pos / m.fs, seg = m.segments.filter(function (s) { return t >= s.start_s && t < s.end_s; })[0];
          return seg ? seg.label + "  " + Math.floor(t - seg.start_s) + " s" : "";
        },
        stop: function () {}
      };
      S.src = src; setSourceButtons("demo");
      status("Demo", true);
      log("Demo started. Open PhysioNet recording, " + (band ? "the 3 band channels Fp1, O1, O2" : "16 channels") + " at 160 Hz.");
    }).catch(function () { status("No data", false); log("The demo recording did not load."); });
  }

  // ---------- source: Muse over Web Bluetooth ----------
  var MUSE_SERVICE = 0xfe8d, MUSE_CTRL = "273e0001-4c4d-454d-96be-f03bac821358";
  var MUSE_EEG = ["273e0003-4c4d-454d-96be-f03bac821358", "273e0004-4c4d-454d-96be-f03bac821358",
    "273e0005-4c4d-454d-96be-f03bac821358", "273e0006-4c4d-454d-96be-f03bac821358"];
  var museCmd = EEGVCodec.museCmd;
  function museDecode(dv) { return EEGVCodec.museDecode(new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength)); }
  function startMuse() {
    if (!navigator.bluetooth) return;
    var device, ctrl;
    navigator.bluetooth.requestDevice({ filters: [{ services: [MUSE_SERVICE] }] }).then(function (dev) {
      stopSource();
      device = dev; status("Connecting", false); log("Connecting to " + (dev.name || "Muse") + ".");
      return dev.gatt.connect();
    }).then(function (server) { return server.getPrimaryService(MUSE_SERVICE); }).then(function (svc) {
      return svc.getCharacteristic(MUSE_CTRL).then(function (c) { ctrl = c; return Promise.all(MUSE_EEG.map(function (u) { return svc.getCharacteristic(u); })); });
    }).then(function (chars) {
      setup(256, MUSE_LABELS);
      var q = [[], [], [], []];
      var handlers = chars.map(function (ch, k) {
        var h = function (ev) {
          var s = museDecode(ev.target.value); Array.prototype.push.apply(q[k], s);
          var n = Math.min(q[0].length, q[1].length, q[2].length, q[3].length);
          for (var i = 0; i < n; i++) if (!S.paused) push([q[0][i], q[1][i], q[2][i], q[3][i]]);
          for (var j = 0; j < 4; j++) q[j].splice(0, n);
          if (q[k].length > 512) q.forEach(function (a) { a.length = 0; });
        };
        ch.addEventListener("characteristicvaluechanged", h);
        return h;
      });
      S.src = {
        name: "muse",
        stop: function () {
          try { ctrl.writeValue(museCmd("h")); } catch (e) { /* already gone */ }
          chars.forEach(function (ch, k) { ch.removeEventListener("characteristicvaluechanged", handlers[k]); });
          try { device.gatt.disconnect(); } catch (e) { /* already gone */ }
        }
      };
      device.addEventListener("gattserverdisconnected", function () { if (S.src && S.src.name === "muse") { status("Disconnected", false); log("The Muse disconnected."); } });
      setSourceButtons("muse");
      return Promise.all(chars.map(function (ch) { return ch.startNotifications(); }))
        .then(function () { return ctrl.writeValue(museCmd("h")); })
        .then(function () { return ctrl.writeValue(museCmd("p21")); })
        .then(function () { return ctrl.writeValue(museCmd("s")); })
        .then(function () { return ctrl.writeValue(museCmd("d")); })
        .then(function () { status("Live", true); log("Muse streaming, 4 channels at 256 Hz."); });
    }).catch(function (e) {
      if (e && e.name === "NotFoundError") return; // the person closed the chooser
      status("Error", false); log("Muse connection failed. " + (e && e.message ? e.message : ""));
    });
  }

  // ---------- source: OpenBCI Cyton over Web Serial ----------
  function startCyton() {
    if (!navigator.serial) return;
    var port, reader, writer, alive = true;
    navigator.serial.requestPort().then(function (p) {
      stopSource(); port = p; status("Connecting", false); log("Opening the serial port at 115200 baud.");
      return port.open({ baudRate: 115200 });
    }).then(function () {
      writer = port.writable.getWriter(); reader = port.readable.getReader();
      var enc = new TextEncoder(), dec = new TextDecoder(), text = "", parser = null;
      function send(s) { return writer.write(enc.encode(s)); }
      function waitFor(test, ms) {
        return new Promise(function (res) {
          var t0 = Date.now();
          (function check() { if (test() || Date.now() - t0 > ms) res(); else setTimeout(check, 50); })();
        });
      }
      function loop() {
        return reader.read().then(function (r) {
          if (r.done || !alive) return;
          if (!parser) text += dec.decode(r.value, { stream: true });
          else {
            var frames = parser.feed(r.value);
            if (!S.paused) for (var i = 0; i < frames.length; i++) push(frames[i]);
          }
          return loop();
        });
      }
      S.src = {
        name: "cyton", railed: 187500 * 0.95,
        stop: function () {
          alive = false;
          var w = writer;
          Promise.resolve().then(function () { return w.write(enc.encode("s")); }).catch(function () {})
            .then(function () { try { w.releaseLock(); } catch (e) { /* closed */ } return reader.cancel(); }).catch(function () {})
            .then(function () { try { reader.releaseLock(); } catch (e) { /* closed */ } return port.close(); }).catch(function () {});
        }
      };
      setSourceButtons("cyton");
      loop().catch(function (e) { if (alive) { status("Error", false); log("Serial read stopped. " + (e && e.message ? e.message : "")); } });
      var vText = "";
      return send("s").then(function () { return send("v"); })
        .then(function () { return waitFor(function () { return text.indexOf("$$$") >= 0; }, 4000); })
        .then(function () {
          vText = text; text = "";
          if (!/\$\$\$|OpenBCI|ADS1299/i.test(vText)) log("No reply from the board. Check that the dongle switch is on GPIO 6 and the board is on PC.");
          var fw = vText.match(/Firmware:\s*v?([0-9.]+)/i);
          if (fw) log("Cyton firmware " + fw[1] + ".");
          return send("C");
        })
        .then(function () { return waitFor(function () { return EEGVCodec.daisyFromReply(text) !== null; }, 2000); })
        .then(function () {
          var daisy = EEGVCodec.daisyFromReply(text);
          if (daisy === null) { daisy = /daisy/i.test(vText); log("No reply to the channel mode command. Using the reset text."); }
          log(daisy ? "Cyton with Daisy found, 16 channels at 125 Hz each." : "Cyton found, 8 channels at 250 Hz.");
          setup(daisy ? 125 : 250, CYTON_LABELS.slice(0, daisy ? 16 : 8));
          parser = EEGVCodec.cytonParser(daisy);
          return send("b");
        }).then(function () { status("Live", true); });
    }).catch(function (e) {
      if (e && e.name === "NotFoundError") return;
      status("Error", false); log("Cyton connection failed. " + (e && e.message ? e.message : ""));
    });
  }

  // ---------- source: NPG Lite over Web Bluetooth ----------
  var NPG_SERVICE = "4fafc201-1fb5-459e-8fcc-c5c9c331914b", NPG_DATA = "beb5483e-36e1-4688-b7f5-ea07361b26a8",
    NPG_CTRL = "0000ff01-0000-1000-8000-00805f9b34fb", NPG_BATT = "f633d0ec-46b4-43c1-a39f-1ca06d0602e1";
  function startNpg() {
    if (!navigator.bluetooth) return;
    var device, ctrl, data, batt = null, onData, onBatt, enc = new TextEncoder(), st = { last: null, missed: 0 }, ready = false;
    navigator.bluetooth.requestDevice({ filters: [{ namePrefix: "NPG" }], optionalServices: [NPG_SERVICE] }).then(function (dev) {
      stopSource();
      device = dev; status("Connecting", false); log("Connecting to " + (dev.name || "NPG Lite") + ".");
      return dev.gatt.connect();
    }).then(function (server) { return server.getPrimaryService(NPG_SERVICE); }).then(function (svc) {
      return Promise.all([svc.getCharacteristic(NPG_CTRL), svc.getCharacteristic(NPG_DATA),
        svc.getCharacteristic(NPG_BATT).catch(function () { return null; })]);
    }).then(function (cs) {
      ctrl = cs[0]; data = cs[1]; batt = cs[2];
      onData = function (ev) {
        var v = ev.target.value, b = new Uint8Array(v.buffer, v.byteOffset, v.byteLength);
        var nch = EEGVCodec.npgChannels(b.length);
        if (!nch) return;
        if (!ready) {
          var labels = NPG_LABELS.slice(0, nch);
          while (labels.length < nch) labels.push("Ch" + (labels.length + 1));
          setup(500, labels, "counts");
          ready = true; status("Live", true);
          log("NPG Lite streaming, " + nch + " channels at 500 Hz. Values are ADC counts, not microvolts.");
        }
        var fr = EEGVCodec.npgDecode(b, st);
        if (!S.paused) for (var i = 0; i < fr.length; i++) push(fr[i]);
      };
      data.addEventListener("characteristicvaluechanged", onData);
      if (batt) {
        onBatt = function (ev) { log("NPG Lite battery " + ev.target.value.getUint8(0) + " %."); };
        batt.addEventListener("characteristicvaluechanged", onBatt);
      }
      S.src = {
        name: "npg", railed: 2000, noisy: 1500,
        stop: function () {
          try { ctrl.writeValue(enc.encode("STOP")); } catch (e) { /* already gone */ }
          data.removeEventListener("characteristicvaluechanged", onData);
          if (batt && onBatt) batt.removeEventListener("characteristicvaluechanged", onBatt);
          if (st.missed) log("NPG Lite: " + st.missed + " samples were lost on the radio link.");
          try { device.gatt.disconnect(); } catch (e) { /* already gone */ }
        }
      };
      device.addEventListener("gattserverdisconnected", function () { if (S.src && S.src.name === "npg") { status("Disconnected", false); log("The NPG Lite disconnected."); } });
      setSourceButtons("npg");
      return data.startNotifications()
        .then(function () { return batt ? batt.startNotifications().catch(function () {}) : null; })
        .then(function () { return ctrl.writeValue(enc.encode("START")); })
        .then(function () { status("Starting", false); log("START sent. Waiting for data."); });
    }).catch(function (e) {
      if (e && e.name === "NotFoundError") return;
      status("Error", false); log("NPG Lite connection failed. " + (e && e.message ? e.message : ""));
    });
  }

  function stopSource() {
    if (S.rec) stopRecord("Recording stopped because the source changed.");
    if (S.test) endTest(true);
    if (S.src && S.src.stop) S.src.stop();
    S.src = null; status("Waiting", false);
  }

  // ---------- recording (stays in the browser, saved as CSV by the person) ----------
  function startRecord() {
    if (!S.src) return;
    S.rec = { t0: new Date(), rows: [], max: Math.round(S.fs * 1800), marks: [], labels: S.labels.slice(), fs: S.fs, src: S.src.name, unit: S.unit };
    $("eegv-rec").setAttribute("aria-pressed", "true"); $("eegv-rec").textContent = "Stop and save";
    $("eegv-mark").disabled = false; log("Recording started.");
  }
  function stopRecord(msg) {
    var r = S.rec; S.rec = null;
    $("eegv-rec").setAttribute("aria-pressed", "false"); $("eegv-rec").textContent = "Record";
    $("eegv-mark").disabled = true;
    if (!r || !r.rows.length) return;
    var lines = ["# Open EEG Viewer, theconsciousness.ai/hardware/eeg-viewer/",
      "# source: " + r.src + (r.src === "demo" ? " (PhysioNet EEGMMIDB S001 R01+R02, ODC-By 1.0, doi 10.13026/C28G6P)" : ""),
      "# started: " + r.t0.toISOString(), "# sample_rate_hz: " + r.fs, "# unit: " + (r.unit === "counts" ? "ADC counts centred on 2048 (gain not published)" : "microvolt") + ", unfiltered",
      "time_s," + r.labels.join(",") + ",marker"];
    var mk = {}; r.marks.forEach(function (m) { mk[m.i] = (mk[m.i] ? mk[m.i] + " | " : "") + m.t; });
    for (var i = 0; i < r.rows.length; i++) {
      var row = r.rows[i], s = (i / r.fs).toFixed(4);
      for (var c = 0; c < row.length; c++) s += "," + row[c].toFixed(3);
      lines.push(s + "," + (mk[i] ? '"' + mk[i].replace(/"/g, "'") + '"' : ""));
    }
    var blob = new Blob([lines.join("\n")], { type: "text/csv" }), a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "eeg-" + r.src + "-" + r.t0.toISOString().slice(0, 19).replace(/[:T]/g, "-") + ".csv";
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
    log((msg ? msg + " " : "") + "Saved " + (r.rows.length / r.fs).toFixed(1) + " s to a CSV file on this device.");
  }

  // ---------- eyes closed test (Berger's alpha test, 1929) ----------
  var PH = [{ k: "open", t: 20, say: "Keep your eyes open and look at one point." }, { k: "closed", t: 20, say: "Close your eyes and relax." }];
  function tone(f) {
    try {
      var A = window.AudioContext || window.webkitAudioContext; if (!A) return;
      var ac = tone.ac || (tone.ac = new A()), o = ac.createOscillator(), g = ac.createGain();
      o.frequency.value = f; o.type = "sine"; g.gain.setValueAtTime(0.0001, ac.currentTime);
      g.gain.exponentialRampToValueAtTime(0.05, ac.currentTime + 0.05); g.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + 0.6);
      o.connect(g); g.connect(ac.destination); o.start(); o.stop(ac.currentTime + 0.65);
    } catch (e) { /* no audio */ }
  }
  function startTest() {
    if (!S.src) return;
    S.test = { i: 0, t0: performance.now(), vals: { open: [], closed: [] } };
    if (S.src.name === "demo") S.src.seek(5);
    $("eegv-test").setAttribute("aria-pressed", "true");
    $("eegv-test-out").textContent = ""; tone(330); testSay(); log("Eyes closed test started.");
  }
  function testSay() { var p = PH[S.test.i]; $("eegv-test-say").textContent = p.say; }
  function testTick(fb) {
    var T = S.test, p = PH[T.i], el = (performance.now() - T.t0) / 1000;
    if (el > 5) T.vals[p.k].push(fb.alpha); // skip the first 5 s of each phase, the filter and the eyes settle
    $("eegv-test-bar").style.width = Math.min(100, ((T.i * 20 + el) / 40) * 100) + "%";
    if (el >= p.t) {
      T.i++;
      if (T.i < PH.length) {
        T.t0 = performance.now(); tone(262);
        if (S.src && S.src.name === "demo") S.src.seek(66);
        testSay();
      } else endTest(false);
    }
  }
  function endTest(cancel) {
    var T = S.test; S.test = null; $("eegv-test").setAttribute("aria-pressed", "false"); $("eegv-test-bar").style.width = "0";
    if (cancel || !T) { $("eegv-test-say").textContent = "Test stopped."; return; }
    tone(392);
    var m = function (a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : 0; };
    var o = m(T.vals.open), c = m(T.vals.closed), ratio = o > 0 ? c / o : 0;
    $("eegv-test-say").textContent = "Done. You can open your eyes.";
    $("eegv-test-out").textContent = "Alpha share at " + S.focus.join(" + ") + ": eyes open " + Math.round(o * 100) + "%, eyes closed " + Math.round(c * 100) + "%, ratio " + ratio.toFixed(1) + ". " +
      (ratio >= 1.5 ? "Alpha rose when the eyes closed, the response Hans Berger first recorded." : "Alpha did not rise clearly. Check the electrode contact at the back of the head and try again.");
    log("Eyes closed test. Open " + Math.round(o * 100) + "%, closed " + Math.round(c * 100) + "%.");
  }

  // ---------- controls ----------
  $("eegv-src-demo").addEventListener("click", function () { startDemo(0); });
  $("eegv-src-muse").addEventListener("click", startMuse);
  $("eegv-src-cyton").addEventListener("click", startCyton);
  $("eegv-src-npg").addEventListener("click", startNpg);
  $("eegv-jump-open").addEventListener("click", function () { if (S.src && S.src.seek) { S.src.seek(5); log("Jumped to eyes open."); } });
  $("eegv-jump-closed").addEventListener("click", function () { if (S.src && S.src.seek) { S.src.seek(66); log("Jumped to eyes closed."); } });
  $("eegv-pause").addEventListener("click", function () {
    S.paused = !S.paused; this.setAttribute("aria-pressed", S.paused ? "true" : "false"); this.textContent = S.paused ? "Resume" : "Pause";
  });
  $("eegv-rec").addEventListener("click", function () { if (S.rec) stopRecord(); else startRecord(); });
  $("eegv-mark").addEventListener("click", function () {
    if (!S.rec) return; var t = ($("eegv-mark-text").value || "mark").slice(0, 60);
    S.rec.marks.push({ i: S.rec.rows.length, t: t }); log("Marker: " + t);
  });
  $("eegv-test").addEventListener("click", function () { if (S.test) endTest(true); else startTest(); });
  $("eegv-scale").addEventListener("change", function () { S.scale = +this.value; });
  $("eegv-notch").value = String(S.notch);
  $("eegv-notch").addEventListener("change", function () {
    S.notch = +this.value; try { localStorage.setItem("eegv-notch", String(S.notch)); } catch (e) { /* storage off */ }
    if (S.nch) makeFilters();
  });
  $("eegv-win").value = String(S.win);
  $("eegv-win").addEventListener("change", function () { S.win = +this.value; });


  function setScaleLabels() {
    var sel = $("eegv-scale");
    for (var i = 0; i < sel.options.length; i++) sel.options[i].textContent = "\u00b1" + sel.options[i].value + " " + S.unit;
  }

  // ---------- view: hide the side panels, full screen ----------
  // Native Fullscreen API on the console where it exists. Where it is missing or refused (Safari on
  // iPhone), a class pins the console to the whole window instead, so the button always works.
  var btnPanels = $("eegv-panels"), btnFull = $("eegv-full");
  function setPanels(off) {
    root.classList.toggle("no-panels", off);
    btnPanels.setAttribute("aria-pressed", off ? "true" : "false");
    var l = off ? "Show the side panels" : "Hide the side panels";
    btnPanels.setAttribute("aria-label", l); btnPanels.title = l;
    try { localStorage.setItem("eegv-panels", off ? "off" : "on"); } catch (e) { /* storage off */ }
    resize();
  }
  function syncFull() {
    var on = document.fullscreenElement === root || root.classList.contains("is-max");
    root.classList.toggle("is-full", on);
    btnFull.setAttribute("aria-pressed", on ? "true" : "false");
    var l = on ? "Leave full screen" : "Full screen";
    btnFull.setAttribute("aria-label", l); btnFull.title = l;
    document.documentElement.style.overflow = root.classList.contains("is-max") ? "hidden" : "";
    resize();
  }
  function setMax(on) { root.classList.toggle("is-max", on); syncFull(); }
  btnPanels.addEventListener("click", function () { setPanels(!root.classList.contains("no-panels")); });
  btnFull.addEventListener("click", function () {
    if (document.fullscreenElement) { document.exitFullscreen().catch(function () {}); return; }
    if (root.classList.contains("is-max")) { setMax(false); return; }
    if (root.requestFullscreen) root.requestFullscreen().catch(function () { setMax(true); });
    else setMax(true);
  });
  document.addEventListener("fullscreenchange", syncFull);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && root.classList.contains("is-max")) setMax(false); });
  try { if (localStorage.getItem("eegv-panels") === "off") setPanels(true); } catch (e) { /* storage off */ }

  // browser support for each input
  if (!navigator.bluetooth) { $("eegv-src-muse").disabled = true; $("eegv-src-npg").disabled = true; $("eegv-muse-note").hidden = false; }
  if (!navigator.serial) { $("eegv-src-cyton").disabled = true; $("eegv-cyton-note").hidden = false; }
  if (!window.isSecureContext) log("This page needs HTTPS for Bluetooth and USB.");

  // ---------- loop ----------
  function frame(ts) {
    if (S.src && S.src.tick) S.src.tick();
    if (S.nch && ts - S.lastSpec > 250) { S.lastSpec = ts; spectrum(); updateReadouts(); drawSpec(); drawHead(); }
    drawTraces();
    requestAnimationFrame(frame);
  }
  resize(); drawSpec(); drawHead();
  requestAnimationFrame(frame);

  // start the demo when the console is first on screen, so the recording loads only for people who see it
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { io.disconnect(); if (!S.src) startDemo(0); } }, { rootMargin: "200px" });
    io.observe(root);
  } else startDemo(0);
})();
