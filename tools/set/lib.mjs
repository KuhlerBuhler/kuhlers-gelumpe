/**
 * The set helpers of src/pattern-set.mjs, plus reading a backup from disk.
 */
import { readFileSync } from "node:fs";
import { PatternFile } from "../../src/pattern.mjs";

export * from "../../src/pattern-set.mjs";

export const loadSet = path => PatternFile.parse(readFileSync(path));
