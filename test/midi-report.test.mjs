import { test } from "node:test";
import assert from "node:assert/strict";
import { collectMidi, midiReport } from "../site/app/midi-report.mjs";

const port = (id, name, extra = {}) => [id, { id, name, manufacturer: "KORG INC.", state: "connected", connection: "closed", ...extra }];
const access = (inputs, outputs) => ({ inputs: new Map(inputs), outputs: new Map(outputs) });
const web = made => ({ native: false, supported: true, requestAccess: async () => made });
const granted = { query: async () => ({ state: "granted" }) };

test("no ports: the report says so in every list, and nothing counts as an Electribe", async () => {
  const report = await collectMidi({ transport: web(access([], [])), permissions: granted, usb: "absent", app: { version: "1.3.5" }, agent: "Test/1.0" });
  assert.equal(report.access, "granted");
  assert.deepEqual(report.pairs, []);
  assert.equal(midiReport(report), [
    "MIDI-Bericht",
    "App-Version 1.3.5",
    "System: Test/1.0",
    "Übertragung: Web MIDI (Browser)",
    "MIDI-Zugriff: erlaubt",
    "USB: Keine Electribe per USB angesteckt",
    "Eingänge (0):",
    "  keine",
    "Ausgänge (0):",
    "  keine",
    "Als Electribe erkannt (0):",
    "  keine",
  ].join("\n"));
});

test("Windows jack names: every port is listed, the SOUND pair is the Electribe", async () => {
  const made = access(
    [port("i1", "electribe2 sampler SOUND"), port("i2", "MIDIIN2 (electribe2 sampler PAD/KNOB)"), port("i3", "Microsoft GS Wavetable Synth", { manufacturer: "Microsoft" })],
    [port("o1", "electribe2 sampler SOUND"), port("o2", "MIDIOUT2 (electribe2 sampler PAD/KNOB)")],
  );
  const report = await collectMidi({ transport: web(made), permissions: granted, usb: "present" });
  assert.deepEqual(report.pairs, [{ out: "electribe2 sampler SOUND", in: "electribe2 sampler SOUND" }]);
  const text = midiReport(report);
  assert.match(text, /^Eingänge \(3\):\n {2}electribe2 sampler SOUND \[KORG INC\., connected, closed\]\n {2}MIDIIN2 \(electribe2 sampler PAD\/KNOB\) \[KORG INC\., connected, closed\]\n {2}Microsoft GS Wavetable Synth \[Microsoft, connected, closed\]$/m);
  assert.match(text, /^Ausgänge \(2\):$/m);
  assert.match(text, /^Als Electribe erkannt \(1\):\n {2}Ausgang „electribe2 sampler SOUND“ mit Eingang „electribe2 sampler SOUND“$/m);
});

test("a Korg port without electribe in its name is listed but not taken", async () => {
  const made = access([port("i", "KORG USB-MIDI Device")], [port("o", "KORG USB-MIDI Device")]);
  const text = midiReport(await collectMidi({ transport: web(made), permissions: granted }));
  assert.match(text, /^ {2}KORG USB-MIDI Device \[KORG INC\., connected, closed\]$/m);
  assert.match(text, /^Als Electribe erkannt \(0\):\n {2}keine$/m);
});

test("Web MIDI not yet allowed: opening the settings does not ask the browser, a click does", async () => {
  let asked = 0;
  const transport = { native: false, supported: true, requestAccess: async () => { asked++; return access([], []); } };
  const prompt = { query: async () => ({ state: "prompt" }) };
  const quiet = await collectMidi({ transport, permissions: prompt });
  assert.equal(asked, 0);
  assert.match(midiReport(quiet), /^MIDI-Zugriff: noch nicht gefragt/m);
  assert.equal((await collectMidi({ transport, permissions: prompt, ask: true })).access, "granted");
  assert.equal(asked, 1);
});

test("a refused or failing request shows its message", async () => {
  const fail = error => ({ native: false, supported: true, requestAccess: async () => { throw error; } });
  const denied = Object.assign(new Error("Permission denied."), { name: "NotAllowedError" });
  const refused = midiReport(await collectMidi({ transport: fail(denied), permissions: granted }));
  assert.match(refused, /^MIDI-Zugriff: abgelehnt\nFehler: Permission denied\.$/m);
  const broken = midiReport(await collectMidi({ transport: fail(new Error("driver gone")), permissions: granted }));
  assert.match(broken, /^MIDI-Zugriff: Fehler \(driver gone\)$/m);
  const none = midiReport(await collectMidi({ transport: { native: false, supported: false }, permissions: granted }));
  assert.match(none, /^MIDI-Zugriff: nicht verfügbar$/m);
});

test("native MIDI lists every system port, not only the Electribe ones the transport keeps", async () => {
  const transport = {
    native: true,
    supported: true,
    requestAccess: async () => access([["i", { id: "i", name: "electribe2 sampler" }]], [["o", { id: "o", name: "electribe2 sampler" }]]),
    listPorts: async () => ({ inputs: [{ id: "i", name: "electribe2 sampler" }, { id: "k", name: "IAC Driver Bus 1" }], outputs: [{ id: "o", name: "electribe2 sampler" }] }),
  };
  const text = midiReport(await collectMidi({ transport }));
  assert.match(text, /^Übertragung: Natives MIDI \(App\)$/m);
  assert.match(text, /^Eingänge \(2\):\n {2}electribe2 sampler\n {2}IAC Driver Bus 1$/m);
  assert.match(text, /^Als Electribe erkannt \(1\):$/m);
});

test("Korg's own driver on Windows: its jack port names bring a hint to remove it; elsewhere and with Windows' driver none", async () => {
  const windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)";
  const hint = /^Hinweis: Die Portnamen kommen von Korgs eigenem USB-MIDI-Treiber\./m;
  const report = async (made, agent) => midiReport(await collectMidi({ transport: web(made), permissions: granted, agent }));
  const korg = access([port("i", "electribe2 sampler 1 PAD/KNOB")], [port("o", "electribe2 sampler 1 SOUND")]);
  assert.match(await report(korg, windows), hint);
  assert.match(await report(access([port("i", "Electribe 3 PAD/KNOB")], [port("o", "Electribe 3 SOUND")]), windows), hint, "also after the rename");
  assert.doesNotMatch(await report(access([port("i", "Electribe 3")], [port("o", "Electribe 3")]), windows), /Hinweis/, "Windows' own driver");
  assert.doesNotMatch(await report(korg, "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"), /Hinweis/, "not on a Mac");
});
