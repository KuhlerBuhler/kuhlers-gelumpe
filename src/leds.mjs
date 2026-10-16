/**
 * Which front LEDs are lit, read from the firmware's LED manager
 * (data/map/screen.mjs, measure:2026-10-14/led-zustand-ram).
 */
import { BLOCKS } from "./map/index.mjs";
import { pointerBlock } from "./map/address.mjs";
import { readU32le } from "./bytes.mjs";

const LEDS = BLOCKS.get("ledState");
const { offset, stride, count, brightness } = LEDS.meta;

// Every entry starts with its own LED number; that is how a stale or wrong address shows.
const numbered = bytes => Array.from({ length: count }, (_, i) => bytes[i * stride] === i).every(Boolean);

/**
 * @param {(addr: number, length: number) => Promise<Uint8Array>} readRam
 * @param {number|null} at the table address a former call returned, or null to look it up
 * @returns {Promise<{at: number, leds: Object<number, number>}>} the brightness, 1 to 255, of every lit LED
 */
export async function readLeds(readRam, at = null) {
  const lookup = async () => (await pointerBlock("ledState", async a => readU32le(await readRam(a, 4)))) + offset;
  let here = at ?? await lookup();
  let bytes = await readRam(here, LEDS.size);
  if (!numbered(bytes) && at !== null) {
    here = await lookup();
    bytes = await readRam(here, LEDS.size);
  }
  if (!numbered(bytes)) throw new Error("Die LED-Tabelle der Firmware ist am erwarteten Ort nicht zu erkennen.");
  const leds = {};
  for (let i = 0; i < count; i++) if (bytes[i * stride + brightness]) leds[i] = bytes[i * stride + brightness];
  return { at: here, leds };
}
