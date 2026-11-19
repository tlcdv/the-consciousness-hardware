/* Checks the decoders of the Open EEG Viewer against reference data of the two libraries that
   define the protocols, so they stay correct without a device on the desk.

   - Muse: the test vectors of muse-js (src/lib/muse-parse.spec.ts and muse-utils.spec.ts),
     github.com/urish/muse-js, MIT. Copied below.
   - Cyton: the official OpenBCI utilities package (@openbci/utilities, MIT). Its own packet
     builders and parser, including samplePacketReal, a packet recorded from a real board, are the
     reference. Daisy pairing follows OpenBCI _finalizeNewSampleForDaisy in OpenBCI_NodeJS_Cyton.
   - Daisy detection: the replies to the C command quoted in docs.openbci.com/Cyton/CytonSDK/.

   Run from software/eeg-viewer:
     npm install --no-save @openbci/utilities@1
     node test/codec-test.js
*/
"use strict";
const path = require("path");
const codec = require(path.join(__dirname, "..", "eeg-viewer.js"));
const { utilities: ref, constants: k } = require("@openbci/utilities");

let pass = 0, fail = 0;
function check(name, ok, detail) {
  if (ok) pass++; else { fail++; console.log("FAIL " + name + (detail ? "  " + detail : "")); }
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;

// ---------- Muse, muse-js test vectors ----------
{
  const input = [87, 33, 192, 82, 73, 6, 106, 242, 49, 64, 88, 153, 128, 66, 254, 44, 119, 157];
  const expected = [1394, 448, 1316, 2310, 1711, 561, 1029, 2201, 2052, 766, 711, 1949];
  check("muse 12 bit decode (muse-parse.spec.ts)", JSON.stringify(codec.muse12(new Uint8Array(input))) === JSON.stringify(expected));
  const uv = codec.museDecode(new Uint8Array([0, 7].concat(input)));
  check("muse microvolts = 0.48828125 * (n - 2048)", uv.length === 12 && uv.every((v, i) => v === 0.48828125 * (expected[i] - 2048)));
  check("muse encodeCommand('v1') (muse-utils.spec.ts)", JSON.stringify(Array.from(codec.museCmd("v1"))) === JSON.stringify([3, 118, 49, 10]));
  check("muse command p21", JSON.stringify(Array.from(codec.museCmd("p21"))) === JSON.stringify([4, 112, 50, 49, 10]));
}

// ---------- Cyton, 24 bit conversion, OpenBCI test vectors ----------
for (const [bytes, want] of [[[0x00, 0x06, 0x90], 1680], [[0x02, 0xC0, 0x01], 180225], [[0xFF, 0xFF, 0xFF], -1], [[0x81, 0xA1, 0x01], -8281855], [[0x7F, 0xFF, 0xFF], 8388607], [[0x80, 0x00, 0x00], -8388608]]) {
  const got = codec.int24(new Uint8Array(bytes), 0);
  check("int24 " + bytes.map((b) => b.toString(16)).join(" "), got === want && got === ref.interpret24bitAsInt32(Buffer.from(bytes)), got + " vs " + want);
}

// ---------- Cyton, whole packets against the OpenBCI parser ----------
const settings8 = k.channelSettingsArrayInit(8);
function refParse(pkt) {
  return ref.parsePacketStandardAccel({ rawDataPacket: pkt, channelSettings: settings8, scale: true });
}
check("scale factor equals OpenBCI 4.5 / 24 / (2^23 - 1)", near(codec.CYTON_UV * 1e-6, 4.5 / 24 / (Math.pow(2, 23) - 1), 1e-18));
function packetsMatch(name, pkts) {
  const p = codec.cytonParser(false);
  const frames = p.feed(new Uint8Array(Buffer.concat(pkts)));
  let ok = frames.length === pkts.length, worst = 0;
  pkts.forEach((pkt, i) => {
    const r = refParse(pkt).channelData;               // volts
    for (let c = 0; c < 8 && frames[i]; c++) worst = Math.max(worst, Math.abs(frames[i][c] - r[c] * 1e6));
  });
  check(name, ok && worst < 1e-9, "frames " + frames.length + "/" + pkts.length + ", largest difference " + worst + " uV");
}
packetsMatch("samplePacket 0..255 (OpenBCI builder)", Array.from({ length: 256 }, (_, i) => ref.samplePacket(i)));
packetsMatch("samplePacketReal, recorded from a real board", Array.from({ length: 50 }, (_, i) => ref.samplePacketReal(i)));
packetsMatch("random samples through convertSampleToPacketStandard", Array.from({ length: 500 }, (_, i) => {
  const s = ref.randomSample(8, k.OBCISampleRate250, false, "none")(i % 256);
  s.sampleNumber = i % 256;
  return ref.convertSampleToPacketStandard(s);
}));
// negative channel value, as in openBCIUtilities-test.js
{
  const pkt = ref.samplePacket(0); Buffer.from([0x81]).copy(pkt, 2);
  const f = codec.cytonParser(false).feed(new Uint8Array(pkt))[0][0];
  check("negative channel value", near(f, refParse(pkt).channelData[0] * 1e6, 1e-9) && near(f, codec.CYTON_UV * -8323071, 1e-6));
}

// ---------- Cyton + Daisy stream: pairing, chunking, noise ----------
{
  const raw = Array.from({ length: 401 }, (_, i) => {
    const s = ref.randomSample(8, k.OBCISampleRate250, false, "none")(i % 256);
    s.sampleNumber = i % 256;
    return ref.convertSampleToPacketStandard(s);
  });
  // reference: OpenBCI _finalizeNewSampleForDaisy with makeDaisySampleObject
  const want = []; let lower = null;
  for (const pkt of raw) {
    const s = refParse(pkt);
    if (s.sampleNumber % 2 === 1) lower = s;
    else if (lower) { want.push(ref.makeDaisySampleObject(lower, s).channelData); lower = null; }
  }
  // ours: the same bytes with junk between packets, fed in chunks of random size, like a serial port
  const junk = Buffer.from("OpenBCI V3 8-16 channel\n$$$");
  const stream = Buffer.concat([junk].concat(raw.flatMap((p, i) => (i % 37 === 5 ? [p, Buffer.from([0xa0, 0x01, 0x02])] : [p]))));
  const p = codec.cytonParser(true); const got = [];
  let seed = 7, at = 0;
  while (at < stream.length) {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    const n = 1 + (seed % 97);
    p.feed(new Uint8Array(stream.subarray(at, at + n))).forEach((f) => got.push(f));
    at += n;
  }
  let worst = 0;
  for (let i = 0; i < Math.min(got.length, want.length); i++) for (let c = 0; c < 16; c++) worst = Math.max(worst, Math.abs(got[i][c] - want[i][c] * 1e6));
  check("daisy frames equal OpenBCI merge, chunked stream with junk", got.length === want.length && got[0].length === 16 && worst < 1e-9,
    "frames " + got.length + "/" + want.length + ", largest difference " + worst + " uV");
  // a dropped packet: the parser must not pair across the gap
  const gap = raw.slice(1, 9).filter((_, i) => i !== 3);   // sample numbers 1..8 without 4
  const g = codec.cytonParser(true); const f = g.feed(new Uint8Array(Buffer.concat(gap)));
  check("daisy drops an unpaired packet", f.length === 3 && g.stats.missed === 1, "frames " + f.length + ", missed " + g.stats.missed);
}

// ---------- Daisy detection from the reply to C (Cyton SDK) ----------
for (const [t, want] of [["16$$$", true], ["daisy attached16$$$", true], ["no daisy to attach!8$$$", false], ["daisy removed$$$", null], ["", null], ["OpenBCI V3 8-16 channel\n$$$", null]]) {
  check("C reply " + JSON.stringify(t), codec.daisyFromReply(t) === want, String(codec.daisyFromReply(t)));
}

console.log(pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
