import test from 'node:test';
import assert from 'node:assert/strict';
import { electribePorts } from '../src/session.mjs';

const access = (ins, outs) => ({
  inputs: new Map(ins.map((name, i) => [`in${i}`, { name }])),
  outputs: new Map(outs.map((name, i) => [`out${i}`, { name }])),
});
const names = ports => ports.map(p => [p.out.name, p.in.name]);

test('ports of the same name pair, SOUND before PAD/KNOB', () => {
  const both = ['electribe2 sampler SOUND', 'electribe2 sampler PAD/KNOB'];
  assert.deepEqual(names(electribePorts(access(both, both))), [['electribe2 sampler SOUND', 'electribe2 sampler SOUND']]);
});

test('Windows names the second jack MIDIIN2 and MIDIOUT2', () => {
  const ports = electribePorts(access(['electribe2 sampler', 'MIDIIN2 (electribe2 sampler)'], ['electribe2 sampler', 'MIDIOUT2 (electribe2 sampler)']));
  assert.deepEqual(names(ports), [['electribe2 sampler', 'electribe2 sampler']]);
});

test('Windows with the Electribe 3 name: one input and one output named after their jack still pair', () => {
  const ports = electribePorts(access(['Electribe 3 PAD/KNOB'], ['Electribe 3 SOUND']));
  assert.deepEqual(names(ports), [['Electribe 3 SOUND', 'Electribe 3 PAD/KNOB']]);
});

test('Windows MIDI Services names the stock ports after their jack too', () => {
  const ports = electribePorts(access(['electribe2 sampler 1 PAD/KNOB'], ['electribe2 sampler 1 SOUND']));
  assert.deepEqual(names(ports), [['electribe2 sampler 1 SOUND', 'electribe2 sampler 1 PAD/KNOB']]);
});

test('two different devices do not pair across', () => {
  assert.deepEqual(electribePorts(access(['electribe2 sampler PAD/KNOB'], ['Electribe 3 SOUND'])), []);
});
