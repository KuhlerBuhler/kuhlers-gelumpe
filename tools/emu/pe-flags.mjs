/**
 * Clears Control Flow Guard in a Windows executable's PE header.
 *
 * PyInstaller's bootloader is built with CFG. Unicorn runs the firmware as code
 * it generates at run time, and with CFG on, Windows 10 ends the process at the
 * first jump into that code, without any message (Unicorn 2.1.4; measured on a
 * user's PC, docs/messungen/2026-10-17-windows-cfg.md).
 */
import { readFileSync, writeFileSync } from "node:fs";

const GUARD_CF = 0x4000;

/** Offset of DllCharacteristics in the optional header, or -1 if `bytes` is no PE file. */
export function dllCharacteristicsAt(bytes) {
  if (bytes.length < 0x40 || bytes[0] !== 0x4d || bytes[1] !== 0x5a) return -1;
  const pe = bytes.readUInt32LE(0x3c);
  if (pe + 24 + 72 > bytes.length || bytes.readUInt32LE(pe) !== 0x4550) return -1;
  return pe + 24 + 70;   // same place in PE32 and PE32+
}

/** Clears the CFG flag in place; returns true if it was set. */
export function clearCfg(bytes) {
  const at = dllCharacteristicsAt(bytes);
  if (at < 0) throw new Error("keine Windows-Programmdatei");
  const flags = bytes.readUInt16LE(at);
  bytes.writeUInt16LE(flags & ~GUARD_CF, at);
  return (flags & GUARD_CF) !== 0;
}

export function clearCfgInFile(file) {
  const bytes = readFileSync(file);
  if (clearCfg(bytes)) writeFileSync(file, bytes);
}
