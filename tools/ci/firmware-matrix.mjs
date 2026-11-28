import { fileURLToPath } from "node:url";
import { HACKTRIBE_SHA256, STOCK_SHA256, SYNTH_SHA256, HACKTRIBE_BLUE_SHA256 } from "../../src/patcher.mjs";

const FIRMWARES = [
  { name: "hacktribe", secret: "E2_VSB_URL", sha256: HACKTRIBE_SHA256 },
  { name: "red", secret: "E2_VSB_STOCK_URL", sha256: STOCK_SHA256 },
  { name: "blue", secret: "E2_VSB_SYNTH_URL", sha256: SYNTH_SHA256 },
  { name: "hacktribe-blue", secret: "E2_VSB_URL", sha256: HACKTRIBE_SHA256, blue_head: HACKTRIBE_BLUE_SHA256 },
];

export function firmwareMatrix(count, { full = true, cases = "all" } = {}) {
  if (!Number.isSafeInteger(count) || count < 1 || count > 64) throw new Error("firmware shards must be an integer from 1 to 64");
  if (typeof full !== "boolean" || typeof cases !== "string") throw new Error("full must be boolean and cases must be a string");
  const firmwares = FIRMWARES.map(f => ({ ...f, artifact: `firmware-shard-${f.name}--${count}` }));
  const editor = full || cases === "all" || cases.split(",").some(c => c.trim() === "fx_card_cases");
  const smokes = firmwares.filter(f => f.name !== "hacktribe-blue").map(f => ({ ...f, kind: "start" }));
  if (editor) smokes.push(...firmwares.filter(f => f.name !== "hacktribe-blue").map(f => ({ ...f, kind: "editor" })));
  return { firmwares, parts: Array.from({ length: count }, (_, i) => i + 1), smokes };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv[3] !== undefined && !["true", "false"].includes(process.argv[3])) throw new Error("full must be true or false");
  const matrix = firmwareMatrix(Number(process.argv[2]), { full: process.argv[3] !== "false", cases: process.argv[4] ?? "all" });
  for (const [key, value] of Object.entries(matrix)) console.log(`${key}=${JSON.stringify(value)}`);
}
