/**
 * Line coverage of a script run: hand `step` to the VM as `env.onStep`, run
 * the script, then ask which source lines had code that never ran.
 */
import { decodeInstructions, lineAt } from "./blob.mjs";

export class Coverage {
  constructor(script) {
    this.script = script;
    this.executed = new Set();
    this.step = offset => { this.executed.add(offset); };
  }

  /** @returns {{ all: number[], covered: number[], missing: number[] }} sorted source line numbers */
  lines() {
    const { code, lines } = this.script;
    const all = new Set();
    const covered = new Set();
    for (const ins of decodeInstructions(code).list ?? []) {
      const line = lineAt(lines, ins.offset);
      if (line === 0) continue;
      all.add(line);
      if (this.executed.has(ins.offset)) covered.add(line);
    }
    const sorted = s => [...s].sort((a, b) => a - b);
    return { all: sorted(all), covered: sorted(covered), missing: sorted([...all].filter(l => !covered.has(l))) };
  }
}
