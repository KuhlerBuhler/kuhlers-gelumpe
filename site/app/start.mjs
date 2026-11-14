/**
 * The start page follows the situation: a first visit sees the welcome (what BLECHTRIBE is, how to install it), whoever
 * has BLECHTRIBE sees the hub (device and emulator state, next steps). The decision is a pure function; the page
 * listens to the device session and the emulator and switches at most once while they load.
 */
import { t } from "./i18n.mjs";
import { setStateText } from "./state.mjs";

/** Where the patch blech-version keeps "BLECH x.y.z", NUL padded to 16 bytes (tools/patch/blech_version.mjs). */
export const VERSION_AT = 0xC014FCF0;
export const VERSION_LENGTH = 16;

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

/**
 * What a session tells about the Electribe, read once per session: red or blue (a flash read) and the BLECHTRIBE
 * version (a RAM read). Only reads; a failed or slow read gives null, never an error.
 */
const facts = new WeakMap();
export function deviceFacts(session) {
  if (!session?.device) return Promise.resolve({ hardware: null, version: null });
  let known = facts.get(session);
  if (!known) {
    const hardware = Promise.resolve().then(() => session.hardware?.()).catch(() => null).then(h => h ?? null);
    const version = session.device.ram === "blech"
      ? Promise.resolve().then(() => session.readRamBlock(VERSION_AT, VERSION_LENGTH)).then(parseBlechVersion, () => null)
      : Promise.resolve(null);
    known = Promise.all([hardware, version]).then(([h, v]) => ({ hardware: h, version: v }));
    facts.set(session, known);
  }
  return known;
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
  deviceFacts(session).then(f => { if (!line.hidden && f.hardware) say(f.hardware); });
}

/**
 * The start page. `session()` gives the Electribe on the cable (never the emulator's port), `emulator()` the emulator
 * panel. Call `sessionChanged()` when the session changes and `firmwareChanged()` when the emulator's firmware may have.
 * The view starts from the merker, so a returning visitor does not see the welcome flash by while things load.
 */
export function startPage(root, { storage = null, session = () => null, emulator = () => null, paint = () => {} } = {}) {
  let seen = seenBefore(storage);
  let shown = null;
  const views = { welcome: root.querySelector("#cee-start-welcome"), hub: root.querySelector("#cee-start-hub") };
  const found = root.querySelector("#cee-start-found");
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
    }
    if (found) paintFound(found, state, s);
    paint(state, { session: device ? s : null, emulator: emulator() });
    return state;
  };
  render();
  return {
    sessionChanged: render,
    firmwareChanged: render,
    /** The patcher saved a file or sent it to the Electribe. */
    done() { seen = true; markDone(storage); render(); },
    get view() { return shown; },
  };
}
