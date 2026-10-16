import { test } from "node:test";

/** `test` for the tests of one part: of all that are defined, every `parts`-th one from `index`. */
export function only(index, parts) {
  let n = 0;
  return (...args) => { if (n++ % parts === index) test(...args); };
}
