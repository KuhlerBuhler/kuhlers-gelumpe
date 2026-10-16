/**
 * The parts that need a filesystem. Everything else runs in a browser too.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { VsbImage } from "./image.mjs";
import { parseUnits, setUnits } from "./units.mjs";

const UNITS_JSON = fileURLToPath(new URL("../data/units.json", import.meta.url));

export function readUnits(path = UNITS_JSON) {
  return setUnits(parseUnits(JSON.parse(readFileSync(path, "utf8"))));
}

export function readImage(path) {
  return new VsbImage(readFileSync(path));
}

export function writeImage(image, path) {
  writeFileSync(path, Buffer.from(image.bytes));
}
