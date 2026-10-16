/**
 * The emulator service (tools/emu/server.py) with the user's own VSB, as the
 * port pair DeviceSession expects. For local tests only: it needs the VSB,
 * Unicorn and tools/emu/.venv.
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { release, tempDir, track } from "./lifetime.mjs";

const server = fileURLToPath(new URL("../../tools/emu/server.py", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32"
  ? "../../tools/emu/.venv/Scripts/python.exe"
  : "../../tools/emu/.venv/bin/python", import.meta.url));
const ORIGIN = "http://127.0.0.1:8737";
const HTTP_TIMEOUT_MS = 60_000;     // a request the service never answers fails the test instead of hanging it

/** 128x64 display bytes (8 pages, bit 0 the top row) as 32 lines of block characters. */
export function asciiDisplay(bytes) {
  const lit = (x, y) => (bytes[(y >> 3) * 128 + x] >> (y & 7)) & 1;
  const lines = [];
  for (let y = 0; y < 64; y += 2) {
    let line = "";
    for (let x = 0; x < 128; x++) line += [" ", "\u2584", "\u2580", "\u2588"][lit(x, y) * 2 + lit(x, y + 1)];
    lines.push(line.trimEnd());
  }
  return lines.join("\n");
}

export const emuPython = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");

const STOP_GRACE_MS = 5_000;       // the service saves the card on SIGTERM; one that does not leave in time is killed

/**
 * Starts the service and waits until it listens, without firmware. It ends with this process
 * (`--parent-pid`, so also after a SIGKILL) and, when it made its own folder, takes that folder along
 * (`--ephemeral`); `allowOrigin` lets a page on another origin use it. Without `sdDir` the card and the flash live in a fresh temporary folder, so a test
 * never touches ~/.gelumpe/sd and nothing is left behind.
 */
export async function startService({ sdDir = null, unthrottled = true, allowOrigin = [] } = {}) {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const token = randomBytes(12).toString("base64url");
  const ownDir = sdDir ? null : tempDir("gelumpe-sd-");
  const cards = sdDir || ownDir;
  const child = track(spawn(emuPython(), [
    server, "--port", String(port), "--sd-dir", cards, "--parent-pid", String(process.pid),
    ...(ownDir ? ["--ephemeral"] : []), ...(unthrottled ? ["--unthrottled"] : []), ...allowOrigin.flatMap(o => ["--allow-origin", o]),
  ], { env: { ...process.env, E2_EMU_TOKEN: token }, stdio: ["ignore", "pipe", "pipe"] }));
  const exited = new Promise(resolve => child.once("exit", resolve));
  const stop = async () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill();
      const timer = setTimeout(() => child.kill("SIGKILL"), STOP_GRACE_MS);
      await exited;
      clearTimeout(timer);
    }
    if (ownDir) release(ownDir);
  };
  let output = "";
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`emulator service did not start: ${output}`)), 10_000);
      const seen = chunk => {
        output += chunk;
        if (output.includes("Editor öffnen")) { clearTimeout(timer); resolve(); }
      };
      child.stdout.on("data", seen);
      child.stderr.on("data", seen);
      child.on("exit", code => { clearTimeout(timer); reject(new Error(`emulator service exited ${code}: ${output}`)); });
    });
  } catch (error) {
    await stop();
    throw error;
  }
  return { child, port, token, cards, stop };
}

/**
 * Starts the service, loads the VSB, runs the firmware until `bootSeconds` of device time.
 * The service runs unthrottled (as fast as the CPU goes); `settle(ms)` waits in device time, which is
 * what a pause between two key presses means to the firmware, and `status.device_ms` is its clock.
 * The virtual SD cards live in `sdDir`, a fresh temporary folder unless given, so a test never
 * touches the cards in ~/.gelumpe/sd. `prepare(api)` runs before the firmware starts, to set up a card.
 */
export async function startEmulator(vsbPath, options = {}) {
  const service = await startService(options);
  try {
    return await boot(service, vsbPath, options);
  } catch (error) {
    await service.stop();
    throw error;
  }
}

async function boot({ port, token, cards, stop: stopService }, vsbPath, { bootSeconds = 3, prepare = null } = {}) {
  const base = `http://127.0.0.1:${port}`;
  const headers = { "X-Emu-Token": token, Origin: ORIGIN };
  const post = async (path, body) => {
    const res = await fetch(base + path, { method: "POST", body, headers, signal: AbortSignal.timeout(HTTP_TIMEOUT_MS) });
    const data = await res.json();
    if (!res.ok) throw new Error(`${path}: ${data.error}`);
    return data;
  };
  /** Any route; JSON answers come back parsed, anything else (a download) as bytes. Errors are returned, not thrown. */
  const request = async (method, path, body) => {
    const res = await fetch(base + path, { method, body, headers, signal: AbortSignal.timeout(HTTP_TIMEOUT_MS) });
    const json = res.headers.get("content-type") === "application/json";
    return { status: res.status, ok: res.ok, headers: res.headers, body: json ? await res.json() : new Uint8Array(await res.arrayBuffer()) };
  };
  if (prepare) await prepare({ post, request });

  const name = "electribe2 sampler (Emulator)";
  const midiPort = { name, in: { name, onmidimessage: null }, out: { name, send: null } };
  let queue = Promise.resolve();
  midiPort.out.send = data => { queue = queue.then(() => post("/midi", Uint8Array.from(data))); };

  const status = { device_ms: 0, state: "empty" };
  let display = new Uint8Array(1024);
  let leds = {};
  const ledLog = [];                   // every LED state the service published, oldest first
  const events = new AbortController();
  const stream = await fetch(`${base}/events?token=${token}`, { headers: { Origin: ORIGIN }, signal: events.signal });
  (async () => {
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      for await (const chunk of stream.body) {
        buffer += decoder.decode(chunk, { stream: true });
        let end;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);
          const kind = block.match(/^event: (.*)$/m)?.[1];
          const data = block.match(/^data: (.*)$/m)?.[1];
          if (kind === "status") Object.assign(status, JSON.parse(data));
          if (kind === "display") display = Uint8Array.from(atob(JSON.parse(data)), c => c.charCodeAt(0));
          if (kind === "leds") { leds = JSON.parse(data); ledLog.push(leds); }
          if (kind === "midi") {
            const hex = JSON.parse(data);
            midiPort.in.onmidimessage?.({ data: Uint8Array.from(hex.match(/../g), h => parseInt(h, 16)) });
          }
        }
      }
    } catch {}
  })();

  await post("/firmware", readFileSync(vsbPath));
  await post("/start", "{}");
  const deadline = Date.now() + 60_000;
  while (status.device_ms < bootSeconds * 1000) {
    if (status.state === "crashed") throw new Error(status.error);
    if (Date.now() > deadline) throw new Error("the firmware did not reach the main screen in time");
    await new Promise(r => setTimeout(r, 5));
  }

  return {
    port: midiPort,
    status,
    /** Wait `ms` of device time, as long as the firmware runs. */
    async settle(ms) {
      const until = status.device_ms + ms;
      const limit = Date.now() + 120_000;
      while (status.device_ms < until) {
        // "hung" is the service saying the firmware has not drawn the panel for a while (a long export); it passes
        if (status.state !== "running" && status.state !== "hung") throw new Error(`the device is ${status.state} while waiting for ${ms} ms of device time`);
        if (Date.now() > limit) throw new Error(`${ms} ms of device time did not pass in 2 minutes`);
        await new Promise(r => setTimeout(r, 2));
      }
    },
    request,
    cards,
    /** The display as text, two pixel rows per character row: what a failed step was looking at. */
    screen: () => asciiDisplay(display),
    /** The 1024 display bytes as they came, for drawing a picture. */
    rawDisplay: () => display,
    /** What the firmware last sent the panel for each LED (event leds), number to brightness. */
    leds: () => leds,
    /** How many LED states the service has published; pass it to `ledsSince` to ask what the LEDs did after this point. */
    ledMark: () => ledLog.length,
    /** The LED states from `mark` on: the one that was in force at the mark, then every later one. */
    ledsSince: mark => [ledLog[mark - 1] ?? {}, ...ledLog.slice(mark)],
    /** A control used on the front, as on the page (POST /input). */
    input: cmd => post("/input", JSON.stringify(cmd)),
    async stop() {
      events.abort();
      await stopService();
    },
  };
}
