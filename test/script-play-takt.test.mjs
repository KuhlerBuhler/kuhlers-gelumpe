import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { LED_NAMES } from "../data/script/names.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";

const led = name => LED_NAMES.find(n => n.name === name).value;
const STOP = led("STOP");
const PLAY = led("PLAY");
const PLAY_BLUE = led("PLAY_BLUE");
// values the plugin never writes: the PLAY LEDs keep them as long as it leaves them to the firmware
const FIRMWARE_PLAY = 77;
const FIRMWARE_PLAY_BLUE = 33;
const SOURCE = PRESETS.find(p => p.id === "playtakt").source;

/** STOP-Takt (id playtakt) in the background. The simulator's firmware drives neither STOP nor PLAY, tools/emu/timer_cases.py checks the firmware. */
function plugin() {
  const result = compile(SOURCE, { name: "playtakt" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  assert.equal(device.apps.length, 0, "no app, a background plugin");
  device.leds[PLAY] = FIRMWARE_PLAY;
  device.leds[PLAY_BLUE] = FIRMWARE_PLAY_BLUE;
  device.run(2);
  /** The STOP LED for `frames` frames, one value per frame. */
  const watch = frames => Array.from({ length: frames }, () => { device.run(1); return device.leds[STOP]; });
  const playUntouched = what => {
    assert.equal(device.leds[PLAY], FIRMWARE_PLAY, `${what}: PLAY stays the firmware's`);
    assert.equal(device.leds[PLAY_BLUE], FIRMWARE_PLAY_BLUE, `${what}: PLAY_BLUE stays the firmware's`);
  };
  return { device, hw: device.hardware, watch, playUntouched };
}

test("STOP-Takt: the title, and the source never names the PLAY LEDs", () => {
  assert.equal(PRESETS.find(p => p.id === "playtakt").title, "STOP-Takt");
  assert.doesNotMatch(SOURCE, /korg\.led\.PLAY/);
  assert.match(SOURCE, /korg\.led\.STOP/);
});

test("STOP-Takt: stopped, the STOP LED is off and PLAY is left alone", () => {
  const p = plugin();
  assert.ok(p.watch(50).every(v => v === 0), "no blinking while stopped");
  p.playUntouched("stopped");
});

test("STOP-Takt: playing, the STOP LED blinks on the beat and follows the tempo", () => {
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
  // short: one step of the four in a beat, 125 ms at 120 BPM, about 3 frames
  const seen = p.watch(100);
  const lit = seen.reduce((runs, v, i) => (v === 255 ? (seen[i - 1] === 255 ? runs.with(-1, runs.at(-1) + 1) : [...runs, 1]) : runs), []).slice(1, -1);
  assert.ok(lit.length >= 3 && lit.every(n => n >= 2 && n <= 4), `lit for one step: ${lit}`);
  p.playUntouched("playing");
  p.hw.tempo = 600;
  assert.ok(ons(60).every(d => d === 25), "on every beat at 60 BPM: 1000 ms, 25 frames");
  p.playUntouched("playing at 60 BPM");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("STOP-Takt: STOP and pause turn the STOP LED off, PLAY again blinks again, PLAY stays the firmware's", () => {
  const p = plugin();
  const lastLit = () => {
    let last = 255;
    for (let i = 0; i < 40 && !(last === 0 && p.device.leds[STOP] === 255); i++) { last = p.device.leds[STOP]; p.device.run(1); }
    assert.equal(p.device.leds[STOP], 255, "a beat just lit it, its timer to go dark is pending");
  };
  p.hw.api()["korg.play"]();
  lastLit();
  p.hw.api()["korg.stop"]();
  assert.ok(p.watch(60).every(v => v === 0), "off after STOP");
  p.playUntouched("after STOP");
  p.hw.api()["korg.play"]();
  assert.ok(p.watch(40).includes(255), "blinks again after PLAY");
  // the firmware's pause: transport 2, its stop event
  lastLit();
  p.hw.transport = 2;
  p.hw.emit("stop");
  assert.ok(p.watch(60).every(v => v === 0), "off in the pause, no blinking");
  p.playUntouched("paused");
});
