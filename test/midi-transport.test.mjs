import { test } from "node:test";
import assert from "node:assert/strict";
import { createMidiTransport } from "../site/app/midi.mjs";

function fixture({ native = true, invoke, timeout } = {}) {
  const calls = [];
  const payloads = new Map();
  let channel, browserRequests = 0;
  const access = { inputs: new Map(), outputs: new Map() };
  const scope = {
    __GELUMPE_APP: { nativeMidi: native },
    navigator: { requestMIDIAccess: async () => { browserRequests++; return access; } },
    __TAURI__: { core: {
      Channel: class {
        constructor() { channel = this; }
        emit({ bytes, ...event }) {
          if (event.type === "message") payloads.set(`${event.sessionId}:${event.sequence}`, bytes);
          return this.onmessage(event);
        }
      },
      invoke: async (command, args) => {
        calls.push({ command, args });
        if (invoke) { const result = invoke(command, args); if (result !== undefined) return result; }
        if (command === "midi_list") return { inputs: [{ id: "in", name: "electribe" }], outputs: [{ id: "out", name: "electribe" }] };
        if (command === "midi_open") return { sessionId: "session" };
        if (command === "midi_close") return { state: "closed" };
        if (command === "midi_read") return payloads.get(`${args.sessionId}:${args.sequence}`);
        if (command === "midi_ack") payloads.delete(`${args.sessionId}:${args.sequence}`);
      },
    } },
  };
  return { transport: createMidiTransport(scope, { sendTimeout: timeout }), calls, access, get channel() { return channel; }, get browserRequests() { return browserRequests; } };
}
const pair = access => ({ in: [...access.inputs.values()][0], out: [...access.outputs.values()][0], name: "electribe" });

test("native MIDI lists without opening ports or requesting browser permission", async () => {
  const f = fixture();
  assert.equal(f.transport.native, true);
  const access = await f.transport.requestAccess();
  assert.equal(access.inputs.size, 1);
  assert.deepEqual(f.calls.map(c => c.command), ["midi_list"]);
  assert.equal(f.browserRequests, 0);
});

test("browser and Windows use Web MIDI unless native MIDI is explicitly enabled", async () => {
  const f = fixture({ native: false });
  assert.equal(f.transport.native, false);
  assert.equal(await f.transport.requestAccess(), f.access);
  assert.equal(f.browserRequests, 1);
  assert.deepEqual(f.calls, []);
});

test("native failure is visible and never falls back to Web MIDI", async () => {
  const f = fixture({ invoke: () => { throw new Error("ALSA unavailable"); } });
  await assert.rejects(f.transport.requestAccess(), /ALSA unavailable/);
  assert.equal(f.browserRequests, 0);
});

test("ambiguous native names are rejected without opening any port", async () => {
  const f = fixture({ invoke: () => ({ inputs: [{ id: "a", name: "electribe" }, { id: "b", name: "electribe" }], outputs: [{ id: "o", name: "electribe" }] }) });
  await assert.rejects(f.transport.requestAccess(), /eindeutig/i);
  assert.deepEqual(f.calls.map(c => c.command), ["midi_list"]);
});

test("native messages preserve bytes and ignore other or closed sessions", async () => {
  const f = fixture();
  const access = await f.transport.requestAccess(), port = pair(access), received = [];
  await f.transport.openPort(port);
  port.in.onmidimessage = event => received.push([...event.data]);
  await f.channel.emit({ sessionId: "old", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 1, 0xf7] });
  await port.out.send(Uint8Array.of(0xf0, 2, 0xf7));
  assert.deepEqual(received, [[0xf0, 1, 0xf7]]);
  assert.deepEqual(f.calls.find(c => c.command === "midi_send").args, { sessionId: "session", bytes: [0xf0, 2, 0xf7] });
  await f.transport.closePort(port);
  await f.transport.closePort(port);
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 3, 0xf7] });
  assert.equal(received.length, 1);
  assert.equal(f.calls.filter(c => c.command === "midi_close").length, 1);
  await assert.rejects(port.out.send([0xf0, 0xf7]), /getrennt/i);
});

test("native disconnect invalidates the port and closes its resource", async () => {
  const f = fixture(), access = await f.transport.requestAccess(), port = pair(access);
  await f.transport.openPort(port);
  const states = [];
  access.onstatechange = event => states.push(event);
  await f.channel.emit({ sessionId: "session", type: "disconnected", code: "unplugged", message: "USB getrennt" });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(states[0].port, port.out);
  assert.equal(port.out.state, "disconnected");
  assert.equal(f.calls.at(-1).command, "midi_close");
});

test("native send errors and hangs close the session before another send", async () => {
  for (const hangs of [false, true]) {
    const f = fixture({ timeout: () => 5, invoke: command => {
      if (command === "midi_send") return hangs ? new Promise(() => {}) : Promise.reject(new Error("send failed"));
    } });
    const access = await f.transport.requestAccess(), port = pair(access);
    await f.transport.openPort(port);
    await assert.rejects(port.out.send([0xf0, 0xf7]), hangs ? /zu lange/i : /send failed/);
    assert.equal(f.calls.at(-1).command, "midi_close");
    await assert.rejects(port.out.send([0xf0, 0xf7]), /getrennt/i);
    assert.equal(f.calls.filter(c => c.command === "midi_send").length, 1);
  }
});

test("browser ports release both connections when switching or closing", async () => {
  const f = fixture({ native: false });
  const closed = [];
  await f.transport.closePort({ in: { close: async () => closed.push("in") }, out: { close: async () => closed.push("out") } });
  assert.deepEqual(closed.sort(), ["in", "out"]);
});

test("native page teardown closes every active session", async () => {
  const f = fixture(), access = await f.transport.requestAccess(), port = pair(access);
  await f.transport.openPort(port);
  await f.transport.dispose();
  assert.equal(f.calls.at(-1).command, "midi_close");
  await assert.rejects(port.out.send([0xf0, 0xf7]), /getrennt/i);
});

test("disconnect delivered while native open resolves cannot leave a live session", async () => {
  const f = fixture({ invoke: (command, args) => {
    if (command === "midi_open") {
      args.events.emit({ sessionId: "early", type: "error", message: "connection lost" });
      return { sessionId: "early" };
    }
  } });
  const access = await f.transport.requestAccess(), port = pair(access);
  await assert.rejects(f.transport.openPort(port), /getrennt/i);
  assert.equal(f.calls.at(-1).command, "midi_close");
});

test("quarantined close reports that the native port is still releasing", async () => {
  const f = fixture({ invoke: command => {
    if (command === "midi_close") return { state: "quarantined" };
    if (command === "midi_send") return Promise.reject(Object.assign(new Error("send timeout"), { code: "send-timeout" }));
  } });
  const access = await f.transport.requestAccess(), port = pair(access), states = [];
  access.onstatechange = state => states.push(state);
  await f.transport.openPort(port);
  await assert.rejects(port.out.send([0xf0, 0xf7]), { code: "send-timeout" });
  assert.equal(states[0].quarantined, true);
  assert.match(states[0].message, /freigegeben/i);
  assert.deepEqual(await f.transport.closePort(port), { state: "quarantined" });
});

test("Tauri string rejections become errors with a readable message", async () => {
  const f = fixture({ invoke: () => Promise.reject("ALSA port unavailable") });
  await assert.rejects(f.transport.requestAccess(), { message: "ALSA port unavailable" });
});

test("a quarantined close is refreshed once the native port has been released", async () => {
  let released = false;
  const f = fixture({ invoke: command => command === "midi_close" ? { state: released ? "closed" : "quarantined" } : undefined });
  const port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  assert.deepEqual(await f.transport.closePort(port), { state: "quarantined" });
  released = true;
  assert.deepEqual(await f.transport.closePort(port), { state: "closed" });
  await f.transport.closePort(port);
  assert.equal(f.calls.filter(c => c.command === "midi_close").length, 2);
});

test("concurrent closes share the same native close operation", async () => {
  let complete;
  const f = fixture({ invoke: command => command === "midi_close" ? new Promise(resolve => { complete = resolve; }) : undefined });
  const port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  const first = f.transport.closePort(port), second = f.transport.closePort(port);
  complete({ state: "quarantined" });
  await Promise.all([first, second]);
  assert.equal(f.calls.filter(c => c.command === "midi_close").length, 1);
});

test("the native disconnected envelope has a readable German fallback", async () => {
  const f = fixture(), access = await f.transport.requestAccess(), port = pair(access), states = [];
  access.onstatechange = state => states.push(state);
  await f.transport.openPort(port);
  await f.channel.emit({ sessionId: "session", type: "disconnected" });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(states[0].message, /MIDI-Verbindung.*getrennt/);
  assert.doesNotMatch(states[0].message, /object Object|undefined/);
});

test("native frame credits are acknowledged after consumption, including stale and closed frames", async () => {
  const f = fixture(), port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  port.in.onmidimessage = () => assert.equal(f.calls.filter(c => c.command === "midi_ack").length, 0);
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 1, 0xf7] });
  await f.channel.emit({ sessionId: "old", type: "message", sequence: 2, bytes: [0xf0, 2, 0xf7] });
  await f.transport.closePort(port);
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 3, bytes: [0xf0, 3, 0xf7] });
  assert.deepEqual(f.calls.filter(c => c.command === "midi_ack").map(c => c.args), [
    { sessionId: "session", sequence: 1 }, { sessionId: "old", sequence: 2 }, { sessionId: "session", sequence: 3 },
  ]);
});

test("early native frames keep their credits until open completes", async () => {
  let finish;
  const f = fixture({ invoke: (command, args) => {
    if (command !== "midi_open") return;
    args.events.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
    return new Promise(resolve => { finish = resolve; });
  } });
  const port = pair(await f.transport.requestAccess()), opening = f.transport.openPort(port);
  assert.equal(f.calls.some(c => c.command === "midi_ack"), false);
  finish({ sessionId: "session" });
  await opening;
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(f.calls.find(c => c.command === "midi_ack").args, { sessionId: "session", sequence: 1 });
});

test("throwing message handlers still release native credits", async () => {
  const f = fixture(), port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  port.in.onmidimessage = () => { throw new Error("handler failed"); };
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(f.calls.find(c => c.command === "midi_ack").args, { sessionId: "session", sequence: 1 });
});

test("an active credit acknowledgement failure closes the native session", async () => {
  const f = fixture({ invoke: command => command === "midi_ack" ? Promise.reject({ code: "ack_failed", message: "credit failed" }) : undefined });
  const port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(port.out.state, "disconnected");
  assert.ok(f.calls.some(c => c.command === "midi_close"));
});

test("a stale credit acknowledgement failure leaves the active session intact", async () => {
  const f = fixture({ invoke: command => command === "midi_ack" ? Promise.reject({ code: "old_session", message: "old credit" }) : undefined });
  const port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  await f.channel.emit({ sessionId: "old", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(port.out.state, "connected");
  assert.equal(f.calls.some(c => c.command === "midi_close"), false);
});


test("native message payloads are pulled in order before returning their credits", async () => {
  let finish;
  const f = fixture({ invoke: (command, args) => {
    if (command === "midi_read" && args.sequence === 1) return new Promise(resolve => { finish = resolve; });
  } });
  const port = pair(await f.transport.requestAccess()), received = [];
  await f.transport.openPort(port);
  port.in.onmidimessage = event => received.push([...event.data]);
  const first = f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 1, 0xf7] });
  const second = f.channel.emit({ sessionId: "session", type: "message", sequence: 2, bytes: [0xf0, 2, 0xf7] });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(f.calls.filter(c => c.command === "midi_read").map(c => c.args.sequence), [1]);
  assert.equal(f.calls.some(c => c.command === "midi_ack"), false);
  assert.deepEqual(received, []);
  finish([0xf0, 1, 0xf7]);
  await Promise.all([first, second]);
  assert.deepEqual(received, [[0xf0, 1, 0xf7], [0xf0, 2, 0xf7]]);
  assert.deepEqual(f.calls.filter(c => ["midi_read", "midi_ack"].includes(c.command)).map(c => [c.command, c.args.sequence]), [["midi_read", 1], ["midi_ack", 1], ["midi_read", 2], ["midi_ack", 2]]);
});

test("stale and closed native notifications return credits without pulling bytes", async () => {
  const f = fixture(), port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  await f.channel.emit({ sessionId: "old", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  await f.transport.closePort(port);
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 2, bytes: [0xf0, 0xf7] });
  assert.equal(f.calls.some(c => c.command === "midi_read"), false);
  assert.equal(f.calls.filter(c => c.command === "midi_ack").length, 2);
});

test("a payload read failure closes the active context and still acknowledges the frame", async () => {
  const f = fixture({ invoke: command => command === "midi_read" ? Promise.reject({ code: "read_failed", message: "payload unavailable" }) : undefined });
  const port = pair(await f.transport.requestAccess());
  await f.transport.openPort(port);
  await f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  assert.equal(port.out.state, "disconnected");
  assert.ok(f.calls.some(c => c.command === "midi_close"));
  assert.deepEqual(f.calls.find(c => c.command === "midi_ack").args, { sessionId: "session", sequence: 1 });
});

test("disconnect invalidates an outstanding payload read and late bytes are discarded", async () => {
  let finish;
  const f = fixture({ invoke: command => command === "midi_read" ? new Promise(resolve => { finish = resolve; }) : undefined });
  const port = pair(await f.transport.requestAccess()), received = [];
  await f.transport.openPort(port);
  port.in.onmidimessage = event => received.push([...event.data]);
  const reading = f.channel.emit({ sessionId: "session", type: "message", sequence: 1, bytes: [0xf0, 0xf7] });
  await new Promise(resolve => setImmediate(resolve));
  await f.channel.emit({ sessionId: "session", type: "disconnected" });
  assert.equal(port.out.state, "disconnected");
  finish([0xf0, 0xf7]);
  await reading;
  assert.deepEqual(received, []);
  assert.deepEqual(f.calls.find(c => c.command === "midi_ack").args, { sessionId: "session", sequence: 1 });
});
