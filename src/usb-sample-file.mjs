/**
 * The sample file on the card of the connected Electribe, KORG/<folder>/Sample/e2sSample.all, over USB (tools/patch/blech_sysex.py,
 * FILE commands with bit 30). Listing reads the header and a few bytes of each sample, not the audio. Adding sends the new samples
 * and the header. Removing is done on the card: the file firmware has no truncate, so the new file is built as a temp file beside it
 * (the header and the new samples sent, the kept samples copied on the card), checked by size and CRC, then the old file is deleted
 * and the temp file copied back and deleted. Until the old file is deleted nothing of it has changed; after that the finished temp
 * file is on the card and `finishTemp` completes the swap.
 */
import { BLECH, crc32 } from "./protocol.mjs";
import { crc32Join } from "./crc-combine.mjs";
import { prepare } from "./usb-update.mjs";
import { HEADER, SampleFileError, emptySampleFile, parseRemote, planChange } from "./sample-file.mjs";
import { render, text, TextError } from "./text.mjs";

/** The error of a swap that went wrong after the old file was deleted: the temp file on the card holds the finished file. */
export class SwapInterrupted extends TextError {}

async function prepareSamples(session) {
  const model = await prepare(session);
  const info = await session.sender.blechInfo(model);
  if (!(info.flags & BLECH.FLAG_SAMPLE)) throw new TextError("usbsamples.tooOld");
  return { model, sender: session.sender };
}

const pieces = (at, length) => {
  const out = [];
  for (let done = 0; done < length; done += BLECH.COPY_MAX) out.push({ at: at + done, length: Math.min(BLECH.COPY_MAX, length - done) });
  return out;
}

/**
 * The samples on the card, and whether a temp file of an interrupted swap lies beside the file.
 * @returns {Promise<{ parsed: object, header: Uint8Array, temp: number }>} `temp` is the size of the temp file, 0 when there is none
 */
export function readDeviceSamples(session, onProgress) {
  return session.exclusive(async () => {
    const { model, sender } = await prepareSamples(session);
    const temp = await sender.sampleFileSize(model, true);
    const size = await sender.sampleFileSize(model);
    if (!size) return { parsed: { size: 0, samples: [], header: emptySampleFile() }, header: emptySampleFile(), temp };
    const parsed = await parseRemote((at, n) => sender.sampleFileRead(at, n, model), size, onProgress);
    return { parsed, header: parsed.header, temp };
  });
}

/** What the plan needs on the card: only the header and the new samples when nothing is removed, else a compaction. */
export const needsCompaction = (parsed, plan) => plan.moves.length > 0 || plan.size < parsed.size;

/**
 * Puts a change on the card. `plan` is planChange(...). `onProgress({ phase, done, total })` says which part is running.
 * Returns when the card holds the new file and the temp file is gone.
 */
export function writeDeviceChange(session, parsed, plan, onProgress = () => {}) {
  return session.exclusive(async () => {
    const { model, sender } = await prepareSamples(session);
    if (!needsCompaction(parsed, plan)) {
      // new samples behind the old ones first, the header last: a cut-off leaves samples nobody lists, never a list without its samples
      const total = plan.appends.reduce((n, a) => n + a.bytes.length, 0) + HEADER;
      let done = 0;
      for (const a of plan.appends) {
        await sender.sampleFileWrite(a.at, a.bytes, model, n => onProgress({ phase: render(text("usbsamples.phase.send")), done: done + n, total }));
        done += a.bytes.length;
      }
      await sender.sampleFileWrite(0, plan.header, model, n => onProgress({ phase: render(text("usbsamples.phase.header")), done: done + n, total }));
      return;
    }
    const keptBytes = plan.keeps.reduce((n, k) => n + k.length, 0);
    const sent = plan.appends.reduce((n, a) => n + a.bytes.length, 0);
    const total = HEADER + keptBytes + sent + plan.size * 3;
    let done = 0;
    const report = phase => { onProgress({ phase, done, total }); };
    const parts = [];
    try {
      report(render(text("usbsamples.phase.build")));
      await sender.sampleFileWrite(0, plan.header, model, null, true);
      parts.push({ crc: crc32(plan.header), length: plan.header.length });
      done += HEADER;
      // kept samples that lie next to each other in the old file are copied in one go
      const runs = [];
      for (const k of plan.keeps) {
        const last = runs.at(-1);
        if (last && last.from + last.length === k.from) last.length += k.length;
        else runs.push({ from: k.from, to: k.to, length: k.length });
      }
      for (const run of runs) {
        for (const piece of pieces(0, run.length)) {
          const crc = await sender.sampleFileCopy({ at: run.from + piece.at }, { at: run.to + piece.at, temp: true }, piece.length, model);
          parts.push({ crc, length: piece.length });
          done += piece.length;
          report(render(text("usbsamples.phase.build")));
        }
      }
      for (const a of plan.appends) {
        await sender.sampleFileWrite(a.at, a.bytes, model, null, true);
        parts.push({ crc: crc32(a.bytes), length: a.bytes.length });
        done += a.bytes.length;
        report(render(text("usbsamples.phase.send")));
      }
      const expected = crc32Join(parts);
      if (parts.reduce((n, p) => n + p.length, 0) !== plan.size) throw new SampleFileError("usbsamples.partsSize");
      await checkFile(sender, model, true, plan.size, expected, n => { done += n; report(render(text("usbsamples.phase.check"))); });
      // from here on the old file goes: a failure leaves the finished temp file on the card
      try {
        if (parsed.size) await sender.sampleFileDelete(model, false);
        await copyBack(sender, model, plan.size, expected, n => { done += n; report(render(text("usbsamples.phase.copyBack"))); });
        await sender.sampleFileDelete(model, true);
      } catch (e) {
        throw new SwapInterrupted("usbsamples.interrupted", { error: e.text ?? e.message }, { cause: e });
      }
    } catch (e) {
      if (!(e instanceof SwapInterrupted)) await sender.sampleFileDelete(model, true).catch(() => {});
      throw e;
    }
  });
}

/** The size and the CRC-32 of a file on the card, read by the device itself in pieces; throws when they are not the expected ones. */
async function checkFile(sender, model, temp, size, expected, onPiece) {
  const have = await sender.sampleFileSize(model, temp);
  if (have !== size) throw new SampleFileError(temp ? "usbsamples.size.temp" : "usbsamples.size", { have, size });
  const crcs = [];
  for (const piece of pieces(0, size)) {
    crcs.push({ crc: await sender.sampleFileCrc(piece.at, piece.length, model, temp), length: piece.length });
    onPiece?.(piece.length);
  }
  if (crc32Join(crcs) !== expected) throw new SampleFileError(temp ? "usbsamples.crc.temp" : "usbsamples.crc");
}

/** The temp file copied onto the sample file, which is not there; then the size and the CRC of the result are checked. */
async function copyBack(sender, model, size, expected, onPiece) {
  for (const piece of pieces(0, size)) {
    await sender.sampleFileCopy({ at: piece.at, temp: true }, { at: piece.at }, piece.length, model);
    onPiece?.(piece.length);
  }
  await checkFile(sender, model, false, size, expected, onPiece);
}

/**
 * What lies beside the sample file from an interrupted swap: nothing, a finished temp file (its table fits its size), or a broken one.
 * @returns {Promise<"none"|"finished"|"broken">}
 */
export function inspectTemp(session) {
  return session.exclusive(async () => {
    const { model, sender } = await prepareSamples(session);
    const size = await sender.sampleFileSize(model, true);
    if (!size) return "none";
    try {
      const parsed = await parseRemote((at, n) => sender.sampleFileRead(at, n, model, null, true), size);
      const end = Math.max(HEADER, ...parsed.samples.map(s => s.offset + s.length));
      return parsed.samples.every(s => !s.problem) && end === size ? "finished" : "broken";
    } catch { return "broken"; }
  });
}

/** Completes a swap: the finished temp file replaces the sample file, checked by size and CRC against the temp file as the device reads it. */
export function finishTemp(session, onProgress = () => {}) {
  return session.exclusive(async () => {
    const { model, sender } = await prepareSamples(session);
    const size = await sender.sampleFileSize(model, true);
    const crcs = [];
    for (const piece of pieces(0, size)) crcs.push({ crc: await sender.sampleFileCrc(piece.at, piece.length, model, true), length: piece.length });
    const expected = crc32Join(crcs);
    if (await sender.sampleFileSize(model)) await sender.sampleFileDelete(model, false);
    let done = 0;
    await copyBack(sender, model, size, expected, n => { done += n; onProgress({ phase: render(text("usbsamples.phase.copyBack")), done, total: size * 2 }); });
    await sender.sampleFileDelete(model, true);
  });
}

/** Deletes the temp file of an interrupted swap that is broken. */
export function discardTemp(session) {
  return session.exclusive(async () => {
    const { model, sender } = await prepareSamples(session);
    await sender.sampleFileDelete(model, true);
  });
}

export { planChange };
