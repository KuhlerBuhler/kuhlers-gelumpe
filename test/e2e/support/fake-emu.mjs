import { createServer } from "node:http";
import { join } from "node:path";
import { SimDevice } from "../../../src/device.mjs";
import { syxDec, syxEnc, u32le, readU32le } from "../../../src/bytes.mjs";

// A stand-in for tools/emu/server.py: same routes, same events, no firmware.
// The Python service itself is tested in tools/emu/test_server.py.
export const TOKEN = "e2e-token";

/** @param {string} origin the page origin allowed by CORS; @param {{sdDir: string}} opts the folder reported for the card */
export function fakeService(origin, { sdDir = "" } = {}) {
  const seen = { firmware: 0, flash: 0, start: null, inputs: [], midi: [], exec: [], sd: 0, sdCalls: [] };
  const card = { inserted: false };
  const hooks = { hangOnExec: false, restartOnExec: false, midiDelayMs: 0, checkOk: true, checkDelayMs: 0, checkProgress: { state: "idle" }, korg: null };
  const sim = new SimDevice({ channel: 9 });       // no image: answers the search, RAM reads come from `ram`
  const ram = new Map();                           // sparse device RAM for the screen state
  const streams = new Set();
  const display = new Uint8Array(1024);
  display[0] = 0x01;                               // top-left pixel lit
  display[127] = 0x80;                             // bottom row of page 0, right edge
  const send = (res, kind, data) => res.write(`event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`);
  const server = createServer((req, res) => {
    const cors = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Headers": "Content-Type, X-Emu-Token", "Access-Control-Allow-Methods": "GET, POST" };
    if (req.method === "OPTIONS") { res.writeHead(204, cors); res.end(); return; }
    const url = new URL(req.url, "http://x");
    if ((url.searchParams.get("token") || req.headers["x-emu-token"]) !== TOKEN) { res.writeHead(401, cors); res.end("{}"); return; }
    if (url.pathname === "/events") {
      res.writeHead(200, { ...cors, "Content-Type": "text/event-stream" });
      streams.add(res);
      req.on("close", () => streams.delete(res));
      send(res, "status", { state: "empty" });
      return;
    }
    if (req.method === "GET" && url.pathname === "/check/progress") {
      res.writeHead(200, { ...cors, "Content-Type": "application/json" });
      res.end(JSON.stringify(hooks.checkProgress));
      return;
    }
    const chunks = [];
    req.on("data", c => chunks.push(c));
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      if (url.pathname === "/firmware") { seen.firmware = body.length; seen.firmwareBody = body; }
      if (url.pathname === "/flash") seen.flash = body.length;
      if (url.pathname === "/midi") {
        seen.midi.push(body.toString("hex"));
        const reply = { 0x52: readRam, 0x53: writeAddress, 0x54: writeData, 0x57: exec }[body[6]]?.(body) ?? sim.handle(Array.from(body));
        if (reply) {
          const deliver = () => { for (const s of streams) send(s, "midi", Buffer.from(reply).toString("hex")); };
          if (hooks.midiDelayMs) setTimeout(deliver, hooks.midiDelayMs);
          else deliver();
        }
      }
      let status = { state: "loaded" };
      if (url.pathname === "/check") {
        seen.check = { length: body.length, allow: url.searchParams.get("allow"), allowCode: url.searchParams.get("allowCode"), quick: url.searchParams.get("quick"), hardware: url.searchParams.get("hardware"), pair: body };
        status = { ok: hooks.checkOk, checks: [{ id: "boot:normal", ok: true, detail: "bootet bis zum Hauptbildschirm" }, { id: "kill_switch", ok: hooks.checkOk, detail: "Taste im RAM lesbar" }], changed: [] };
      }
      if (url.pathname.startsWith("/sd")) {
        if (req.method === "GET") seen.sd++;
        else seen.sdCalls.push(url.pathname);
        if (url.pathname === "/sd/system") { seen.system = body; card.inserted = true; }
        if (url.pathname === "/sd/insert") card.inserted = true;
        if (url.pathname === "/sd/eject") card.inserted = false;
        status = { available: true, inserted: card.inserted, folder: join(sdDir, "card"), korg: hooks.korg ?? "hacktribe", busy: false, running: false };
      }
      if (url.pathname === "/input") {
        seen.inputs.push(JSON.parse(body.toString()));
        status = { state: "running", device_ms: 1300, speed: 1 };
      }
      if (url.pathname === "/start") {
        seen.start = JSON.parse(body.toString() || "{}");
        status = { state: "running", device_ms: 1200, speed: 1 };
        if (hooks.holdBoot) status.booted = false;     // the main screen is not there yet; broadcast("status", { booted: true, ... }) ends it
        for (const s of streams) {
          send(s, "status", status);
          send(s, "display", Buffer.from(display).toString("base64"));
          send(s, "leds", { 35: 255, 45: 128 });       // SEQUENCER, blue LED of pad 1
        }
      }
      const finish = () => {
        res.writeHead(200, { ...cors, "Content-Type": "application/json" });
        res.end(JSON.stringify(status));
      };
      if (url.pathname === "/check" && hooks.checkDelayMs) setTimeout(finish, hooks.checkDelayMs);
      else finish();
    });
  });
  function readRam(body) {
    const q = syxDec(Array.from(body.subarray(7, -1)));
    const addr = readU32le(q, 0);
    const bytes = Array.from({ length: readU32le(q, 4) }, (_, i) => ram.get(addr + i) ?? 0);
    return [0xf0, 0x42, 0x39, 0x00, 0x01, 0x24, 0x54, 0x52, 0x00, ...syxEnc(bytes), 0xf7];
  }
  let target = null;
  const ACK = [0xf0, 0x42, 0x39, 0x00, 0x01, 0x24, 0x21, 0xf7];
  function writeAddress(body) {
    const q = syxDec(Array.from(body.subarray(7, -1)));
    target = { addr: readU32le(q, 0), length: readU32le(q, 4) };
    return ACK;
  }
  function writeData(body) {
    poke(target.addr, syxDec(Array.from(body.subarray(7, -1))).slice(0, target.length));
    return ACK;
  }
  // Code is not run here; the address is noted, and the firmware can be made to hang afterwards.
  function exec(body) {
    seen.exec.push(readU32le(syxDec(Array.from(body.subarray(7, -1))), 0));
    if (hooks.hangOnExec) setTimeout(() => { for (const s of streams) send(s, "status", { state: "hung", error: "Die Firmware hängt." }); }, 100);
    // A restart shows as device time starting over.
    if (hooks.restartOnExec) setTimeout(() => { for (const s of streams) send(s, "status", { state: "running", device_ms: 10 }); }, 100);
    return ACK;
  }
  const poke = (addr, bytes) => bytes.forEach((b, i) => ram.set(addr + i, b));
  const word = (addr, v) => poke(addr, u32le(v));
  return new Promise(ok => server.listen(0, "127.0.0.1", () => ok({ server, seen, hooks, word, poke, ram, port: server.address().port, broadcast: (kind, data) => { for (const s of streams) send(s, kind, data); } })));
}
