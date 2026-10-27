/**
 * The emulator area: the own firmware runs in the local emulator service
 * (`npm run emu`), and its display shows here live. Files go only to that
 * service on this computer.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { identify, buildOf, lackOf, hasBlechSysex, firmwareName } from "../../src/firmware.mjs";
import { devicePanel } from "./panel.mjs";
import { t } from "./i18n.mjs";

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
  empty: ["muted", "emu.state.empty"],
  loaded: ["muted", "emu.state.loaded"],
  running: ["ok", "emu.state.running"],
  stopped: ["muted", "emu.state.stopped"],
  crashed: ["error", "emu.state.crashed"],
  hung: ["warn", "emu.state.hung"],
  off: ["muted", "emu.state.off"],
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
    const res = await fetch("./emu.json", { cache: "no-store" });
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
  probe.fillStyle = value.trim() || "#000"; // raw-ok: an unset LCD colour falls back to an unlit pixel
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

export function emulatorPanel(root, link = null, { deviceArea = null, onConnect = () => {}, onBlocked = () => {} } = {}) {
  let events = null;
  let vsb = null;
  let base = null;
  let pushed = null;          // the VSB the service holds. It boots from its own flash after an update, so what it runs may not be `vsb`
  let resume = false;         // the service went away while the firmware ran: once it answers again, the page boots it again

  const deviceBox = el("div", { className: "cee-emu-device", id: "cee-emu-device" });
  const status = el("p", { className: "cee-emu-status ui-sr-only", id: "cee-emu-status", role: "status" });
  const canvas = el("canvas", { className: "cee-lcd", id: "cee-emu-lcd", width: 128, height: 64 });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", t("emu.display"));
  // What the device shows, as text: only a screen reader hears it (follow.mjs fills it in).
  const where = el("p", { className: "ui-sr-only", id: "cee-emu-where" });
  canvas.setAttribute("aria-describedby", "cee-emu-where");

  // Inputs go out one after another, so a release never overtakes its press.
  // Knob and touch moves only send their latest value.
  let queue = Promise.resolve();
  const latest = new Map();
  let external = false;       // the drawing shows a real device; the emulator neither draws nor takes input
  let mirrored = true;        // the real device's display is drawn (it has RAM access); without, the drawing stays blank
  let lastShade = null;
  const send = (cmd, coalesce) => {
    if (external) {
      if (cmd.kind === "power" && cmd.down) onBlocked();
      return;
    }
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
    }).then(s => { if (s?.state && s.state !== lastState) showStatus(s); }, e => say("error", t("common.error"), e.message));
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
        midiQueue = midiQueue.then(() => api("/midi", body)).catch(e => say("error", t("common.error"), e.message));
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
  const say = (tone, word, text, quiet = false, extra = null, keep = false) => {
    const key = [tone, word, text, quiet, !!extra].join("\0");
    if (key === said) return;
    said = key;
    // The line is for screen readers only; what goes wrong is said in the toast, nothing stands above the device.
    status.replaceChildren(pill(tone, word), el("span", { textContent: ` ${text}` }), ...(extra ? [" ", extra] : []));
    // A state the emulator reports by itself goes away again; it must not lie on the page's buttons. Why the firmware
    // crashed or hangs (`keep`) stays until it is closed: the person needs it to decide on a restart.
    if (!quiet && (tone === "error" || tone === "warn")) toast(text, keep ? "error" : "info");
  };
  // In the desktop app the app starts the emulator itself (src-tauri); the page started by `npm start` finds it through
  // /emu.json. Nobody is asked to run a command: the start button looks for it, and what fails is said in a toast.
  const inApp = !!window.__GELUMPE_APP;
  const START_HINT = inApp
    ? t("emu.start.app")
    : t("emu.start.page");
  const startButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-emu-start", textContent: t("emu.start"), hidden: true });
  /** Looks for the emulator service; false and a toast when there is none. */
  async function start() {
    startButton.disabled = true;
    try {
      const found = await findLink({ link: null, fresh: false });
      if (!found.link) throw new Error(START_HINT);
      link = found.link;
      listen();
      onConnect(link);
      return true;
    } catch (e) {
      toast(e.message, "error");
      return false;
    } finally {
      startButton.disabled = false;
    }
  }
  startButton.addEventListener("click", () => start());

  const vsbInput = el("input", { type: "file", className: "ui-sr-only", id: "cee-emu-vsb", accept: ".VSB,.vsb", tabIndex: -1 });
  vsbInput.setAttribute("aria-hidden", "true");
  const vsbInfo = el("span", { className: "ui-dropzone-files ui-sr-only", id: "cee-emu-vsb-info" });

  // Which build the loaded VSB is (src/firmware.mjs); the places that need Hacktribe's functions ask `lack()`.
  let build = null;
  let blech = false;
  function setBuild(bytes) {
    build = bytes ? buildOf(bytes) : null;
    blech = !!bytes && hasBlechSysex(bytes);
  }
  /** The line for the file chooser; Korg's own build is a recognised file, it only is not the measured one. */
  /** A recognised file is said by the display; the line is for screen readers, what went wrong goes to the toast. */
  const showInfo = (text, wrong = false) => {
    vsbInfo.textContent = text;
    if (wrong) toast(text, "error");
  };
  const describe = (name, id, saved) => {
    const when = saved ? t("emu.file.saved") : "";
    if (id.build === "synth") return t("emu.file.synth", { name, when });
    if (id.build === "stock") return t("emu.file.stock", { name, when });
    if (id.known) return t("emu.file.known", { name, when });
    return saved ? t("emu.file.unknown", { name, when }) : t("emu.file.unknown.why", { name, reasons: id.reasons.join(" ") });
  };
  /** A file the emulator is not built for: said in the toast as well. */
  const unknown = id => id.build !== "synth" && id.build !== "stock" && !id.known;

  // A switched-off Electribe takes its firmware on the display: drop the file there or tap it.
  const offerTitle = el("strong", { textContent: "SYSTEM.VSB" });
  const offerText = el("span");
  const offer = el("button", { type: "button", className: "cee-emu-offer", id: "cee-emu-offer" }, [offerTitle, " ", offerText]);
  offer.addEventListener("click", () => (external ? onBlocked() : vsbInput.click()));
  function renderOffer() {
    const off = lastState !== "running" && lastState !== "hung" && !fake && !external;
    const held = external && !mirrored;
    offer.hidden = !off && !held;
    if (held) {
      offerTitle.textContent = t("emu.offer.connected");
      offerText.textContent = t("emu.offer.noDisplay");
      offer.title = t("emu.offer.disconnect");
      return;
    }
    offerTitle.textContent = vsb ? t("emu.offer.loaded") : "SYSTEM.VSB";
    offerText.textContent = vsb ? firmwareName(vsb) : t("emu.offer.drop");
    // Its name is what the display says; what a tap does is the title.
    offer.title = vsb ? t("emu.offer.other") : t("emu.offer.pick");
  }

  const api = async (path, body, type = "application/octet-stream") => {
    if (!link) throw new Error(START_HINT);
    let res;
    try {
      res = await fetch(`http://127.0.0.1:${link.port}${path}`, {
        method: "POST", body, headers: { "Content-Type": type, "X-Emu-Token": link.token },
      });
    } catch {
      throw new Error(inApp ? t("emu.api.app") : t("emu.api.page", { port: link.port }));
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || t("emu.api.status", { status: res.status }));
    return data;
  };

  function showStatus(s) {
    const [tone, key] = STATE_WORDS[s.state] || ["muted", null];
    const word = key ? t(key) : s.state;
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
    if (resume) {
      resume = false;
      // A service started again holds no firmware and runs none: the power key the person pressed before counts again.
      if (!live(s.state) && vsb) queueMicrotask(boot);
    }
    say(tone, word, s.error || (s.state === "running" ? t("emu.running") : s.state === "off" ? t("emu.off") : ""), QUIET.has(s.state) && !s.error, null, !!s.error);
    if (s.state !== "running") device.showLeds({}, true);
    if (!fake) device.setPower(live(s.state));
    deviceBox.dataset.state = s.state;
    renderOffer();
  }

  function listen() {
    events?.close();
    startButton.hidden = !!link;
    if (!link) {
      say("muted", t("emu.state.off"), t("emu.notStarted"), true);
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
        // The app starts its service again on the same port (src-tauri), `npm start` too: whatever answers next
        // holds no firmware, and what ran is booted again once it is back.
        pushed = null;
        if (lastState === "running" || lastState === "hung") {
          showStatus({ state: "stopped" });
          resume = true;
        }
        const text = inApp ? t("emu.lost.app") : t("emu.lost.page");
        say("warn", t("emu.state.lost"), text);
        // A browser that gives up instead of trying again is asked again.
        if (events.readyState === EventSource.CLOSED) setTimeout(() => { if (events?.readyState === EventSource.CLOSED) listen(); }, 2000);
      }
    });
  }

  vsbInput.addEventListener("change", async () => {
    const file = vsbInput.files?.[0];
    if (!file) return;
    vsbInput.value = "";
    const bytes = new Uint8Array(await file.arrayBuffer());
    vsb = null;
    base = null;
    setBuild(null);
    keep.delete("vsb");
    if (bytes.length !== VSB_SIZE) {
      showInfo(t("emu.size.info", { file: file.name, size: bytes.length, expected: VSB_SIZE }), true);
      toast(t("emu.size.toast", { file: file.name, size: bytes.length, expected: VSB_SIZE }), "error");
      showStatus({ state: "empty" });
      return;
    }
    const id = await identify(bytes);
    showInfo(describe(file.name, id, false), unknown(id));
    vsb = bytes;
    setBuild(bytes);
    keep.put("vsb", { name: file.name, bytes });
    if (lastState !== "running" && lastState !== "hung") showStatus({ state: "loaded" });
    renderOffer();
  });

  let booting = false;
  let fake = null;
  /** No firmware loaded: the device lights its display for a few seconds, says so and goes off again. */
  function startFake() {
    drawDisplay(canvas, textScreen(["NO", "FIRMWARE"]));
    device.setPower(true);
    fake = setTimeout(endFake, FAKE_BOOT_MS);
    renderOffer();
  }
  function endFake() {
    clearTimeout(fake);
    fake = null;
    device.setPower(false);
    renderOffer();
  }
  /** The power key of a switched-off device: the firmware goes to the service, then it starts. */
  async function boot() {
    if (booting) return;
    if (!vsb) { startFake(); return; }
    booting = true;
    try {
      if (!link && !await start()) return;
      if (pushed !== vsb) { await api("/firmware", vsb); pushed = vsb; }   // sent again, a restart after SOFTWARE UPDATE would start the old file
      showStatus(await api("/start", "{}", "application/json"));
    } catch (e) {
      say("error", t("common.error"), e.message);
      toast(e.message, "error");
    } finally {
      booting = false;
    }
  }

  const bar = el("div", { className: "cee-emu-bar" }, [status, startButton, el("div", { className: "cee-emu-file" }, [vsbInput, vsbInfo])]);
  root.replaceChildren(bar, deviceBox, where);
  const frame = el("div", { className: "cee-lcd-frame" }, [canvas, offer]);
  frame.addEventListener("dragover", e => { if (!offer.hidden) { e.preventDefault(); frame.dataset.drag = ""; } });
  frame.addEventListener("dragleave", () => delete frame.dataset.drag);
  frame.addEventListener("drop", e => {
    delete frame.dataset.drag;
    if (offer.hidden || !e.dataTransfer?.files?.length) return;
    e.preventDefault();
    vsbInput.files = e.dataTransfer.files;
    vsbInput.dispatchEvent(new Event("change"));
  });
  deviceBox.append(device.build(frame));
  showStatus({ state: "empty" });
  listen();
  // After a reload: the VSB chosen before comes back from this browser. The service reports by itself
  // whether it still runs; the status event re-attaches the display, so nothing boots here.
  keep.get("vsb").then(async saved => {
    if (!saved?.bytes || vsb) return;
    vsb = saved.bytes;
    setBuild(vsb);
    const id = await identify(vsb);
    showInfo(describe(saved.name, id, true), unknown(id));
    if (lastState === "empty") showStatus({ state: "loaded" });
    renderOffer();
  });
  return {
    port, where, bar,
    /** The device front, display and controls. */
    front: deviceBox,
    get link() { return link; },
    get firmware() { return vsb; },
    /** "hacktribe" or "stock" for the loaded VSB, null while there is none. */
    get build() { return build; },
    /** Why a function of Hacktribe's cannot be used with the loaded firmware, or null when it can (or none is loaded). */
    lack(what = "sysex") { return build ? lackOf(build, what, { blech }) : null; },
    /** The VSB the user loaded; an export booted with bootWith() does not replace it. */
    get baseFirmware() { return base ?? vsb; },
    /** Export check of the original and its patched copy (tools/emu/check.py), minutes. `hardware` "blue" for Sampler code on the blue (Hacktribe for the blue). `onProgress(snapshot)` hears the service's progress about once a second while it runs (GET /check/progress). */
    check(original, patched, allow = [], allowCode = [], onProgress = null, { quick = false, hardware = null } = {}) {
      const body = new Uint8Array(original.length + patched.length);
      body.set(original);
      body.set(patched, original.length);
      const spans = list => list.map(([at, n]) => `0x${at.toString(16)}:${n}`).join(",");
      const query = [["allow", spans(allow)], ["allowCode", spans(allowCode)], ["quick", quick ? "1" : ""], ["hardware", hardware ?? ""]].filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("&");
      const run = api(`/check${query ? `?${query}` : ""}`, body);
      if (!onProgress || !link) return run;
      let over = false;
      (async () => {
        while (!over) {
          await new Promise(r => setTimeout(r, 1000));
          if (over) break;
          try {
            const res = await fetch(`http://127.0.0.1:${link.port}/check/progress?token=${encodeURIComponent(link.token)}`);
            if (res.ok) {
              const snapshot = await res.json();
              if (!over) onProgress(snapshot);
            }
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
      showInfo(t("emu.rehearse"));
      showStatus(await api("/start", "{}", "application/json"));
      return sd.korg;
    },
    /** Boot the emulator with other firmware bytes, such as an export. */
    async bootWith(bytes) {
      await api("/firmware", bytes);
      pushed = bytes;
      base = base ?? vsb;
      vsb = bytes;
      setBuild(bytes);
      showInfo(t("emu.export"));
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
    /** Switch the Electribe on, as the power key does; says in words what happened (the console's start). */
    async powerOn() {
      if (lastState === "running" || lastState === "hung") return t("emu.power.already");
      if (!vsb) throw new Error(t("emu.power.noFirmware"));
      await boot();
      if (lastState !== "running") throw new Error(t("emu.power.failed"));
      return t("emu.power.on");
    },
    /** Let the drawing show a real device (its display bytes through drawBytes) or give it back to the emulator. */
    external(on, mirrors = true) {
      const was = external;
      external = on;
      mirrored = mirrors;
      renderOffer();
      if (on || was) device.showLeds({}, true);
      if (!on && lastShade) drawShade(canvas, lastShade);
    },
    drawBytes: bytes => drawDisplay(canvas, bytes),
    /** The lit LEDs of a real device, number to brightness; the ones not listed go dark. */
    drawLeds: leds => { if (external) device.showLeds(leds, true); },
  };
}
