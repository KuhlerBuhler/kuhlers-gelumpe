/**
 * A bsdiff 4 file (BSDIFF40, what `bspatch old new patch` reads) for an image
 * whose changes we know, instead of one found by searching.
 *
 * Classic bsdiff finds matches by suffix sorting and stores the old bytes it
 * leaves behind as differences, so a changed region that was copied from
 * somewhere else in the firmware would be stored as old minus new, which is
 * firmware. Here the changes are given: `matches` say which stretch of the new
 * image is a copy of which stretch of the old one (the copy changes of the
 * patches), every other byte that equals the old image at the same place is a
 * plain match, and everything else is a literal that goes into the extra
 * block as it is. The diff block therefore holds nothing but zeros and the
 * extra block nothing but bytes of the new image that no old byte explains,
 * which are the bytes the patches write.
 *
 * Needs the `bzip2` program (the format is bzip2 streams); this is a build tool.
 */
import { spawnSync } from "node:child_process";

export const BSDIFF_MAGIC = "BSDIFF40";
const MIN_RUN = 16;

const bzip2 = (cmd, data) => {
  const r = spawnSync("bzip2", cmd, { input: data, maxBuffer: 1 << 30 });
  if (r.error || r.status !== 0) throw new Error(`bzip2 ${cmd.join(" ")}: ${r.error?.message ?? r.stderr?.toString()}`);
  return new Uint8Array(r.stdout);
};

/** bsdiff's number: 8 bytes little endian, sign and magnitude. */
export function putOfft(buffer, at, value) {
  let m = BigInt(Math.abs(value));
  for (let i = 0; i < 8; i++, m >>= 8n) buffer[at + i] = Number(m & 0xffn);
  if (value < 0) buffer[at + 7] |= 0x80;
}

export function getOfft(buffer, at) {
  let m = 0n;
  for (let i = 7; i >= 0; i--) m = (m << 8n) | BigInt(buffer[at + i] & (i === 7 ? 0x7f : 0xff));
  return buffer[at + 7] & 0x80 ? -Number(m) : Number(m);
}

/**
 * The segments that cover `next`: { copy: true, at, from, length } (new[at..] equals old[from..])
 * or { copy: false, at, length } (a literal).
 * @param {{at: number, from: number, length: number}[]} matches stretches of `next` known to equal stretches of `old`
 */
export function segments(old, next, matches = []) {
  const known = [...matches].sort((a, b) => a.at - b.at);
  known.forEach((m, i) => {
    if (m.at < 0 || m.from < 0 || m.length <= 0 || m.at + m.length > next.length || m.from + m.length > old.length) throw new RangeError("a match lies outside the images");
    if (i && known[i - 1].at + known[i - 1].length > m.at) throw new RangeError("matches overlap");
    for (let k = 0; k < m.length; k++) if (next[m.at + k] !== old[m.from + k]) throw new Error(`the match at ${m.at} is not a copy of ${m.from}`);
  });
  const runAt = (at, cap) => {
    let n = 0;
    while (n < cap && at + n < next.length && at + n < old.length && next[at + n] === old[at + n]) n++;
    return n;
  };
  const out = [];
  const push = s => {
    const last = out.at(-1);
    if (last && last.copy === s.copy && last.at + last.length === s.at && (!s.copy || last.from + last.length === s.from)) last.length += s.length;
    else out.push(s);
  };
  let at = 0;
  let k = 0;
  while (at < next.length) {
    if (k < known.length && known[k].at === at) {
      push({ copy: true, ...known[k] });
      at += known[k++].length;
      continue;
    }
    const limit = k < known.length ? known[k].at : next.length;
    const run = runAt(at, limit - at);
    if (run >= MIN_RUN || (run > 0 && at + run === limit)) {
      push({ copy: true, at, from: at, length: run });
      at += run;
      continue;
    }
    let end = at;
    while (end < limit && (end === at || runAt(end, MIN_RUN) < MIN_RUN)) end++;
    push({ copy: false, at, length: end - at });
    at = end;
  }
  return out;
}

/** The stretches of the result that are copies of firmware (the copy changes minus what they write over). */
export function copyMatches(patches, spans) {
  const matches = [];
  let n = 0;
  for (const patch of patches) {
    for (const change of patch.changes ?? []) {
      const span = spans[n++];
      if (!change.copy) continue;
      const writes = (change.over ?? []).map(o => [o.at, o.at + o.bytes.length / 2]).sort((a, b) => a[0] - b[0]);
      let at = 0;
      for (const [from, to] of [...writes, [change.copy.length, change.copy.length]]) {
        if (from > at) matches.push({ at: span.file + at, from: change.copy.file + at, length: from - at });
        at = to;
      }
    }
  }
  return matches;
}

/** The three blocks of a bsdiff 4 file for these segments: control triples, diff and extra. */
export function blocks(next, segs) {
  const steps = [];
  for (let i = 0; i < segs.length;) {
    const copy = segs[i].copy ? segs[i++] : null;
    const lit = i < segs.length && !segs[i].copy ? segs[i++] : null;
    steps.push({ from: copy?.from ?? 0, x: copy?.length ?? 0, y: lit?.length ?? 0, lit });
  }
  const ctrl = new Uint8Array(steps.length * 24);
  steps.forEach((s, i) => {
    putOfft(ctrl, i * 24, s.x);
    putOfft(ctrl, i * 24 + 8, s.y);
    putOfft(ctrl, i * 24 + 16, i + 1 < steps.length ? steps[i + 1].from - (s.from + s.x) : 0);
  });
  const diff = new Uint8Array(steps.reduce((n, s) => n + s.x, 0));
  const extra = new Uint8Array(steps.reduce((n, s) => n + s.y, 0));
  let at = 0;
  for (const s of steps) if (s.lit) { extra.set(next.subarray(s.lit.at, s.lit.at + s.lit.length), at); at += s.lit.length; }
  return { ctrl, diff, extra };
}

/** The file: header, then the three blocks as bzip2 streams. */
export function buildBsdiff(old, next, matches = []) {
  const { ctrl, diff, extra } = blocks(next, segments(old, next, matches));
  const [c, d, e] = [ctrl, diff, extra].map(b => bzip2(["-9", "-c"], b));
  const out = new Uint8Array(32 + c.length + d.length + e.length);
  out.set(Uint8Array.from(BSDIFF_MAGIC, ch => ch.charCodeAt(0)), 0);
  putOfft(out, 8, c.length);
  putOfft(out, 16, d.length);
  putOfft(out, 24, next.length);
  out.set(c, 32);
  out.set(d, 32 + c.length);
  out.set(e, 32 + c.length + d.length);
  return out;
}

/** The blocks of a bsdiff 4 file, decompressed. */
export function parseBsdiff(file) {
  if (String.fromCharCode(...file.subarray(0, 8)) !== BSDIFF_MAGIC) throw new Error("not a BSDIFF40 file");
  const [cl, dl, size] = [8, 16, 24].map(o => getOfft(file, o));
  if (cl < 0 || dl < 0 || size < 0 || 32 + cl + dl > file.length) throw new Error("corrupt BSDIFF40 header");
  const unpack = b => bzip2(["-dc"], b);
  return {
    size,
    ctrl: unpack(file.subarray(32, 32 + cl)),
    diff: unpack(file.subarray(32 + cl, 32 + cl + dl)),
    extra: unpack(file.subarray(32 + cl + dl)),
  };
}

/** bspatch, for tests and for checking the file without the program. */
export function applyBsdiff(old, file) {
  const { size, ctrl, diff, extra } = parseBsdiff(file);
  const out = new Uint8Array(size);
  let [oldAt, at, d, e] = [0, 0, 0, 0];
  for (let i = 0; i < ctrl.length; i += 24) {
    const [x, y, z] = [0, 8, 16].map(o => getOfft(ctrl, i + o));
    if (at + x + y > size || d + x > diff.length || e + y > extra.length) throw new Error("corrupt BSDIFF40 control block");
    for (let k = 0; k < x; k++) out[at + k] = ((old[oldAt + k] ?? 0) + diff[d + k]) & 0xff;
    at += x; oldAt += x; d += x;
    out.set(extra.subarray(e, e + y), at);
    at += y; e += y; oldAt += z;
  }
  if (at !== size) throw new Error("the patch does not fill the new file");
  return out;
}
