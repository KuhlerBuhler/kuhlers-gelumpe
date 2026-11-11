import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { LED_NAMES } from "../data/script/names.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";

const led = name => LED_NAMES.find(n => n.name === name).value;
const PLAY = led("PLAY");
const PLAY_BLUE = led("PLAY_BLUE");

/** PLAY-Takt in the background. The simulator's firmware does not drive the PLAY LED, tools/emu/timer_cases.py checks that. */
function plugin() {
  const result = compile(PRESETS.find(p => p.id === "playtakt").source, { name: "playtakt" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  assert.equal(device.apps.length, 0, "no app, a background plugin");
  device.run(2);
  /** The PLAY LED for `frames` frames, one value per frame. */
  const watch = frames => Array.from({ length: frames }, () => { device.run(1); return device.leds[PLAY]; });
  return { device, hw: device.hardware, watch };
}

test("PLAY-Takt: stopped, the PLAY LED is lit", () => {
  const p = plugin();
  assert.deepEqual([p.device.leds[PLAY], p.device.leds[PLAY_BLUE]], [255, 255]);
  assert.ok(p.watch(50).every(v => v === 255), "it stays lit");
});

test("PLAY-Takt: playing, the PLAY LED blinks on the beat and follows the tempo", () => {
  const p = plugin();
  p.hw.api()["korg.play"]();
  const ons = tempo => {
    const seen = p.watch(100);
    const starts = seen.flatMap((v, i) => (v === 255 && seen[i - 1] === 0 ? [i] : []));
    assert.ok(seen.includes(0), `${tempo}: it goes dark between the beats`);
    return starts.slice(1).map((at, i) => at - starts[i]);
  };
  // 120 BPM: a beat is 500 ms, 12.5 frames of 40 ms
  assert.ok(ons(120).every(d => d === 12 || d === 13), "on every beat at 120 BPM");
  assert.equal(p.device.leds[PLAY_BLUE], p.device.leds[PLAY], "both LEDs of PLAY together");
  p.hw.tempo = 600;
  assert.ok(ons(60).every(d => d === 25), "on every beat at 60 BPM: 1000 ms, 25 frames");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("PLAY-Takt: STOP and pause leave the PLAY LED lit, PLAY again blinks again", () => {
  const p = plugin();
  p.hw.api()["korg.play"]();
  let last = 255;
  for (let i = 0; i < 40 && !(last === 0 && p.device.leds[PLAY] === 255); i++) { last = p.device.leds[PLAY]; p.device.run(1); }
  assert.equal(p.device.leds[PLAY], 255, "a beat just lit it, its timer to go dark is pending");
  p.hw.api()["korg.stop"]();
  assert.ok(p.watch(60).every(v => v === 255), "lit after STOP");
  p.hw.api()["korg.play"]();
  assert.ok(p.watch(40).includes(0), "blinks again after PLAY");
  // the firmware's pause: transport 2, its stop event; the firmware's own blink of PLAY is the emulator's case
  p.hw.transport = 2;
  p.hw.emit("stop");
  p.device.leds[PLAY] = 0;
  assert.ok(p.watch(60).every(v => v === 255), "lit in the pause, set again in each frame");
});
