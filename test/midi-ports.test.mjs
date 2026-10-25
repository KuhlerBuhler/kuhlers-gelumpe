import { test } from "node:test";
import assert from "node:assert/strict";
import { electribePorts } from "../src/session.mjs";

const access = (outs, ins) => ({
  outputs: new Map(outs.map(name => [`o-${name}`, { name }])),
  inputs: new Map(ins.map(name => [`i-${name}`, { name }])),
});

test("Windows' second jack is no second Electribe: one pair, the first jack", () => {
  const ports = electribePorts(access(
    ["electribe2 sampler", "MIDIOUT2 (electribe2 sampler)"],
    ["electribe2 sampler", "MIDIIN2 (electribe2 sampler)"],
  ));
  assert.deepEqual(ports.map(p => [p.out.name, p.in.name]), [["electribe2 sampler", "electribe2 sampler"]]);
});

test("an output without an input of its name is not offered", () => {
  const ports = electribePorts(access(["MIDIOUT2 (electribe2 sampler)", "electribe2 sampler"], ["electribe2 sampler"]));
  assert.deepEqual(ports.map(p => p.name), ["electribe2 sampler"]);
  assert.equal(electribePorts(access(["MIDIOUT2 (electribe2 sampler)"], [])).length, 0);
});

test("only the second jack paired: MIDIOUT2 goes with MIDIIN2", () => {
  const ports = electribePorts(access(["MIDIOUT2 (electribe2 sampler)"], ["MIDIIN2 (electribe2 sampler)"]));
  assert.deepEqual(ports.map(p => [p.out.name, p.in.name]), [["MIDIOUT2 (electribe2 sampler)", "MIDIIN2 (electribe2 sampler)"]]);
});

test("named jacks: SOUND is taken, PAD/KNOB of the same device is not", () => {
  const names = ["electribe2 sampler _ PAD/KNOB", "electribe2 sampler _ SOUND"];
  assert.deepEqual(electribePorts(access(names, names)).map(p => p.name), ["electribe2 sampler _ SOUND"]);
});

test("two different Electribes still both show", () => {
  const names = ["electribe2 sampler", "electribe2"];
  assert.deepEqual(electribePorts(access(names, names)).map(p => p.name), names);
});

test("other MIDI devices are ignored", () => {
  assert.equal(electribePorts(access(["IAC Bus 1"], ["IAC Bus 1"])).length, 0);
});
