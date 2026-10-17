/**
 * The emulator area: the own firmware runs in the local emulator service
 * (`npm run emu`), and its display shows here live. Files go only to that
 * service on this computer.
 */
import { el } from "./fields.mjs";
import { identify, buildOf, lackOf, hasBlechSysex } from "../../src/firmware.mjs";
import { devicePanel } from "./panel.mjs";

const VSB_SIZE = 0x200100;
const STORE = "cee.emu";
const DB = "cee.emu.files";

/** The chosen VSB stays in this browser (IndexedDB), so a reload does not forget it. It never leaves this computer. */
const keep = {
  open: () => new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore("files");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }),
  async run(mode, work) {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("files", mode);
      const req = work(tx.objectStore("files"));
      tx.oncomplete = () => { db.close(); resolve(req.result); };
      tx.onerror = () => { db.close(); reject(tx.error); };
    });
  },
  put(key, value) { return this.run("readwrite", st => st.put(value, key)).catch(() => {}); },
  get(key) { return this.run("readonly", st => st.get(key)).catch(() => undefined); },
  delete(key) { return this.run("readwrite", st => st.delete(key)).catch(() => {}); },
};

const STATE_WORDS = {
  empty: ["muted", "bereit"],
  loaded: ["muted", "geladen"],
  running: ["ok", "läuft"],
  stopped: ["muted", "angehalten"],
  crashed: ["error", "abgestürzt"],
  hung: ["warn", "hängt"],
  off: ["muted", "aus"],
};

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

/**
 * Port and key from `#emu=port:key`, kept for this tab only and taken out of
 * the address bar. Call before anything else rewrites the address.
 */
export function takeLink() {
  const m = location.hash.match(/(?:^#|&)emu=(\d+):([\w-]+)/);
  if (m) {
    const link = { port: Number(m[1]), token: m[2] };
    try { sessionStorage.setItem(STORE, JSON.stringify(link)); } catch {}
    history.replaceState(null, "", location.pathname + location.search);
    return { link, fresh: true };
  }
  try { return { link: JSON.parse(sessionStorage.getItem(STORE)) || null, fresh: false }; } catch { return { link: null, fresh: false }; }
}

/**
 * Without a link, ask the page server: `npm start` runs both and tells the
 * page where the emulator listens. A static host has no /emu.json.
 */
export async function findLink(taken) {
  if (taken.link && taken.fresh) return taken;
  if (!["127.0.0.1", "localhost"].includes(location.hostname)) return taken;
  try {
    const res = await fetch("emu.json", { cache: "no-store" });
    if (res.ok) {
      const link = await res.json();
      if (Number.isInteger(link?.port) && typeof link.token === "string") {
        try { sessionStorage.setItem(STORE, JSON.stringify(link)); } catch {}
        return { link, fresh: true };
      }
    }
  } catch {}
  return taken;
}

/** The display bytes: 8 pages of 128 columns, bit 0 the top row of a page. */
export function drawDisplay(canvas, bytes) {
  const ctx = canvas.getContext("2d");
  const style = getComputedStyle(canvas);
  const img = ctx.createImageData(128, 64);
  const on = parseColor(style.getPropertyValue("--cee-lcd-on"));
  const off = parseColor(style.getPropertyValue("--cee-lcd-off"));
  for (let y = 0; y < 64; y++) {
    for (let x = 0; x < 128; x++) {
      const lit = (bytes[(y >> 3) * 128 + x] >> (y & 7)) & 1;
      img.data.set([...(lit ? on : off), 255], (y * 128 + x) * 4);
    }
  }
  ctx.putImageData(img, 0, 0);
}

/**
 * The display as it looks: one byte per pixel, 0 clear to 15 dark, row by row (tools/emu/lcd.py).
 * Returns RGBA for a 128 x 64 image, each pixel between the off and the on colour.
 */
export function shadeImage(levels, on, off) {
  const out = new Uint8ClampedArray(128 * 64 * 4);
  for (let i = 0; i < 128 * 64; i++) {
    const mix = Math.min(levels[i], 15) / 15;
    for (let c = 0; c < 3; c++) out[i * 4 + c] = Math.round(off[c] + (on[c] - off[c]) * mix);
    out[i * 4 + 3] = 255;
  }
  return out;
}

export function drawShade(canvas, levels) {
  const ctx = canvas.getContext("2d");
  const style = getComputedStyle(canvas);
  const on = parseColor(style.getPropertyValue("--cee-lcd-on"));
  const off = parseColor(style.getPropertyValue("--cee-lcd-off"));
  ctx.putImageData(new ImageData(shadeImage(levels, on, off), 128, 64), 0, 0);
}

function parseColor(value) {
  const probe = document.createElement("canvas").getContext("2d");
  probe.fillStyle = value.trim() || "#000";
  probe.fillRect(0, 0, 1, 1);
  return Array.from(probe.getImageData(0, 0, 1, 1).data.slice(0, 3));
}

/** 5 x 7 pixel letters, one byte per column, bit 0 the top row; just what the no-firmware screen needs. */
const GLYPHS = {
  N: [0x7F, 0x04, 0x08, 0x10, 0x7F], O: [0x3E, 0x41, 0x41, 0x41, 0x3E], F: [0x7F, 0x09, 0x09, 0x09, 0x01],
  I: [0x00, 0x41, 0x7F, 0x41, 0x00], R: [0x7F, 0x09, 0x19, 0x29, 0x46], M: [0x7F, 0x02, 0x0C, 0x02, 0x7F],
  W: [0x3F, 0x40, 0x38, 0x40, 0x3F], A: [0x7E, 0x11, 0x11, 0x11, 0x7E], E: [0x7F, 0x49, 0x49, 0x49, 0x41],
};
const FAKE_BOOT_MS = 5000;

/** Display bytes (the layout drawDisplay reads) with centred lines of text, each pixel drawn `scale` times. */
export function textScreen(lines, scale = 2) {
  const bytes = new Uint8Array(1024);
  const pitch = 6 * scale;
  const top = Math.floor((64 - lines.length * 8 * scale + scale) / 2);
  lines.forEach((line, row) => {
    const left = Math.floor((128 - line.length * pitch + scale) / 2);
    [...line].forEach((ch, i) => (GLYPHS[ch] || []).forEach((col, c) => {
      for (let y = 0; y < 7; y++) {
        if (!((col >> y) & 1)) continue;
        for (let dy = 0; dy < scale; dy++) for (let dx = 0; dx < scale; dx++) {
          const px = left + i * pitch + c * scale + dx;
          const py = top + row * 8 * scale + y * scale + dy;
          bytes[(py >> 3) * 128 + px] |= 1 << (py & 7);
        }
      }
    }));
  });
  return bytes;
}

/** States the device itself shows well enough: the status line says nothing, only a screen reader hears it. */
const QUIET = new Set(["empty", "loaded", "running", "stopped", "off"]);

export function emulatorPanel(root, link = null, { deviceArea = null, sub }) {
  let events = null;
  let vsb = null;
  let base = null;
  let pushed = null;          // the VSB the service holds. It boots from its own flash after an update, so what it runs may not be `vsb`

  const deviceBox = el("div", { className: "cee-emu-device", id: "cee-emu-device" });
  const status = el("p", { className: "cee-emu-status ui-sr-only", id: "cee-emu-status", role: "status" });
  const canvas = el("canvas", { className: "cee-lcd", id: "cee-emu-lcd", width: 128, height: 64 });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "Display der emulierten Electribe");
  canvas.setAttribute("aria-describedby", "cee-side-where");

  // Inputs go out one after another, so a release never overtakes its press.
  // Knob and touch moves only send their latest value.
  let queue = Promise.resolve();
  const latest = new Map();
  let external = false;       // the drawing shows a real device; the emulator neither draws nor takes input
  let lastShade = null;
  const send = (cmd, coalesce) => {
    if (external) return;
    // A switched-off Electribe does not answer: the power key boots it, everything else is ignored.
    if (lastState !== "running" && lastState !== "hung") {
      if (cmd.kind === "power" && cmd.down) { if (fake) endFake(); else boot(); }
      return;
    }
    if (coalesce) {
      const waiting = latest.has(coalesce);
      latest.set(coalesce, cmd);
      if (waiting) return;
    }
    queue = queue.then(() => {
      const next = coalesce ? latest.get(coalesce) : cmd;
      if (coalesce) latest.delete(coalesce);
      return api("/input", JSON.stringify(next), "application/json");
    }).then(s => { if (s?.state && s.state !== lastState) showStatus(s); }, e => say("error", "Fehler", e.message));
  };
  let lastState = "empty";
  let lastDeviceMs = 0;
  // The service says when the firmware has shown its main screen. Before that the page sends no MIDI: the device
  // cannot get any while it starts, and the firmware asserts on it (MidiHandler.cpp, line 85). A service that
  // sends no `booted` (older, or a stand-in) counts as booted.
  let booted = false;
  let generation = 0;
  const device = devicePanel(send);

  // The emulated DIN MIDI as a port pair, shaped like electribePorts() output,
  // so DeviceSession, planner and gate run unchanged against the firmware.
  let midiQueue = Promise.resolve();
  const name = "electribe2 sampler (Emulator)";
  const port = {
    name,
    in: { name, onmidimessage: null },
    out: {
      name,
      send(data) {
        if (lastState === "running" && !booted) return;
        const body = Uint8Array.from(data);
        midiQueue = midiQueue.then(() => api("/midi", body)).catch(e => say("error", "Fehler", e.message));
      },
    },
    ondisconnect: null,
    get running() { return lastState === "running" && booted; },
    /** Marks the port as the emulator's: code may run on it (src/gate.mjs). */
    emulator: true,
    /** Counts the firmware's restarts, seen as device time running backwards or a new start, so a rehearsal can tell. */
    get generation() { return generation; },
  };

  let said = "";
  const say = (tone, word, text, quiet = false) => {
    const key = [tone, word, text, quiet].join("\0");
    if (key === said) return;
    said = key;
    status.replaceChildren(pill(tone, word), el("span", { textContent: ` ${text}` }));
    status.classList.toggle("ui-sr-only", quiet);
  };

  const vsbInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-emu-vsb", accept: ".VSB,.vsb" });
  const vsbInfo = el("span", { className: "ui-dropzone-files" });

  // Which build the loaded VSB is (src/firmware.mjs); the places that need Hacktribe's functions ask `lack()`.
  let build = null;
  let blech = false;
  function setBuild(bytes) {
    build = bytes ? buildOf(bytes) : null;
    blech = !!bytes && hasBlechSysex(bytes);
  }
  /** The line for the file chooser; Korg's own build is a recognised file, it only is not the measured one. */
  const describe = (name, id, saved) => {
    const when = saved ? " (vom letzten Mal)" : "";
    if (id.build === "synth") return `${name}: Firmware der blauen Electribe 2 (Synth), erkannt${when}. Presets und Modulationen gibt es für sie nicht.`;
    if (id.build === "stock") return `${name}: Korgs Original-Firmware 2.02, erkannt${when}.`;
    return id.known ? `${name}: erkannt${when}.` : `${name}: nicht erkannt${when}.${saved ? "" : ` ${id.reasons.join(" ")} Der Emulator ist für die vermessene Firmware gebaut.`}`;
  };

  const drop = (input, title, hint, info) => el("label", { className: "ui-dropzone" }, [
    input,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: `${title} hierher ziehen oder ` }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: hint }),
    info,
  ]);

  const api = async (path, body, type = "application/octet-stream") => {
    if (!link) throw new Error("Nicht verbunden. Starte npm run emu und öffne den Link, den es ausgibt.");
    let res;
    try {
      res = await fetch(`http://127.0.0.1:${link.port}${path}`, {
        method: "POST", body, headers: { "Content-Type": type, "X-Emu-Token": link.token },
      });
    } catch {
      throw new Error(`Der Emulator auf Port ${link.port} antwortet nicht. Läuft npm run emu?`);
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Emulator antwortet mit ${res.status}.`);
    return data;
  };

  function showStatus(s) {
    const [tone, word] = STATE_WORDS[s.state] || ["muted", s.state];
    const live = state => state === "running" || state === "hung";
    const stopped = live(lastState) && !live(s.state);
    if (typeof s.device_ms === "number") {
      if (s.device_ms < lastDeviceMs) generation++;
      lastDeviceMs = s.device_ms;
    }
    if (s.state === "running" && lastState !== "running") generation++;
    lastState = s.state;
    booted = s.state === "running" && s.booted !== false;
    if (stopped) port.ondisconnect?.();
    say(tone, word, s.error || (s.state === "running" ? "Die Firmware läuft." : s.state === "off" ? "Die Electribe ist aus." : ""), QUIET.has(s.state) && !s.error);
    if (s.state !== "running") device.showLeds({}, true);
    if (!fake) device.setPower(live(s.state));
    deviceBox.dataset.state = s.state;
  }

  function listen() {
    events?.close();
    if (!link) {
      say("muted", "nicht verbunden", "Starte npm run emu im Projektordner und öffne den Link, den es ausgibt.");
      return;
    }
    events = new EventSource(`http://127.0.0.1:${link.port}/events?token=${encodeURIComponent(link.token)}`);
    events.addEventListener("status", e => showStatus(JSON.parse(e.data)));
    // The service sends the on/off display and, besides it, the levels the LCD shows while it
    // follows a switched pixel; once levels come, they are what is drawn.
    let shaded = false;
    events.addEventListener("display", e => {
      if (shaded || external) return;
      const b64 = JSON.parse(e.data);
      drawDisplay(canvas, Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
    });
    events.addEventListener("shade", e => {
      shaded = true;
      lastShade = Uint8Array.from(atob(JSON.parse(e.data)), c => c.charCodeAt(0));
      if (!external) drawShade(canvas, lastShade);
    });
    events.addEventListener("leds", e => { if (!external && (lastState === "running" || lastState === "hung")) device.showLeds(JSON.parse(e.data), true); });
    events.addEventListener("midi", e => {
      const hex = JSON.parse(e.data);
      port.in.onmidimessage?.({ data: Uint8Array.from(hex.match(/../g), h => parseInt(h, 16)) });
    });
    events.addEventListener("error", () => {
      if (events.readyState === EventSource.CLOSED || events.readyState === EventSource.CONNECTING) {
        say("warn", "getrennt", `Keine Verbindung zum Emulator auf Port ${link.port}. Läuft npm run emu, und ist der Link aktuell?`);
      }
    });
  }

  vsbInput.addEventListener("change", async () => {
    const file = vsbInput.files?.[0];
    if (!file) return;
    const bytes = new Uint8Array(await file.arrayBuffer());
    vsb = null;
    base = null;
    setBuild(null);
    keep.delete("vsb");
    if (bytes.length !== VSB_SIZE) {
      vsbInfo.textContent = `${file.name}: ${bytes.length} Byte, eine VSB hat ${VSB_SIZE}.`;
      showStatus({ state: "empty" });
      return;
    }
    const id = await identify(bytes);
    vsbInfo.textContent = describe(file.name, id, false);
    vsb = bytes;
    setBuild(bytes);
    keep.put("vsb", { name: file.name, bytes });
    if (lastState !== "running" && lastState !== "hung") showStatus({ state: "loaded" });
  });

  let booting = false;
  let fake = null;
  /** No firmware loaded: the device lights its display for a few seconds, says so and goes off again. */
  function startFake() {
    drawDisplay(canvas, textScreen(["NO", "FIRMWARE"]));
    device.setPower(true);
    fake = setTimeout(endFake, FAKE_BOOT_MS);
  }
  function endFake() {
    clearTimeout(fake);
    fake = null;
    device.setPower(false);
  }
  /** The power key of a switched-off device: the firmware goes to the service, then it starts. */
  async function boot() {
    if (booting) return;
    if (!vsb) { startFake(); return; }
    booting = true;
    try {
      if (pushed !== vsb) { await api("/firmware", vsb); pushed = vsb; }   // sent again, a restart after SOFTWARE UPDATE would start the old file
      showStatus(await api("/start", "{}", "application/json"));
      firmware.details.open = false;
    } catch (e) {
      say("error", "Fehler", e.message);
    } finally {
      booting = false;
    }
  }

  // Under the device front: what it shows right now, read from its RAM.
  const aside = el("section", { className: "ui-section cee-emu-live", id: "cee-emu-side" });
  // The firmware is an option of the page: a sub-item of its sidebar entry.
  const firmware = sub.add("emu", { id: "cee-emu-setup", title: "Firmware (VSB)" });
  firmware.body.append(drop(vsbInput, "SYSTEM.VSB", "Deine eigene Firmware-Datei.", vsbInfo));
  root.replaceChildren(
    el("div", { className: "cee-emu-bar" }, [status]),
    deviceBox,
    aside,
  );
  deviceBox.append(device.build(el("div", { className: "cee-lcd-frame" }, [canvas])));
  showStatus({ state: "empty" });
  listen();
  // After a reload: the VSB chosen before comes back from this browser. The service reports by itself
  // whether it still runs; the status event re-attaches the display, so nothing boots here.
  keep.get("vsb").then(async saved => {
    if (!saved?.bytes || vsb) return;
    vsb = saved.bytes;
    setBuild(vsb);
    vsbInfo.textContent = describe(saved.name, await identify(vsb), true);
    if (lastState === "empty") showStatus({ state: "loaded" });
  });
  return {
    port, aside,
    get link() { return link; },
    get firmware() { return vsb; },
    /** "hacktribe" or "stock" for the loaded VSB, null while there is none. */
    get build() { return build; },
    /** Why a function of Hacktribe's cannot be used with the loaded firmware, or null when it can (or none is loaded). */
    lack(what = "sysex") { return build ? lackOf(build, what, { blech }) : null; },
    /** The VSB the user loaded; an export booted with bootWith() does not replace it. */
    get baseFirmware() { return base ?? vsb; },
    /** Export check of the original and its patched copy (tools/emu/check.py), minutes. `onProgress(snapshot)` hears the service's progress about once a second while it runs (GET /check/progress). */
    check(original, patched, allow = [], allowCode = [], onProgress = null, { quick = false } = {}) {
      const body = new Uint8Array(original.length + patched.length);
      body.set(original);
      body.set(patched, original.length);
      const spans = list => list.map(([at, n]) => `0x${at.toString(16)}:${n}`).join(",");
      const query = [["allow", spans(allow)], ["allowCode", spans(allowCode)], ["quick", quick ? "1" : ""]].filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("&");
      const run = api(`/check${query ? `?${query}` : ""}`, body);
      if (!onProgress || !link) return run;
      let over = false;
      (async () => {
        while (!over) {
          await new Promise(r => setTimeout(r, 1000));
          if (over) break;
          try {
            const res = await fetch(`http://127.0.0.1:${link.port}/check/progress?token=${encodeURIComponent(link.token)}`);
            if (res.ok && !over) onProgress(await res.json());
          } catch { /* the next poll tries again; the check request itself reports a lost service */ }
        }
      })();
      return run.finally(() => { over = true; });
    },
    /**
     * Run `running` (the user's own file, as it is) with `update` on the virtual card as SYSTEM.VSB, the way a person
     * tries SOFTWARE UPDATE. Returns the folder below KORG/ the file went to, the one the running firmware reads.
     */
    async rehearseUpdate(running, update) {
      showStatus(await api("/stop", "{}", "application/json"));     // the page sends no MIDI to a firmware that is about to restart
      await api("/firmware", running);
      pushed = running;
      const sd = await api("/sd/system", update);
      vsb = running;
      base = null;
      setBuild(running);
      keep.put("vsb", { name: "SYSTEM.VSB", bytes: running });
      vsbInfo.textContent = "SYSTEM.VSB für den Update-Test geladen.";
      showStatus(await api("/start", "{}", "application/json"));
      firmware.details.open = false;
      return sd.korg;
    },
    /** Boot the emulator with other firmware bytes, such as an export. */
    async bootWith(bytes) {
      await api("/firmware", bytes);
      pushed = bytes;
      base = base ?? vsb;
      vsb = bytes;
      setBuild(bytes);
      vsbInfo.textContent = "Exportierte Kopie geladen.";
      showStatus(await api("/start", "{}", "application/json"));
    },
    /**
     * Press a front button the way a finger does: held 100 ms, then 400 ms
     * for the firmware to act. Down and up in one go reach the firmware
     * within a few milliseconds, and the second of two such presses is lost.
     */
    async button(index) {
      const wait = ms => new Promise(r => setTimeout(r, ms));
      send({ kind: "button", index, down: true });
      await wait(100);
      send({ kind: "button", index, down: false });
      await wait(400);
    },
    connect(next) { link = next; listen(); },
    /** Let the drawing show a real device (its display bytes through drawBytes) or give it back to the emulator. */
    external(on) {
      const was = external;
      external = on;
      if (on || was) device.showLeds({}, true);
      if (!on && lastShade) drawShade(canvas, lastShade);
    },
    drawBytes: bytes => drawDisplay(canvas, bytes),
    /** The lit LEDs of a real device, number to brightness; the ones not listed go dark. */
    drawLeds: leds => { if (external) device.showLeds(leds, true); },
  };
}
