/**
 * The virtual SD card of the emulator. The card is one fixed folder on this computer, in
 * ~/.gelumpe/sd/card, laid out the way the firmware expects (KORG/...). The page does two things:
 * put the card in or take it out, and show the folder in the file manager. Only the local
 * emulator service can open the file manager, so both go through its routes under /sd
 * (tools/emu/server.py). Formatting is the firmware's own: DATA UTILITY, CARD FORMAT.
 *
 * While the card is in, the folder is write-protected and only the emulated Electribe changes
 * it. The card goes in and out also while the Electribe runs.
 *
 * Mounting: the panel reads the link from `emulator.link` and takes a new one through
 * connect(). `heading: false` leaves out the title when the host already names the block; `bar: true`
 * lays it out for the navbar, the switch and "SD-Karte öffnen" in a row, the state for screen readers only.
 *
 *   const sd = sdcardPanel(node, emulator, { bar: true });
 *   sd.connect(found.link);       // when the link changes later
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { t } from "./i18n.mjs";

const STYLE = new URL("./sdcard.css", import.meta.url).href;

/** What the panel shows for a state answered by GET /sd; a pure function so it can be tested. */
export function cardView(state) {
  if (!state?.available) return { available: false, checked: false, canOpen: false, line: t("sd.notConnected"), busy: false, error: "" };
  const busy = !!state.busy;
  return {
    available: true,
    checked: !!state.inserted,
    canOpen: true,
    line: busy ? t("sd.writing") : state.inserted ? t("sd.inserted") : t("sd.notInserted"),
    busy,
    error: state.error || "",
  };
}

export function sdcardPanel(root, emulator = null, { heading = true, bar = false } = {}) {
  if (typeof document !== "undefined" && !document.querySelector("link[data-cee-sd]")) {
    const css = el("link", { rel: "stylesheet", href: STYLE });
    css.setAttribute("data-cee-sd", "");
    document.head.append(css);
  }
  let explicit = null;
  let state = { available: false };
  let working = false;
  let events = null;
  let refreshTimer = null;

  const link = () => explicit ?? emulator?.link ?? null;

  const api = async (method, path) => {
    const l = link();
    if (!l) throw new Error(window.__GELUMPE_APP ? t("sd.appEmuDown") : t("sd.noLink"));
    let res;
    try {
      res = await fetch(`http://127.0.0.1:${l.port}${path}`, {
        method, body: method === "POST" ? "{}" : undefined, headers: { "X-Emu-Token": l.token, ...(method === "POST" ? { "Content-Type": "application/json" } : {}) },
      });
    } catch {
      throw new Error(window.__GELUMPE_APP ? t("sd.appEmuSilent") : t("sd.emuSilent", { port: l.port }));
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw Object.assign(new Error(data.error || t("sd.emuStatus", { status: res.status })), { status: res.status });
    return data;
  };

  // ---- parts of the page -------------------------------------------------------
  const status = el("p", { className: "muted", id: "cee-sd-status", role: "status", ariaLive: "polite" });
  const inserted = el("input", { type: "checkbox", id: "cee-sd-inserted" });
  inserted.setAttribute("role", "switch");
  const open = el("button", { type: "button", className: bar ? "btn sm" : "btn", id: "cee-sd-open", textContent: bar ? t("sd.openCard") : t("common.open") });
  let shownError = "";                       // the card's own error, toasted once when it comes up

  // What goes wrong in the background goes to a toast that goes away again; the line only says the state of the card.
  // An action the user started says its error in a toast that stays (run).
  let toldProblem = "";
  const say = (text) => { if (text !== toldProblem) toast(text, "info"); toldProblem = text; };

  function render() {
    const view = cardView(state);
    if (view.error && view.error !== shownError) toast(view.error, "info");
    shownError = view.error || "";
    status.textContent = view.line;
    inserted.checked = view.checked;
    inserted.disabled = !view.available || working;
    open.disabled = !view.canOpen || working;
  }

  // ---- data --------------------------------------------------------------------
  async function load() {
    state = await api("GET", "/sd").catch(e => { if (e.status === 404) return { available: false }; throw e; });
    toldProblem = "";
    render();
  }

  /** One action at a time: the controls stay off until it is done, errors go to the toast. */
  async function run(action) {
    if (working) return;
    working = true;
    render();
    try {
      await action();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      working = false;
      try { await load(); } catch (e) { say(e.message); }
    }
  }

  // ---- events from the service ---------------------------------------------------
  function listen() {
    events?.close();
    const l = link();
    if (!l || typeof EventSource === "undefined") return;
    events = new EventSource(`http://127.0.0.1:${l.port}/events?token=${encodeURIComponent(l.token)}`);
    let seen = null;
    events.addEventListener("status", e => {
      const s = JSON.parse(e.data);
      const now = `${s.state}|${s.card?.name ?? ""}`;
      if (now !== seen) { seen = now; refreshSoon(); }
    });
    events.addEventListener("sd", e => {
      const { busy } = JSON.parse(e.data);
      state = { ...state, busy };
      render();
      if (!busy) refreshSoon();            // the firmware stopped writing: look again
    });
  }

  function refreshSoon() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => { if (!working) load().catch(e => say(e.message)); }, 400);
  }

  // ---- controls ------------------------------------------------------------------
  inserted.addEventListener("change", () => {
    const want = inserted.checked;
    run(() => api("POST", want ? "/sd/insert" : "/sd/eject"));
  });

  open.addEventListener("click", () => run(() => api("POST", "/sd/open")));

  // ---- layout --------------------------------------------------------------------
  if (bar) {
    status.className = "ui-sr-only";
    root.replaceChildren(
      el("label", { className: "ui-switch cee-sd-switch" }, [inserted, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("sd.cardIn")]),
      open,
      status,
    );
  } else root.replaceChildren(...[
    heading ? el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("sd.title") })]) : null,
    el("div", { className: "actions cee-sd-actions" }, [
      el("label", { className: "ui-switch" }, [inserted, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("sd.insert")]),
      open,
    ]),
    status,
  ].filter(Boolean));
  render();
  if (link()) { listen(); load().catch(e => say(e.message)); }

  return {
    /** Use another link to the service, e.g. after the page found it. */
    connect(next) {
      explicit = next;
      listen();
      load().catch(e => say(e.message));
    },
    refresh: () => load(),
  };
}
