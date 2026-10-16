// Compiles a key-counting test plugin and prints it with the ARM include as JSON for tap_motion_probe.py.
import { compile, formatError } from "../../src/script/compiler.mjs";
import { markProbed } from "../../src/script/blob.mjs";
import { asmInclude } from "../../src/script/arm-tables.mjs";

const source = `
  let taps = 0; let lastKey = 0; let shifts = 0; let others = 0;
  korg.onEvent("buttonPress", (key) => {
    lastKey = key;
    if (key == korg.key.TAP) { taps += 1; }
    else if (key == korg.key.SHIFT) { shifts += 1; }
    else { others += 1; }
  });
`;
const result = compile(source, { name: "tapwatch" });
if (!result.ok) throw new Error(result.errors.map(formatError).join("\n"));
const program = { blob: Buffer.from(markProbed(result.blob)).toString("hex"), symbols: result.info.symbols };
process.stdout.write(JSON.stringify({ include: asmInclude(), programs: { tapwatch: program } }));
