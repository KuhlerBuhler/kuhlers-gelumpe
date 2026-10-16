import { readU32le } from "./bytes.mjs";

export function checkInstruction(bytes, instruction, where) {
  const { expected, mask, range } = instruction;
  const word = readU32le(bytes, 0);
  const immediate = bytes[0];
  if (bytes.length !== 4 || (word & mask) >>> 0 !== (expected & mask) >>> 0 ||
      immediate < range[0] || immediate > range[1]) {
    throw new Error(`Instruktion ${where} ist nicht der erwartete ARM-Menüzähler. Schreiben gesperrt.`);
  }
}

export function checkReadGuard(step, bytes) {
  if (step.guard) checkInstruction(bytes, step.guard, `bei 0x${step.target.addr.toString(16)}`);
}
