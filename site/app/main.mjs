/**
 * The editor page: load a pattern backup or a single pattern, edit it in
 * plain words, save it. The file never leaves the browser.
 */
import { PatternFile, Pattern, parseSinglePattern, toSinglePattern, FileError } from "../../src/pattern.mjs";
import { fieldsOf, field } from "../../src/map/index.mjs";
import { control, el } from "./fields.mjs";
import { stepEditor } from "./steps.mjs";
import { devicePanel } from "./device.mjs";
import { fxPanel } from "./fx.mjs";
import { levelsPanel } from "./levels.mjs";
import { modulationsPage } from "./modulations.mjs";
import { samplesPage } from "./samples.mjs";
import { emulatorPanel, takeLink, findLink } from "./emulator.mjs";
import { followDevice } from "./follow.mjs";
import { emulatorWindow } from "./emu-window.mjs";
import { subnav } from "./subnav.mjs";
import { sdcardPanel } from "./sdcard.mjs";
import { patcherPage } from "./patcher.mjs";
import { patternToolsPage } from "./pattern-tools.mjs";
import { rescuePage } from "./rescue.mjs";
import { changelogPage } from "./changelog.mjs";
import { splashPage } from "./splash.mjs";
import { terminalPanel } from "./terminal.mjs";
import { featuresPage, featureCards } from "./features.mjs";
import { baukastenPage } from "./baukasten.mjs";
import { scriptsPanel } from "./scripts.mjs";
import { Terminal } from "../../src/terminal.mjs";
import { loadBlechSet } from "../../src/patcher.mjs";
import { patchesPresent, selectFor } from "../../src/patch.mjs";
import { sharedProbe } from "./probe.mjs";
import { dropdown } from "./dropdown.mjs";
import { icon } from "./icons.mjs";
import { watchForUpdate, showNews } from "./update.mjs";
import { apply as applySettings, settingsButton, settingsPage } from "./settings.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";

const $ = sel => document.querySelector(sel);

/** Whether Korgs build carries BLECH already; the set that says what BLECH is loads once. Unreadable counts as yes. */
let blechSet = null;
async function hasBlech(bytes) {
  try {
    blechSet ??= await loadBlechSet(async url => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(url);
      return res.json();
    });
    return (await patchesPresent(bytes, selectFor(blechSet.patches, "stock").patches)).some(p => p.present);
  } catch {
    return true;
  }
}

/** The pages that read Hacktribes tables: Korgs plain build has none of them. */
const NEEDS_TABLES = ["fx", "mod"];

/** Fields a person may change in this phase: plain fields, no expert ones. */
const editable = f => f.edit !== "readonly" && f.edit !== "expert" && f.source !== "unknown";

const PART_GROUPS = [
  ["Klang", ["sample", "oscEdit", "pitch", "glide", "voiceAssign"]],
  ["Filter", ["filterType", "cutoff", "resonance", "egInt"]],
  ["Modulation", ["modType", "modSpeed", "modDepth"]],
  ["Hüllkurve und Pegel", ["egOn", "attack", "decay", "level", "pan"]],
  ["Effekte und Groove", ["ifxOn", "ifxType", "ifxEdit", "mfxSend", "grooveType", "grooveDepth"]],
  ["Spielweise", ["mute", "priority", "padVelocity", "scaleMode", "motionMode"]],
];

/** The open file, the pattern being edited and what can be undone. */
const doc = {
  kind: null,           // "backup" | "single"
  fileName: null,
  file: null,
  pattern: null,
  number: 1,
  history: [],
  open: null,

  get(id, ix = []) { return this.pattern.raw(id, ix); },

  set(id, ix, raw) {
    const change = this.pattern.setRaw(id, ix, raw);
    this.commit();
    if (this.open) this.open.push(change);
    else this.history.push({ number: this.number, changes: [change] });
    updateActions();
    return change;
  },

  /** Several writes that undo as one, such as switching a step on. */
  group(fn) {
    this.open = [];
    try { fn(); } finally {
      if (this.open.length) this.history.push({ number: this.number, changes: this.open });
      this.open = null;
      updateActions();
    }
  },

  commit() { if (this.kind === "backup") this.file.replace(this.number, this.pattern); },

  undo() {
    const entry = this.history.pop();
    if (!entry) return;
    if (entry.number !== this.number) selectPattern(entry.number);
    for (const change of [...entry.changes].reverse()) this.pattern.undo(change);
    this.commit();
    renderPattern();
    updateActions();
  },

  bytes() { return this.kind === "backup" ? this.file.toBytes() : toSinglePattern(this.pattern); },
};

function updateActions() {
  const loaded = !!doc.pattern;
  window.dispatchEvent(new Event("cee:pattern-loaded"));
  $("#cee-save").disabled = !loaded;
  $("#cee-undo").disabled = !doc.history.length;
  $("#cee-changes").textContent = doc.history.length ? `${doc.history.length} Änderungen` : "";
}

function section(title, children, meta = "") {
  return el("section", { className: "ui-section" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: title }), meta ? el("span", { className: "ui-section-meta", textContent: meta }) : null]),
    ...children,
  ]);
}

const controls = [];
function fieldControl(id, ix = []) {
  const f = field(id);
  const c = control(f, () => doc.get(id, ix), raw => doc.set(id, ix, raw));
  controls.push(c);
  return c.node;
}

let steps = null;
let partTabs = null;
let currentPart = 0;

function partPanel(p) {
  const known = new Set(PART_GROUPS.flatMap(([, ids]) => ids));
  const rest = fieldsOf("pattern").filter(f => f.area === "parts" && editable(f) && !known.has(f.id.slice(5)));
  const groups = PART_GROUPS.map(([title, ids]) =>
    el("div", { className: "cee-group" }, [el("h3", { textContent: title }), el("div", { className: "cee-grid" }, ids.map(id => fieldControl(`part.${id}`, [p])))]));
  if (rest.length) groups.push(el("div", { className: "cee-group" }, [el("h3", { textContent: "Weitere" }), el("div", { className: "cee-grid" }, rest.map(f => fieldControl(f.id, [p])))]));
  return groups;
}

function renderPattern() {
  controls.length = 0;
  const main = $("#cee-main");
  const patternFields = fieldsOf("pattern").filter(f => editable(f) && f.area === "pattern");
  const masterFields = fieldsOf("pattern").filter(f => editable(f) && f.area === "master");

  const tabs = el("div", { className: "ui-tabs cee-part-tabs" });
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Parts");
  // One panel per tab, as ui.tabs expects; only the open one holds controls.
  const panels = [];
  for (let p = 0; p < 16; p++) {
    const tab = el("button", { type: "button", className: "ui-tab", id: `cee-part-tab-${p}`, textContent: String(p + 1) });
    tab.setAttribute("role", "tab");
    tab.dataset.tab = String(p);
    tab.setAttribute("aria-controls", `cee-part-panel-${p}`);
    tab.setAttribute("aria-selected", String(p === currentPart));
    tab.setAttribute("aria-label", `Part ${p + 1}`);
    if (p !== currentPart) tab.tabIndex = -1;
    tabs.append(tab);
    const panel = el("div", { className: "ui-tabpanel", id: `cee-part-panel-${p}`, tabIndex: 0, hidden: p !== currentPart });
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", `cee-part-tab-${p}`);
    panels.push(panel);
  }

  steps = stepEditor(doc);
  const name = doc.get("pattern.name") || "ohne Namen";
  main.replaceChildren(
    section(doc.kind === "backup" ? `Pattern ${doc.number}: ${name}` : name, [el("div", { className: "cee-grid" }, patternFields.map(f => fieldControl(f.id)))]),
    section("Master-Effekt", [el("div", { className: "cee-grid" }, masterFields.map(f => fieldControl(f.id)))]),
    section("Parts", [tabs, ...panels]),
    section("Steps", [steps.node], `Part ${currentPart + 1}`),
  );

  const showPart = p => {
    currentPart = p;
    controls.length = 0;
    panels.forEach((panel, i) => panel.replaceChildren(...(i === p ? partPanel(p) : [])));
    steps.show(p);
    main.querySelector(".ui-section:last-child .ui-section-meta").textContent = `Part ${p + 1}`;
  };
  if (window.ui?.tabs) {
    partTabs = window.ui.tabs(tabs, { hash: false, onChange: id => showPart(Number(id)) });
    partTabs.select(String(currentPart), { persist: false });
  }
  showPart(currentPart);
}

function selectPattern(n) {
  doc.number = n;
  doc.pattern = doc.file.pattern(n);
  for (const b of document.querySelectorAll(".cee-pattern-list button")) b.setAttribute("aria-current", String(Number(b.dataset.n) === n));
}

function renderList() {
  const list = el("ul", { className: "ui-list cee-pattern-list" });
  for (let n = 1; n <= doc.file.count; n++) {
    const b = el("button", { type: "button", className: "cee-pattern-item" }, [el("span", { className: "cee-pattern-num", textContent: String(n) }), el("span", { className: "ui-truncate", textContent: doc.file.name(n) || "ohne Namen" })]);
    b.dataset.n = String(n);
    list.append(el("li", {}, b));
  }
  list.addEventListener("click", e => {
    const b = e.target.closest("button[data-n]");
    if (!b) return;
    selectPattern(Number(b.dataset.n));
    renderPattern();
  });
  $("#cee-side").replaceChildren(el("h2", { className: "ui-section-title", textContent: "Patterns" }), list);
}

async function load(file) {
  const input = $("#cee-file");
  const error = $("#cee-error");
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    // Parse into locals first; the open document changes only when this worked.
    const single = bytes.length === 0x100 + 0x4000;
    const parsed = single ? parseSinglePattern(bytes) : PatternFile.parse(bytes);
    error.hidden = true;
    doc.history = [];
    doc.fileName = file.name;
    doc.kind = single ? "single" : "backup";
    if (single) {
      doc.file = null;
      doc.pattern = parsed;
      $("#cee-split").dataset.single = "true";
      $("#cee-side").replaceChildren();
    } else {
      doc.file = parsed;
      $("#cee-split").dataset.single = "false";
      renderList();
      selectPattern(1);
    }
    $("#cee-start").hidden = true;
    $("#cee-split").hidden = false;
    $("#cee-loaded").textContent = `${file.name}, ${single ? "ein Pattern" : `${doc.file.count} Patterns`}`;
    renderPattern();
    updateActions();
  } catch (e) {
    const message = e instanceof FileError ? e.message : `Die Datei ließ sich nicht lesen: ${e.message}`;
    if (window.ui?.rejectFile) window.ui.rejectFile(input, message);
    error.textContent = message;
    error.hidden = false;
  }
}

function save() {
  saveFile(doc.bytes(), doc.fileName || "patterns.e2sallpat");
}

/** Fetching from and sending to the device's pattern buffer. */
function patternDevice(device) {
  const say = (text, kind = "info") => { toast(text, kind); };
  const update = () => {
    const s = device.session;
    $("#cee-pattern-device").hidden = !s;
    $("#cee-send-pattern").disabled = !s || !doc.pattern;
    $("#cee-pattern-undo").disabled = !s || !s.history.some(h => h.pattern);
  };

  $("#cee-fetch").addEventListener("click", async () => {
    if (doc.history.length && !(await window.ui.confirm({ title: "Ungespeicherte Änderungen verwerfen?", text: "Das geholte Pattern ersetzt, was gerade offen ist.", confirmLabel: "Verwerfen und holen", danger: true }))) return;
    if (device.session?.busy) return;
    try {
      const block = await device.session.fetchPattern();
      doc.kind = "single";
      doc.file = null;
      doc.fileName = "vom-geraet.e2spat";
      doc.history = [];
      doc.pattern = new Pattern(block);
      $("#cee-split").dataset.single = "true";
      $("#cee-side").replaceChildren();
      $("#cee-start").hidden = true;
      $("#cee-split").hidden = false;
      $("#cee-loaded").textContent = "Pattern-Puffer vom Gerät";
      renderPattern();
      updateActions();
      say(`Geholt: "${doc.pattern.name || "ohne Namen"}".`, "ok");
    } catch (e) {
      say(`Das Pattern ließ sich nicht holen. Ist die Electribe noch verbunden? (${e.message})`, "error");
    }
    update();
  });

  $("#cee-send-pattern").addEventListener("click", async () => {
    const s = device.session;
    if (!s) return;
    const buttons = ["#cee-send-pattern", "#cee-pattern-undo", "#cee-fetch"].map(sel => $(sel));
    buttons.forEach(b => { b.disabled = true; });
    const release = s.reserve();
    try {
      await s.idle();
      await sendPattern(s);
    } catch (e) {
      say(`Abgebrochen: ${e.message}`, "error");
    } finally {
      release();
      buttons.forEach(b => { b.disabled = false; });
      update();
    }
  });

  async function sendPattern(s) {
    let active = "unbekannt";
    try { active = new Pattern(await s.fetchPattern()).name || "ohne Namen"; } catch (e) {
      say(`Die App konnte das aktuelle Pattern am Gerät nicht sichern, deshalb sendet sie nichts. Verbinde die Electribe neu und versuch es nochmal. (${e.message})`, "error");
      return;
    }
    const edit = { kind: "patternSend", block: Uint8Array.from(doc.pattern.bytes) };
    const checked = await s.check(edit);
    if (checked.verdict === "blocked") { say(`Gesperrt: ${checked.reasons.map(r => r.message).join(" ")}`, "error"); return; }
    const warnings = checked.reasons.map(r => `Warnung: ${r.message}`).join("\n");
    const yes = await window.ui.confirm({
      title: "Pattern ans Gerät senden?",
      text: `Am Gerät ist gerade "${active}" im Puffer. Er wird vorher gesichert und lässt sich zurückholen. Dauerhaft wird das gesendete Pattern erst mit Write am Gerät.${warnings ? `\n\n${warnings}` : ""}`,
      confirmLabel: "Senden",
    });
    if (!yes) return;
    say("Sende …");
    const res = await s.apply(edit, { confirmed: checked.token });
    if (res.ok) say(`Gesendet und zurückgelesen. Vorher im Puffer: "${active}", mit "Senden zurücknehmen" zurückzuholen.`, "ok");
    else if (res.needsConfirmation) say("Am Gerät hat sich inzwischen etwas geändert. Klick bitte nochmal auf Senden.", "error");
    else if (res.gate?.verdict === "blocked") say(`Gesperrt: ${res.gate.reasons.map(r => r.message).join(" ")}`, "error");
    else say(`${res.error?.message ?? "Abgebrochen."}${res.pending?.now ? ` ${res.pending.now.text}` : ""}${s.blocked ? " Entscheide links unter Gerät, wie es weitergeht." : ""}`, "error");
    device.log?.(res.ok ? "Pattern gesendet." : `Pattern: ${res.error?.message ?? "gesperrt"}`, res.ok ? "ok" : "error");
    if (s.blocked) device.showDecision?.();
  }

  $("#cee-pattern-undo").addEventListener("click", async () => {
    const s = device.session;
    if (!s) return;
    const release = s.reserve();
    try {
      await s.idle();
      const res = await s.undo();
      say(res.ok ? "Der vorherige Puffer ist wieder am Gerät." : `Zurücknehmen hat nicht geklappt: ${res.error.message}`, res.ok ? "ok" : "error");
    } catch (e) {
      say(`Zurücknehmen hat nicht geklappt: ${e.message}`, "error");
    } finally {
      release();
      update();
    }
  });

  return { update };
}

/** Pages that share one navbar title: a menu switches between the emulator and the real device. */
const MODES = { emu: "Emulator", device: "Echtes Gerät" };

/** Navbar: the title of the open page, and whether a device is connected, as words. */
function navbar({ onMode }) {
  let page = "start";
  let connectButton = null;
  let device = false;
  let emuAction = null;
  let cardButton = null;
  let consoleAction = null;
  let pluginActions = [];
  let baukastenActions = [];
  const trails = {};
  $("#cee-mode-button").append(icon("chevronDown"));
  const menu = dropdown($("#cee-mode-button"), $("#cee-mode-menu"), { onPick: onMode });
  function render() {
    const mode = page in MODES;
    $("#cee-nav-title").hidden = mode;
    $("#cee-mode").hidden = !mode;
    if (mode) {
      $("#cee-mode-label").textContent = MODES[page];
      for (const item of $("#cee-mode-menu").querySelectorAll("[role=menuitemradio]")) item.setAttribute("aria-checked", String(item.dataset.value === page));
    } else {
      // A page with sub-pages shows where you are as a breadcrumb: Plugins › Dokumentation › the section you read.
      // Every crumb but the last leads back: the title to the page's start, a step with `go` to that step.
      const parts = trails[page] ?? [];
      const tab = $(`#cee-tab-${page}`);
      const title = parts.length && tab ? el("button", { type: "button", className: "cee-crumb-link", textContent: tab.textContent, onclick: () => tab.click() }) : tab?.textContent ?? "";
      $("#cee-nav-title").replaceChildren(title, ...parts.map((t, i) => {
        const text = typeof t === "string" ? t : t.text;
        return t.go && i < parts.length - 1
          ? el("span", { className: "cee-crumb" }, el("button", { type: "button", className: "cee-crumb-link", textContent: text, onclick: t.go }))
          : el("span", { className: "cee-crumb", textContent: text });
      }));
    }
    // On the device page the navbar carries the connect button while no device is attached (it moves there from
    // the page, so its handlers stay), and the words "Gerät verbunden" once one is.
    connectButton ??= $("#cee-connect");
    const state = page === "emu" ? [cardButton, emuAction].filter(Boolean) : page === "console" ? [consoleAction].filter(Boolean) : page === "scripts" ? pluginActions : page === "baukasten" ? baukastenActions : page !== "device" ? [] : device ? [el("span", { className: "cee-nav-fact", textContent: "Gerät verbunden" })] : connectButton ? [connectButton] : [];
    $("#cee-nav-state").replaceChildren(...state);
  }
  return {
    page(id) { menu.close(); page = id; render(); },
    device(on) { device = on; render(); },
    /** A control the emulator page puts into the navbar (the button for its own window). */
    emu(node) { emuAction = node; render(); },
    /** The emulator's SD card: its switch and the button that opens its folder. */
    card(node) { cardButton = node; render(); },
    /** The console's switch that lets scripts go on to the real device. */
    console(node) { consoleAction = node; render(); },
    /** Öffnen and Speichern of the plugin editor while it is open. */
    plugins(nodes) { pluginActions = nodes; render(); },
    /** Exportieren of the Baukasten while its export page is open. */
    baukasten(nodes) { baukastenActions = nodes; render(); },
    /** The breadcrumb after the title of `id`: the sub-page and, in the docs, the section. */
    trail(id, parts) { trails[id] = parts; if (id === page) render(); },
  };
}

/** The emulator's SD card in the navbar: the switch that puts it in and the button that shows its folder. */
function cardBar(nav) {
  const bar = el("div", { className: "cee-sd-bar", id: "cee-emu-card" });
  nav.card(bar);
  return bar;
}

/** Below 60rem the sidebar is a drawer behind the menu button. */
function sidebarDrawer() {
  const side = $("#cee-sidebar");
  const button = $("#cee-menu");
  const set = open => {
    side.toggleAttribute("data-open", open);
    button.setAttribute("aria-expanded", String(open));
    // The drawer stands before the page in the tab order, so the focus has to go in.
    if (open) (side.querySelector("[role=tab][aria-selected=true]") ?? side.querySelector("a, button"))?.focus();
  };
  button.addEventListener("click", () => set(!side.hasAttribute("data-open")));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && side.hasAttribute("data-open")) { set(false); button.focus(); }
  });
  // The drawer covers the menu button; a tap on the page beside it closes it.
  document.addEventListener("pointerdown", e => {
    if (side.hasAttribute("data-open") && !side.contains(e.target) && !button.contains(e.target)) set(false);
  });
  return { close: () => set(false) };
}

/** The sidebar folds away on wide screens; the choice is kept in this browser. */
function sidebarFold() {
  const app = $(".cee-app");
  const button = $("#cee-collapse");
  const set = fold => {
    app.toggleAttribute("data-collapsed", fold);
    button.setAttribute("aria-expanded", String(!fold));
    try { localStorage.setItem("cee.fold", fold ? "1" : "0"); } catch {}
  };
  try { if (localStorage.getItem("cee.fold") === "1") set(true); } catch {}
  button.addEventListener("click", () => set(!app.hasAttribute("data-collapsed")));
}

function boot() {
  applySettings();
  settingsPage($("#cee-settings"));
  const changelog = changelogPage($("#cee-changelog"), $("#cee-tab-changelog"));
  settingsButton($("#cee-settings-button"), () => { areas?.select("settings"); drawer.close(); });
  const emu = takeLink();
  let areas = null;
  // Picking the mode that is open already changes nothing; ui.tabs would show the empty device panel instead of the drawing.
  const nav = navbar({ onMode: id => { if (id !== areas?.current) areas?.select(id, { focus: false }); } });
  const drawer = sidebarDrawer();
  sidebarFold();
  const options = subnav();
  let fx = null;
  let patterns = null;
  let ptools = null;
  let emulator = null;
  let follow = null;
  let popout = null;
  let terminal = null;
  let sd = null;
  // One session on the emulator's port, shared by the effect editor's probe and the terminal's rehearsal.
  const probe = sharedProbe(() => emulator?.port, () => emulator?.lack("sysex") ?? null);
  let restrictNow = () => {};
  const device = devicePanel($("#cee-device"), {
    onSession: () => { restrictNow(); fx?.sessionChanged(); patterns?.update(); ptools?.sessionChanged(); nav.device(!!device?.session); terminal?.update(); },
    emulator: () => emulator?.port,
    view: () => emulator,
    probe,
  });
  // "Echtes Gerät" shows the emulator's Electribe drawing; the connection controls sit above it in that mode only.
  $("#cee-emu").before($("#cee-device"));
  $("#cee-device").hidden = true;
  patterns = patternDevice(device);
  ptools = patternToolsPage($("#cee-ptools"), { device });
  // The device page is one of the two modes of the emulator entry, so its own tab stays out of the list.
  // Pattern-Werkzeuge and Samples are built but not offered (docs/entscheidungen.md). Without ?labs their tabs
  // leave the list before ui.tabs reads it, so neither the navigation nor #ptools / #samples reaches them.
  if (!new URLSearchParams(location.search).has("labs")) for (const tab of document.querySelectorAll("#cee-areas [data-labs]")) tab.remove();
  const listed = () => areas.ids.filter(id => !$(`#cee-tab-${id}`).hidden && $(`#cee-tab-${id}`).getAttribute("aria-disabled") !== "true");
  /** Korgs plain build or the synth's in the emulator and no real device: Presets and Modulationen stay shut, visibly. */
  let plainStock = false;
  let plainWhy = "Nicht mit Korgs Original-Firmware";
  const restrict = () => {
    const none = !emulator?.firmware;
    const shut = (plainStock || none) && !device.session;
    for (const id of NEEDS_TABLES) {
      const tab = $(`#cee-tab-${id}`);
      tab.setAttribute("aria-disabled", String(shut));
      if (shut) tab.title = none ? "Erst im Emulator eine Firmware (VSB) wählen oder ein Gerät verbinden" : plainWhy;
      else tab.removeAttribute("title");
    }
    if (shut && NEEDS_TABLES.includes(areas?.current)) areas.select("emu", { focus: false });
  };
  const shown = id => (id === "device" ? "emu" : id);
  areas = window.ui?.tabs ? window.ui.tabs($("#cee-areas"), {
    persist: "cee.area",
    onChange: id => {
      nav.page(id);
      options.page(id);
      $("#cee-settings-button").toggleAttribute("aria-current", id === "settings");
      $("#cee-tab-emu").toggleAttribute("data-active", id === "device");
      $("#cee-device").hidden = id !== "device";
      if (id === "device") { $("#cee-area-emu").hidden = false; $("#cee-area-device").hidden = true; }
      popout?.realDevice(id === "device");
      if (id === "console") terminal?.update();
      if (id === "changelog") changelog.opened();
    },
  }) : null;
  $("#cee-areas").addEventListener("click", e => { if (e.target.closest("[role=tab]")) drawer.close(); });
  if (areas) {
    nav.page(areas.current);
    options.page(areas.current);
    $("#cee-tab-emu").toggleAttribute("data-active", areas.current === "device");
    $("#cee-device").hidden = areas.current !== "device";
    if (areas.current === "device") { $("#cee-area-emu").hidden = false; $("#cee-area-device").hidden = true; }
  }
  // The tab list stands vertically and skips the hidden tab; ui.tabs would walk into it.
  $("#cee-areas").addEventListener("keydown", e => {
    const keys = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1, Home: "first", End: "last" };
    if (!areas || !(e.key in keys) || !e.target.closest("[role=tab]") || e.altKey || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    e.stopPropagation();
    const ids = listed();
    const at = ids.indexOf(shown(areas.current));
    const to = keys[e.key] === "first" ? 0 : keys[e.key] === "last" ? ids.length - 1 : (at + keys[e.key] + ids.length) % ids.length;
    areas.select(ids[to], { focus: true });
  }, true);
  restrictNow = restrict;
  window.addEventListener("cee:pattern-loaded", () => patterns.update());
  let storage = null;
  try { storage = window.localStorage; } catch { /* blocked: the scripts and the follow switch stay in memory */ }
  follow = followDevice({ device, emulator: () => emulator, probe, fx: () => fx, storage });
  fx = fxPanel($("#cee-fx"), {
    device, embedded: true,
    onSent: sent => follow?.redraw(sent),
    pickerExtra: follow.node,
    idle: "Wähle im Bereich Emulator die Firmware (VSB). Die Presets liest dieser Bereich aus dem laufenden Emulator, bei verbundenem Gerät aus dem Gerät.",
    live: async () => (emulator?.port.running ? probe() : null),
    emulator: () => emulator,
  });
  levelsPanel($("#cee-levels"), {
    session: async () => device.session ?? (emulator?.port.running ? probe() : null),
    presets: () => fx.presets(),
    openPreset: slot => { if (fx.open("ifx", slot)) $("#cee-fx").scrollIntoView?.({ block: "start" }); },
    device,
  });
  emulator = emulatorPanel($("#cee-emu"), emu.link, { deviceArea: device, onConnect: next => sd?.connect(next) });
  const modulations = modulationsPage($("#cee-mod"), { emulator });
  const baukasten = baukastenPage($("#cee-baukasten"), { emulator, sub: options, trail: parts => nav.trail("baukasten", parts), navbar: nodes => nav.baukasten(nodes) });
  samplesPage($("#cee-samples"), { device, emulator, probe });
  let fxFirmware = null;
  let modFirmware = null;
  let plainFor = null;
  let fxRunning = false;
  let noFirmware = null;
  setInterval(() => {
    const running = !!emulator.port.running;
    if (running !== fxRunning) { fxRunning = running; if (running) setTimeout(() => fx.refresh(), 3000); }
    if (emulator.firmware && emulator.firmware !== fxFirmware) {
      fxFirmware = emulator.firmware;
      fx.loadBytes(fxFirmware).catch(() => {});
      terminal?.update();
    }
    if (emulator.firmware && emulator.firmware !== plainFor) {
      const bytes = plainFor = emulator.firmware;
      // the synth has none of Hacktribe's tables, with or without patches
      (emulator.build === "stock" ? hasBlech(bytes).then(yes => !yes) : Promise.resolve(emulator.build === "synth")).then(plain => {
        if (plainFor !== bytes) return;
        plainStock = plain;
        plainWhy = emulator.build === "synth" ? "Nicht mit der Firmware der blauen Electribe 2" : "Nicht mit Korgs Original-Firmware";
        restrict();
      });
    }
    if (emulator.firmware && emulator.firmware !== modFirmware) { modFirmware = emulator.firmware; modulations.loadBytes(modFirmware).catch(() => {}); }
    baukasten.update();
    if (!emulator.firmware !== noFirmware) { noFirmware = !emulator.firmware; restrict(); }
  }, 1000);
  // Shut from the first frame, not a second later: before that a click still opened a page without its tables.
  noFirmware = !emulator.firmware;
  restrict();
  sd = sdcardPanel(cardBar(nav), emulator, { bar: true });
  popout = emulatorWindow(emulator, { place: node => nav.emu(node) });
  popout.realDevice(areas?.current === "device");
  patcherPage($("#cee-patcher"), { emulator, show: id => areas?.select(id), session: () => device.session ?? null });
  rescuePage($("#cee-rescue"));
  featuresPage($("#cee-features"));
  featureCards($("#cee-start-features"));
  splashPage($("#cee-splash"));
  // A run from the console opens the Plugins page, where the run area shows it.
  const scripts = scriptsPanel($("#cee-scripts"), { storage, sub: options, session: () => device.session ?? null, onRun: () => areas?.select("scripts", { focus: false }), trail: parts => nav.trail("scripts", parts), navbar: nodes => nav.plugins(nodes) });
  // The console always talks to the emulator; this switch in the navbar lets a script go on to a connected Electribe.
  const forward = el("input", { type: "checkbox", role: "switch", id: "cee-term-forward" });
  nav.console(el("label", { className: "ui-switch cee-term-forward" }, [forward, el("span", { className: "ui-switch-track", ariaHidden: "true" }), "An echtes Gerät weiterleiten"]));
  terminal = terminalPanel($("#cee-terminal"), {
    terminal: new Terminal({ device, emulator, probe, forward: () => forward.checked }),
    device, scripts, forward,
    lack: () => emulator.lack("sysex"),
    power: () => emulator.powerOn(),
  });
  // The app always starts with the link in its address and opens on the start page; a link opened in the browser goes to the emulator.
  if (emu.fresh) areas?.select(window.__GELUMPE_APP ? "start" : "emu");
  else findLink(emu).then(found => {
    if (!found.fresh) return;
    emulator.connect(found.link);
    sd.connect(found.link);
    areas?.select("emu");
  });

  $("#cee-file").addEventListener("change", e => {
    $("#cee-error").hidden = true;
    const f = e.target.files?.[0];
    if (f) load(f);
  });
  $("#cee-reload").addEventListener("change", e => {
    const f = e.target.files?.[0];
    if (f) load(f);
    e.target.value = "";
  });
  $("#cee-save").addEventListener("click", save);
  $("#cee-undo").addEventListener("click", () => doc.undo());
  document.addEventListener("keydown", e => {
    const inPatterns = !$("#cee-area-patterns").hidden;
    const typing = e.target.closest("input:not([type=range]):not([type=checkbox]):not([type=radio]), textarea, select");
    if ((e.metaKey || e.ctrlKey) && e.key === "z" && !e.shiftKey && inPatterns && !typing) {
      e.preventDefault();
      doc.undo();
    }
  });
  updateActions();
  document.documentElement.dataset.ceeReady = "1";
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
else boot();

watchForUpdate($("#cee-update"));
showNews(toast);

// In the desktop app a new window goes nowhere: the donate and Korg links navigate in place and the app opens them in the browser (src-tauri).
if (window.__GELUMPE_APP) for (const link of document.querySelectorAll("a[href^='https://www.paypal.me/'], a[href^='https://www.korg.com/']")) link.target = "_self";
