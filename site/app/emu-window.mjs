/**
 * The emulator in a window of its own, so it can sit on one screen and the
 * presets on another. That window draws the device and sends its keys to the
 * emulator service itself; the main page keeps its own connection for
 * presets and the terminal and shows a note where the device was.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { icon } from "./icons.mjs";
import { emulatorPanel, takeLink } from "./emulator.mjs";

const CHANNEL = "cee.emu.window";
const BEAT_MS = 1000;
// A window that has not said "here" for this long is gone; closing it in the app sends no last word.
const GONE_MS = 4000;
// Loading the page in the new window takes a moment before its first "here".
const START_MS = 8000;
// The app closes a window when it navigates here (src-tauri/src/main.rs); the address never loads.
const CLOSE_URL = "https://close.gelumpe.invalid/";

const inApp = () => !!window.__GELUMPE_APP || location.protocol === "tauri:" || location.hostname === "tauri.localhost";

/** On the main page: the button that opens the window, and the note with "Hier anzeigen" while it is open. */
export function emulatorWindow(emulator, { place }) {
  const channel = new BroadcastChannel(CHANNEL);
  const open = el("button", { type: "button", className: "btn sm cee-emu-pop", id: "cee-emu-pop" }, [icon("popout"), "Eigenes Fenster"]);
  const back = el("button", { type: "button", className: "btn", id: "cee-emu-back", textContent: "Hier anzeigen" });
  const note = el("div", { className: "cee-emu-away", id: "cee-emu-away", hidden: true }, [
    el("p", { textContent: "Der Emulator ist in einem eigenen Fenster geöffnet." }),
    back,
  ]);
  place(open);
  emulator.front.after(note);

  let away = false;
  let real = false;            // "Echtes Gerät" draws the real device in the front, so it stays here
  let win = null;
  let seen = 0;
  let ignoreUntil = 0;
  let firmware = emulator.firmware;

  const render = () => {
    emulator.front.hidden = away && !real;
    note.hidden = !away || real;
    open.hidden = away;
  };
  const leave = () => {
    away = true;
    render();
  };
  const home = () => {
    away = false;
    win = null;
    render();
  };

  open.addEventListener("click", () => {
    const url = new URL("emulator.html", location.href);
    const link = emulator.link;
    url.hash = link ? `emu=${link.port}:${link.token}` : "";
    win = window.open(url.href, "cee-emulator", "popup,width=1180,height=620");
    if (!win && !inApp()) { toast("Der Browser hat das Fenster blockiert. Erlaube Popups für diese Seite.", "error"); return; }
    seen = Date.now() + START_MS;
    leave();
  });
  back.addEventListener("click", () => {
    channel.postMessage({ type: "close" });
    try { win?.close(); } catch { /* the window closes itself on the message */ }
    ignoreUntil = Date.now() + GONE_MS;
    home();
  });

  channel.addEventListener("message", e => {
    if (e.data?.type === "bye") { home(); return; }
    if (e.data?.type !== "here" || Date.now() < ignoreUntil) return;
    seen = Math.max(seen, Date.now());
    // after a reload of this page the window is still open: take it as it is
    if (!away) leave();
  });
  setInterval(() => {
    if (!away) return;
    if (win?.closed || Date.now() - seen > GONE_MS) { home(); return; }
    // A new firmware chosen here: the window reads it again, so its power key starts the same file.
    if (emulator.firmware !== firmware) {
      firmware = emulator.firmware;
      channel.postMessage({ type: "firmware" });
    }
  }, BEAT_MS);
  render();

  return {
    /** The page shows the real device (true) or the emulator. */
    realDevice(on) { real = on; render(); },
  };
}

/** In the window itself: only the device, talking to the service directly. */
export function runEmulatorWindow() {
  const channel = new BroadcastChannel(CHANNEL);
  const { link } = takeLink();
  // The firmware choice lives on the main page; here it goes nowhere.
  const sub = { add: () => ({ body: el("div"), details: { open: false } }) };
  emulatorPanel(document.getElementById("cee-emu"), link, { sub });
  const here = () => channel.postMessage({ type: "here" });
  here();
  setInterval(here, BEAT_MS);
  window.addEventListener("pagehide", () => channel.postMessage({ type: "bye" }));
  channel.addEventListener("message", e => {
    if (e.data?.type === "close") {
      channel.postMessage({ type: "bye" });
      if (inApp()) location.href = CLOSE_URL;
      else window.close();
    }
    if (e.data?.type === "firmware") location.reload();
  });
}

if (document.documentElement.dataset.ceeView === "emulator") runEmulatorWindow();
