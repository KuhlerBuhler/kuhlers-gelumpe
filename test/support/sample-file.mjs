import { entryFromWav, HEADER, ESLI } from "../../src/sample-file.mjs";

/** Made-up WAVs and sample files for the tests; the audio is a formula, never a recording. */
export const put32 = (b, i, n) => { for (let k = 0; k < 4; k++) b[i + k] = (n >>> (8 * k)) & 255; };
export const text = (b, i, s) => { for (let k = 0; k < s.length; k++) b[i + k] = s.charCodeAt(k); };

/** A WAV made up from a formula, never a recording. `bits` 16 or 24, `extra` chunks to put in front of data. */
export function wav({ frames = 100, channels = 1, bits = 16, rate = 48000, tagNo = 1, esli = null, list = false } = {}) {
  const width = channels * bits / 8;
  const pcm = Uint8Array.from({ length: frames * width }, (_, i) => (i * 37 + 11) & 255);
  const parts = [];
  const chunk = (name, body) => { const c = new Uint8Array(8 + body.length + (body.length & 1)); text(c, 0, name); put32(c, 4, body.length); c.set(body, 8); parts.push(c); };
  const fmt = new Uint8Array(16);
  fmt[0] = tagNo; fmt[2] = channels; put32(fmt, 4, rate); put32(fmt, 8, rate * width); fmt[12] = width; fmt[14] = bits;
  chunk("fmt ", fmt);
  if (list) chunk("LIST", Uint8Array.from([1, 2, 3, 4, 5]));
  chunk("data", pcm);
  if (esli) { const k = new Uint8Array(8 + ESLI); text(k, 0, "esli"); put32(k, 4, ESLI); k.set(esli, 8); chunk("korg", k); }
  const body = 4 + parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(8 + body);
  text(out, 0, "RIFF"); put32(out, 4, body); text(out, 8, "WAVE");
  let at = 12;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}

/** A sample file of `slots` ({slot: name}) the way the firmware writes it. */
export function file(slots) {
  const head = new Uint8Array(HEADER);
  text(head, 0, "e2s sample all"); head[14] = 0x1a;
  const body = [];
  let at = HEADER;
  for (const [slot, name] of Object.entries(slots).sort((a, b) => a[0] - b[0])) {
    const entry = entryFromWav(wav({ frames: 50 + Number(slot) % 7 }), Number(slot), name);
    put32(head, 16 + 4 * Number(slot), at);
    body.push(entry);
    at += entry.length;
  }
  const out = new Uint8Array(at);
  out.set(head);
  let k = HEADER;
  for (const e of body) { out.set(e, k); k += e.length; }
  return out;
}

