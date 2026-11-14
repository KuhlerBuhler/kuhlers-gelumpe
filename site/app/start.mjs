/**
 * The start page follows the situation: a first visit sees the welcome (what BLECHTRIBE is, how to install it), whoever
 * has BLECHTRIBE sees the hub (device and emulator state, next steps). The decision is a pure function; the page
 * listens to the device session and the emulator and switches at most once while they load.
 */
import { t, language } from "./i18n.mjs";
import { setStateText } from "./state.mjs";
import { e2Outline } from "./e2-art.mjs";
import { firmwareName, hardwareOf } from "../../src/firmware.mjs";
import { RELEASE_NOTES } from "../../data/release-notes.mjs";

/** Where the patch blech-version keeps "BLECH x.y.z", NUL padded to 16 bytes (tools/patch/blech_version.mjs). */
export const VERSION_AT = 0xC014FCF0;
export const VERSION_LENGTH = 16;

/** The BLECHTRIBE version this app patches: the newest release notes. */
export const APP_VERSION = RELEASE_NOTES[0]?.version ?? null;

/** The merker: "1" once BLECHTRIBE was patched, installed, connected or loaded into the emulator in this browser. */
export const DONE_KEY = "cee.start.done";

/**
 * Which view the start page shows.
 * `device`: the connected Electribe's `session.device`, or null. `emulator`: the emulator has a firmware loaded.
 * `seen`: the merker says BLECHTRIBE was here before.
 * An Electribe without BLECHTRIBE keeps the welcome, with a line that it was found.
 */
export function startView({ device = null, emulator = false, seen = false } = {}) {
  const blech = !!device?.blech;
  return {
    view: blech || emulator || seen ? "hub" : "welcome",
    found: !!device && !blech,
    blech,
  };
}

/** "1.4.6" from the 16 bytes at VERSION_AT, or null when they hold no version (an older set, or FF). */
export function parseBlechVersion(bytes) {
  if (!bytes?.length) return null;
  let text = "";
  for (const b of bytes) {
    if (b === 0) break;
    if (b < 0x20 || b > 0x7e) return null;
    text += String.fromCharCode(b);
  }
  return /^BLECH (\d+\.\d+\.\d+)$/.exec(text)?.[1] ?? null;
}

/** -1, 0 or 1 for two versions "x.y.z". */
export function compareVersions(a, b) {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d) return Math.sign(d);
  }
  return 0;
}

/** The device against the version this app patches: "update", "current", "newer", or "unknown" without a version. */
export function updateState(deviceVersion, appVersion) {
  if (!deviceVersion || !appVersion) return "unknown";
  const c = compareVersions(deviceVersion, appVersion);
  return c < 0 ? "update" : c > 0 ? "newer" : "current";
}

/**
 * Whether this browser saw BLECHTRIBE before, from the merker. Users of 1.4.x have none: once, signs of earlier use
 * (a page they opened, the changelogs they read, plugins they kept) count, and the answer is stored.
 */
export function seenBefore(storage) {
  try {
    const kept = storage?.getItem(DONE_KEY);
    if (kept === "1" || kept === "0") return kept === "1";
    const area = storage?.getItem("cee.area");
    const used = !!storage?.getItem("cee.changelog.seen") || !!storage?.getItem("cee.scripts.v1") || (!!area && area !== "start");
    storage?.setItem(DONE_KEY, used ? "1" : "0");
    return used;
  } catch {
    return false;
  }
}

/** Stores the merker; blocked storage keeps it for this page only. */
export function markDone(storage) {
  try { storage?.setItem(DONE_KEY, "1"); } catch { /* blocked: the page still knows */ }
}

/** How long the start page waits for one read before it says "unknown"; the read itself goes on. */
export const READ_WAIT = 8000;

const within = (promise, ms) => Promise.race([promise, new Promise(done => setTimeout(done, ms, null))]);

/**
 * What a session tells about the Electribe, read once per session: the BLECHTRIBE version (a RAM read) first, then red or
 * blue (a flash read, slow on some sets). Each a promise of its own, so one does not wait for the other to be shown.
 * Only reads; a failed or slow read gives null, never an error.
 */
const reads = new WeakMap();
export function deviceReads(session, wait = READ_WAIT) {
  if (!session?.device) return { hardware: Promise.resolve(null), version: Promise.resolve(null) };
  let known = reads.get(session);
  if (!known) {
    const version = session.device.ram === "blech"
      ? within(Promise.resolve().then(() => session.readRamBlock(VERSION_AT, VERSION_LENGTH)).then(parseBlechVersion, () => null), wait)
      : Promise.resolve(null);
    const hardware = within(Promise.resolve().then(() => session.hardware?.()).catch(() => null).then(h => h ?? null), wait);
    known = { hardware, version };
    reads.set(session, known);
  }
  return known;
}

/** Both reads of deviceReads() together. */
export async function deviceFacts(session, wait) {
  const { hardware, version } = deviceReads(session, wait);
  return { hardware: await hardware, version: await version };
}

/** Korg's version as the Electribe shows it: [2, 2] is 2.02. */
export const korgVersion = version => `${version[0]}.${String(version[1]).padStart(2, "0")}`;

/** The welcome's line for an Electribe without BLECHTRIBE: found, with red or blue and Korg's version once read. */
function paintFound(line, state, session) {
  line.hidden = !state.found;
  if (!state.found) return;
  line.classList.add("cee-state");
  const say = hardware => setStateText(line, "info", hardware
    ? t("start.found.detail", { hardware: t(hardware === "blue" ? "start.hw.blue" : "start.hw.red"), version: korgVersion(session.device.version) })
    : t("start.found"));
  say(null);
  deviceReads(session).hardware.then(hardware => { if (!line.hidden && hardware) say(hardware); });
}

/** The first points of a release's notes as plain text, in the page's language, else English, else German. */
export function newsOf(note, lang = language(), count = 3) {
  const md = note?.[lang] ?? note?.en ?? note?.de ?? "";
  return md.split("\n").filter(line => line.startsWith("- ")).slice(0, count)
    .map(line => line.slice(2).replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*|`/g, "").trim());
}

/** The tone and word of the device's BLECHTRIBE against this app (updateState). */
const VERSION_SAYS = {
  update: ["warn", () => t("start.hub.update", { version: APP_VERSION })],
  current: ["ok", () => t("start.hub.current")],
  newer: ["info", () => t("start.hub.newer")],
  unknown: ["info", () => t("start.hub.unknown")],
};

const stateLine = (node, tone, word) => {
  node.classList.add("cee-state");
  node.hidden = false;
  setStateText(node, tone, word);
};

/** The Electribe drawn in lines at the front of a card, in the colour of `data-device`. */
function outline(card, label) {
  const art = e2Outline(label);
  const old = card.querySelector(".cee-e2-outline");
  if (old) old.replaceWith(art); else card.prepend(art);
}

/** The hub's update card, first of the next steps: an update when one is due, BLECHTRIBE when the device has none. */
function paintUpdate(hub, kind) {
  const item = hub.querySelector("#cee-start-next-update");
  if (!item) return;
  item.hidden = !kind;
  if (!kind) return;
  item.querySelector("#cee-start-update-title").textContent = kind === "update" ? t("start.card.update", { version: APP_VERSION }) : t("start.card.install");
  item.querySelector("#cee-start-update-hint").textContent = kind === "update" ? t("start.card.update.hint") : t("start.card.install.hint");
}

/** The hub's device card: connected or how to connect, red or blue, Korg's and BLECHTRIBE's version against this app. */
function paintDevice(hub, session, current) {
  const card = hub.querySelector("#cee-start-device");
  if (!card) return;
  const [name, state, facts, version] = ["name", "state", "facts", "version"].map(id => card.querySelector(`#cee-start-device-${id}`));
  const look = hardware => {
    card.dataset.device = hardware ?? "grey";
    name.textContent = hardware ? t("start.hub.device.hw", { hardware: t(hardware === "blue" ? "start.hw.blue" : "start.hw.red") }) : t("start.hub.device");
    outline(card, name.textContent);
  };
  look(null);
  if (!session) {
    stateLine(state, "neutral", t("start.hub.none"));
    facts.hidden = false;
    facts.textContent = t("start.hub.connect");
    version.hidden = true;
    paintUpdate(hub, null);
    return;
  }
  const korg = t("start.hub.korg", { version: korgVersion(session.device.version) });
  stateLine(state, "ok", t("start.hub.connected"));
  facts.hidden = false;
  facts.textContent = korg;
  version.hidden = true;
  const blech = !!session.device.blech;
  paintUpdate(hub, blech ? null : "install");
  stateLine(version, blech ? "running" : "info", t(blech ? "start.hub.reading" : "start.hub.noBlech"));
  const reads = deviceReads(session);
  reads.hardware.then(hardware => { if (current() === session) look(hardware); });
  if (!blech) return;
  reads.version.then(found => {
    if (current() !== session) return;
    if (found) facts.textContent = `${korg}, ${t("start.hub.blech", { version: found })}`;
    const due = updateState(found, APP_VERSION);
    const [tone, say] = VERSION_SAYS[due];
    stateLine(version, tone, say());
    paintUpdate(hub, due === "update" ? "update" : null);
  });
}

/** The hub's emulator card: whether a firmware is loaded, which one, and the way there. */
function paintEmulator(hub, firmware) {
  const card = hub.querySelector("#cee-start-emu-card");
  if (!card) return;
  const [state, name, go] = ["state", "name", "go"].map(id => card.querySelector(`#cee-start-emu-${id}`));
  let label = null;
  try { label = firmware ? firmwareName(firmware) : null; } catch { label = null; }
  card.dataset.device = firmware ? hardwareOf(firmware) : "grey";
  outline(card, t("start.hub.emu"));
  stateLine(state, firmware ? "ok" : "neutral", t(firmware ? "start.hub.emu.loaded" : "start.hub.emu.none"));
  name.hidden = !label;
  name.textContent = label ?? "";
  go.textContent = t(firmware ? "start.hub.emu.open" : "start.hub.emu.load");
}

/** The hub's "new in this version" from the newest release notes; without points the block stays away. */
function paintNews(hub) {
  const box = hub?.querySelector("#cee-start-news");
  if (!box) return;
  const points = newsOf(RELEASE_NOTES[0]);
  box.hidden = !points.length;
  box.querySelector("#cee-start-news-version").textContent = t("start.news.version", { version: APP_VERSION });
  box.querySelector("#cee-start-news-list").replaceChildren(...points.map(text => Object.assign(document.createElement("li"), { textContent: text })));
}

/**
 * The start page. `session()` gives the Electribe on the cable (never the emulator's port), `emulator()` the emulator
 * panel. Call `sessionChanged()` when the session changes, `firmwareChanged()` when the emulator's firmware may have,
 * and `opened()` when the page comes into view.
 * The view starts from the merker, so a returning visitor does not see the welcome flash by while things load.
 */
export function startPage(root, { storage = null, session = () => null, emulator = () => null, paint = () => {} } = {}) {
  let seen = seenBefore(storage);
  let shown = null;
  const views = { welcome: root.querySelector("#cee-start-welcome"), hub: root.querySelector("#cee-start-hub") };
  const found = root.querySelector("#cee-start-found");
  // The install steps belong to the welcome; in the hub they fold into "Install guide".
  const entry = root.querySelector("#cee-start-entry");
  const entryNext = entry?.nextElementSibling ?? null;
  const guide = root.querySelector("#cee-start-guide");
  paintNews(views.hub);
  let painted = null;
  let current = null;
  const render = () => {
    const s = session();
    const device = s && !s.sender?.disconnected ? s.device : null;
    const firmware = !!emulator()?.firmware;
    if ((device?.blech || firmware) && !seen) { seen = true; markDone(storage); }
    const state = startView({ device, emulator: firmware, seen });
    if (state.view !== shown) {
      shown = state.view;
      root.dataset.view = shown;
      for (const [id, node] of Object.entries(views)) if (node) node.hidden = id !== shown;
      if (entry && guide) {
        if (shown === "hub") guide.append(entry);
        else entryNext?.parentNode ? entryNext.before(entry) : views.welcome?.append(entry);
      }
    }
    // The device is read (RAM and flash) only while the page is in view, not on every plug-in on another page.
    const visible = !root.closest("[hidden]");
    if (found && visible) paintFound(found, state, s);
    current = device ? s : null;
    const fw = emulator()?.firmware ?? null;
    if (views.hub && visible && shown === "hub" && (painted?.session !== current || painted?.fw !== fw)) {
      painted = { session: current, fw };
      paintDevice(views.hub, current, () => current);
      paintEmulator(views.hub, fw);
    }
    paint(state, { session: device ? s : null, emulator: emulator() });
    return state;
  };
  render();
  return {
    sessionChanged: render,
    firmwareChanged: render,
    /** The start page came into view. */
    opened: render,
    /** The patcher saved a file or sent it to the Electribe. */
    done() { seen = true; markDone(storage); render(); },
    get view() { return shown; },
  };
}
