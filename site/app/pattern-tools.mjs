/**
 * Pattern-Werkzeuge: Übergänge zwischen zwei Patterns bauen (src/transition.mjs) und einen Part
 * würfeln (src/dice.mjs). Kein Pattern-Editor: die Seite liest Patterns aus einer Sicherung, einer
 * Einzeldatei oder dem Pattern-Puffer des verbundenen Geräts, rechnet eine Vorschau und gibt das
 * Ergebnis weiter, als Datei, als Kopie der Sicherung mit neuen Patterns oder ans Gerät. Nichts
 * davon verändert die geladene Datei, und ans Gerät geht nur, was Linter und Türsteher durchlassen
 * und du bestätigt hast.
 */
import { el } from "./fields.mjs";
import { saveFile } from "./save-file.mjs";
import { toast } from "./toast.mjs";
import { stepEditor } from "./steps.mjs";
import { PatternFile, Pattern, parseSinglePattern, toSinglePattern, FileError, cleanName, NAME_LENGTH } from "../../src/pattern.mjs";
import { makeTransitions, checkTransition, pickSlots, describe } from "../../src/transition.mjs";
import { rollPart, checkRoll, SCALES, ROOTS, DEFAULTS } from "../../src/dice.mjs";
import { summarize, isFree, NO_SAMPLE } from "../../src/pattern-set.mjs";

const SLOTS = 250;
const MAX_DEVICE_COPIES = 8;

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

function field(id, label, input, help) {
  return el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id, textContent: label }), input, help ? el("p", { className: "ui-field-help", textContent: help }) : null]);
}

function selectField(id, label, options, value, onChange) {
  const input = el("select", { className: "select", id });
  for (const [v, text] of options) input.append(el("option", { value: String(v), textContent: text }));
  input.value = String(value);
  input.addEventListener("change", () => onChange(input.value));
  return { node: field(id, label, input), input };
}

function numberField(id, label, { min, max, value, onChange, help = "" }) {
  const input = el("input", { className: "input", id, type: "number", min, max, step: 1, value: String(value) });
  input.addEventListener("input", () => onChange(input.value));
  return { node: field(id, label, input, help), input };
}

function textField(id, label, { value = "", placeholder = "", onChange, help = "" }) {
  const input = el("input", { className: "input", id, type: "text", maxLength: NAME_LENGTH, spellcheck: false, autocomplete: "off", value, placeholder });
  input.addEventListener("change", () => onChange(input.value));
  return { node: field(id, label, input, help), input };
}

function switchField(id, label, checked, onChange) {
  const input = el("input", { type: "checkbox", id, checked });
  input.setAttribute("role", "switch");
  input.addEventListener("change", () => onChange(input.checked));
  return { node: el("div", { className: "cee-field" }, [el("label", { className: "ui-switch" }, [input, el("span", { className: "ui-switch-track", ariaHidden: "true" }), label])]), input };
}

function rangeField(id, label, { min, max, value, show, onChange }) {
  const input = el("input", { type: "range", className: "ui-range", id, min, max, step: 1, value: String(value) });
  const out = el("output", { className: "ui-range-value" });
  const sync = () => { out.textContent = show(Number(input.value)); input.setAttribute("aria-valuetext", out.textContent); window.ui?.syncRange(input); };
  input.addEventListener("input", () => { sync(); onChange(Number(input.value)); });
  sync();
  return { node: el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id }, [label, " ", out]), input]), input, sync };
}

const fileStem = name => String(name || "patterns").replace(/\.[^.]*$/, "");
const safe = name => (name.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "pattern");
const randomSeed = () => crypto.getRandomValues(new Uint32Array(1))[0];

export function patternToolsPage(root, { device }) {
  /** What the pickers offer: the loaded backup or single file, and copies of the device's buffer. */
  const pool = { file: null, fileName: "", single: null, free: new Set(), copies: [], copyCount: 0 };
  const pickers = [];
  // Messages go to the toast; only a running step ("Sende …") stands in the line.
  const say = (text, tone = "info") => {
    line.textContent = tone === "progress" ? text : "";
    if (tone !== "progress") toast(text, tone);
  };
  const line = el("p", { className: "muted ui-break", id: "cee-pt-line", role: "status" });

  // ---- Quelle ----
  const input = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-pt-file", accept: ".e2sallpat,.e2spat" });
  const loaded = el("p", { className: "muted", id: "cee-pt-loaded", textContent: "Noch keine Datei geladen." });
  input.addEventListener("change", () => { const f = input.files?.[0]; if (f) load(f); });
  const undoSend = el("button", { type: "button", className: "btn", id: "cee-pt-undo", textContent: "Senden zurücknehmen", disabled: true });
  const connectEmu = el("button", { type: "button", className: "btn", id: "cee-pt-connect-emu", textContent: "Mit Emulator verbinden" });
  connectEmu.addEventListener("click", () => device.connectEmulator());
  const source = el("section", { className: "ui-section" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Quelle" })]),
    el("p", { className: "muted", textContent: "Die Patterns für beide Werkzeuge kommen aus einer Pattern-Sicherung, einer einzelnen Pattern-Datei oder dem Pattern-Puffer des verbundenen Geräts. Die Datei wird nur gelesen, nie verändert, und bleibt auf deinem Rechner. Das Gerät verbindest du im Bereich Emulator unter „Echtes Gerät“, den Emulator (wenn er läuft) hier." }),
    el("label", { className: "ui-dropzone" }, [
      input,
      el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "Pattern-Sicherung hierher ziehen oder " }), "auswählen"]),
      el("span", { className: "ui-dropzone-hint", textContent: ".e2sallpat mit allen Patterns oder .e2spat mit einem" }),
      el("span", { className: "ui-dropzone-files" }),
    ]),
    loaded,
    el("div", { className: "actions cee-pt-device-row" }, [connectEmu, undoSend]),
    line,
  ]);

  async function load(file) {
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const single = bytes.length === 0x100 + 0x4000;
      const parsed = single ? parseSinglePattern(bytes) : PatternFile.parse(bytes);
      pool.fileName = file.name;
      pool.file = single ? null : parsed;
      pool.single = single ? parsed : null;
      pool.free = new Set();
      if (pool.file) for (let n = 1; n <= pool.file.count; n++) if (isFree(pool.file.pattern(n))) pool.free.add(n);
      loaded.textContent = `${file.name}, ${single ? "ein Pattern" : `${pool.file.count} Patterns, ${pool.free.size} davon frei`}`;
      for (const p of pickers) p.fill({ reset: true });
      transitions.sourceChanged();
      dice.roll();
    } catch (e) {
      const message = e instanceof FileError ? e.message : `Die Datei ließ sich nicht lesen: ${e.message}`;
      if (window.ui?.rejectFile) window.ui.rejectFile(input, message); else toast(message, "error");
    }
  }

  /** A pattern chosen in a picker: its bytes as a Pattern, where it sits in the backup (or null), and a label. */
  function resolve(value) {
    if (value === "single" && pool.single) return { pattern: new Pattern(pool.single.bytes), number: null, label: pool.fileName };
    if (value.startsWith("copy:")) {
      const copy = pool.copies.find(c => c.id === value);
      return copy ? { pattern: new Pattern(copy.bytes), number: null, label: copy.label } : null;
    }
    const n = Number(value);
    return pool.file && n >= 1 && n <= pool.file.count ? { pattern: pool.file.pattern(n), number: n, label: `${n} ${pool.file.name(n) || "ohne Namen"}` } : null;
  }

  function picker(id, label, which, onPick) {
    const select = el("select", { className: "select", id });
    const fetch = el("button", { type: "button", className: "btn", id: `${id}-fetch`, textContent: "Vom Gerät holen", disabled: true });
    function fill({ reset = false } = {}) {
      const keep = reset ? null : select.value;
      select.replaceChildren();
      if (pool.single) select.append(el("option", { value: "single", textContent: `Datei: ${pool.single.name || "ohne Namen"}` }));
      if (pool.file) for (let n = 1; n <= pool.file.count; n++) select.append(el("option", { value: String(n), textContent: `${n}  ${pool.file.name(n) || "ohne Namen"}${pool.free.has(n) ? " (frei)" : ""}` }));
      for (const c of pool.copies) select.append(el("option", { value: c.id, textContent: c.label }));
      select.disabled = !select.options.length;
      if (select.disabled) select.append(el("option", { value: "", textContent: "Erst eine Datei laden oder vom Gerät holen" }));
      if (keep && [...select.options].some(o => o.value === keep)) select.value = keep;
      else if (pool.file) select.value = String(firstWithContent(which));
    }
    fetch.addEventListener("click", async () => {
      const copy = await fetchFromDevice();
      if (!copy) return;
      fill({});
      select.value = copy.id;
      for (const p of pickers) if (p.select !== select) p.fill({});
      onPick();
    });
    select.addEventListener("change", onPick);
    const node = field(id, label, select);
    node.append(fetch);
    const p = { select, fill, fetch, node };
    pickers.push(p);
    return p;
  }

  /** The first and second pattern with content: where the pickers start on a backup. */
  function firstWithContent(which) {
    const used = [...Array(pool.file.count)].map((_, i) => i + 1).filter(n => !pool.free.has(n));
    return used[which] ?? used[0] ?? Math.min(which + 1, pool.file.count);
  }

  async function fetchFromDevice() {
    const s = device.session;
    if (!s) { say("Nichts verbunden. Schalte im Bereich Emulator die Electribe ein, oder steck dein Gerät per USB an und wähl dort oben „Echtes Gerät“.", "error"); return null; }
    const release = s.reserve();
    try {
      await s.idle();
      const bytes = Uint8Array.from(await s.fetchPattern());
      const name = new Pattern(bytes).name || "ohne Namen";
      pool.copyCount++;
      const copy = { id: `copy:${pool.copyCount}`, bytes, label: `Gerät, Kopie ${pool.copyCount}: ${name}` };
      pool.copies.push(copy);
      if (pool.copies.length > MAX_DEVICE_COPIES) pool.copies.shift();
      say(`Geholt: "${name}" aus dem Pattern-Puffer des Geräts.`, "ok");
      return copy;
    } catch (e) {
      say(`Das Pattern ließ sich nicht holen. Ist die Electribe noch verbunden? (${e.message})`, "error");
      return null;
    } finally {
      release();
    }
  }

  /** Fetching and sending use the device's own gate and confirmation; the same flow as the other pattern transport. */
  async function sendToDevice(pattern, label) {
    const s = device.session;
    if (!s) return;
    const release = s.reserve();
    try {
      await s.idle();
      let active = "unbekannt";
      try { active = new Pattern(await s.fetchPattern()).name || "ohne Namen"; } catch (e) {
        say(`Die App konnte das aktuelle Pattern am Gerät nicht sichern, deshalb sendet sie nichts. Verbinde die Electribe neu und versuch es nochmal. (${e.message})`, "error");
        return;
      }
      const edit = { kind: "patternSend", block: Uint8Array.from(pattern.bytes) };
      const checked = await s.check(edit);
      if (checked.verdict === "blocked") { say(`Gesperrt: ${checked.reasons.map(r => r.message).join(" ")}`, "error"); return; }
      const warnings = checked.reasons.map(r => `Warnung: ${r.message}`).join("\n");
      const yes = await window.ui.confirm({
        title: `"${label}" ans Gerät senden?`,
        text: `Am Gerät ist gerade "${active}" im Puffer. Er wird vorher gesichert und lässt sich zurückholen. Dauerhaft wird das gesendete Pattern erst mit Write am Gerät, auf dem Platz, den du dort wählst.${warnings ? `\n\n${warnings}` : ""}`,
        confirmLabel: "Senden",
      });
      if (!yes) return;
      say("Sende …", "progress");
      const res = await s.apply(edit, { confirmed: checked.token });
      if (res.ok) say(`Gesendet und zurückgelesen: "${label}". Vorher im Puffer: "${active}", mit "Senden zurücknehmen" zurückzuholen.`, "ok");
      else if (res.needsConfirmation) say("Am Gerät hat sich inzwischen etwas geändert. Klick bitte nochmal auf Senden.", "error");
      else if (res.gate?.verdict === "blocked") say(`Gesperrt: ${res.gate.reasons.map(r => r.message).join(" ")}`, "error");
      else say(`${res.error?.message ?? "Abgebrochen."}${res.pending?.now ? ` ${res.pending.now.text}` : ""}${s.blocked ? " Entscheide im Bereich Emulator unter „Echtes Gerät“, wie es weitergeht." : ""}`, "error");
      device.log?.(res.ok ? "Pattern gesendet." : `Pattern: ${res.error?.message ?? "gesperrt"}`, res.ok ? "ok" : "error");
      if (s.blocked) device.showDecision?.();
    } catch (e) {
      say(`Abgebrochen: ${e.message}`, "error");
    } finally {
      release();
      sessionChanged();
    }
  }

  undoSend.addEventListener("click", async () => {
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
      sessionChanged();
    }
  });

  /** Put patterns into a copy of the loaded backup and offer it as a download; occupied slots ask first. */
  async function intoBackup(items, { chainA = null } = {}) {
    if (!pool.file) return;
    const taken = items.filter(it => !pool.free.has(it.slot));
    if (taken.length) {
      const list = taken.map(it => `${it.slot} ${pool.file.name(it.slot) || "ohne Namen"}`).join(", ");
      const yes = await window.ui.confirm({
        title: "Belegte Plätze überschreiben?",
        text: `In der neuen Sicherung ersetzen die Patterns diese Plätze: ${list}. Die geladene Datei bleibt unverändert, die neue Sicherung ist eine Kopie.`,
        confirmLabel: "In Kopie einsetzen", danger: true,
      });
      if (!yes) return;
    }
    const all = new PatternFile(pool.file.header.slice(), pool.file.blocks.map(b => b.slice()));
    for (const it of items) all.replace(it.slot, it.pattern);
    if (chainA) all.replace(chainA.number, chainA.pattern);
    const name = `${fileStem(pool.fileName)}-neu.e2sallpat`;
    saveFile(all.toBytes(), name);
    say(`Gespeichert: ${name}, Plätze ${items.map(i => i.slot).join(", ")}${chainA ? `, Chain To von ${chainA.number} auf ${items[0].slot}` : ""}. Die Datei gehört auf die Karte (IMPORT ALL PATTERN) und ersetzt dort alle Patterns.`, "ok");
  }

  const saveSingle = (pattern, name) => { saveFile(toSinglePattern(pattern), name); say(`Gespeichert: ${name}.`, "ok"); };

  /** Findings as a list; true when one of them stops the output. */
  function findingsList(findings) {
    const list = el("ul", { className: "ui-list cee-pt-findings" });
    for (const f of findings) list.append(el("li", { className: "ui-row" }, [pill(f.severity === "error" ? "error" : "warn", f.severity === "error" ? "Fehler" : "Warnung"), el("span", { textContent: ` ${f.message}` })]));
    return list;
  }

  // ---- Übergänge ----
  const transitions = (() => {
    const T = {
      count: 2, direction: "auto", tempo: "ease", pad: "hold", sweep: "tail", valley: "auto", accent: "auto", arrive: "pulse",
      thin: false, insertMotion: false, chain: true, chainA: false, slots: [], slotsTouched: false, slotB: "", names: [],
    };
    const results = el("div", { className: "cee-pt-results", id: "cee-pt-t-results" });
    const pickA = picker("cee-pt-a", "A, der Anfang", 0, () => sourceChanged());
    const pickB = picker("cee-pt-b", "B, das Ziel", 1, () => sourceChanged());
    const opt = (id, label, options, key) => selectField(id, label, options, T[key], v => { T[key] = v; recompute(); });
    const fields = [
      numberField("cee-pt-count", "Zahl der Übergänge", { min: 1, max: 8, value: T.count, onChange: v => { T.count = Number(v) || 0; T.slotsTouched = false; T.names = []; recompute(); } }),
      opt("cee-pt-direction", "Richtung", [["auto", "automatisch"], ["blend", "überblenden"], ["down", "ausdünnen (A geht)"], ["up", "aufbauen (B kommt)"]], "direction"),
      opt("cee-pt-tempo", "Tempo", [["ease", "sanft, in der Mitte"], ["ramp", "gerade Linie"], ["keep", "Tempo von A behalten"]], "tempo"),
      opt("cee-pt-pad", "Master-FX-Pad", [["hold", "Hold an, im letzten aus"], ["release", "Hold, Pad läuft am Ende in die Ecke"], ["corner", "Pad läuft über alle Übergänge in die Ecke"], ["none", "nichts am Pad"]], "pad"),
      opt("cee-pt-sweep", "Filter", [["tail", "ein Bogen im letzten Übergang"], ["run", "eine Fahrt über alle Übergänge"], ["none", "kein Filter"]], "sweep"),
      opt("cee-pt-valley", "Tal in der Mitte", [["auto", "ja, wenige Parts und Steps"], ["none", "nein"]], "valley"),
      opt("cee-pt-accent", "Akzent", [["auto", "ein stummer Part von A als Akzent"], ["none", "keiner"]], "accent"),
      opt("cee-pt-arrive", "Parts von B", [["pulse", "Gegenschläge warten auf B"], ["all", "alle kommen früh"]], "arrive"),
    ];
    const switches = [
      switchField("cee-pt-thin", "Parts vor dem Abgang ausdünnen", T.thin, v => { T.thin = v; recompute(); }),
      switchField("cee-pt-insert-motion", "Insert-Effekt des tragenden Parts per Motion einschalten", T.insertMotion, v => { T.insertMotion = v; recompute(); }),
      switchField("cee-pt-chain", "Chain To setzen: jeder Übergang auf den nächsten, der letzte auf B", T.chain, v => { T.chain = v; recompute(); }),
      switchField("cee-pt-chain-a", "A auf den ersten Übergang zeigen lassen (nur in der neuen Sicherung)", T.chainA, v => { T.chainA = v; recompute(); }),
    ];
    const slotB = numberField("cee-pt-slot-b", "Platz von B", { min: 1, max: SLOTS, value: "", help: "Chain To des letzten Übergangs zeigt hierhin.", onChange: v => { T.slotB = v; recompute(); } });

    const node = el("section", { className: "ui-section" }, [
      el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Übergänge" })]),
      el("p", { className: "muted", textContent: "Aus zwei Patterns entstehen Übergangs-Patterns im Stil der eigenen Ketten: Parts von A gehen in Gruppen, Parts von B kommen, in der Mitte ein Tal, am Ende ein Filterbogen. Jeder Übergang ist eine Bearbeitung einer Kopie von A. Am Gerät ist das noch nicht gehört." }),
      el("div", { className: "cee-grid" }, [pickA.node, pickB.node]),
      el("div", { className: "cee-grid" }, [...fields.map(f => f.node), slotB.node]),
      el("div", { className: "cee-grid" }, switches.map(f => f.node)),
      results,
    ]);

    let current = null;

    function sourceChanged() {
      T.slotsTouched = false;
      T.names = [];
      const b = resolve(pickB.select.value);
      T.slotB = b?.number ? String(b.number) : "";
      slotB.input.value = T.slotB;
      recompute();
    }

    function slotsOk(a, b, slots) {
      const limit = pool.file ? pool.file.count : SLOTS;
      if (slots.length !== T.count || slots.some(s => !Number.isInteger(s) || s < 1 || s > limit)) return `Die Plätze müssen ganze Zahlen von 1 bis ${limit} sein.`;
      if (new Set(slots).size !== slots.length) return "Zwei Übergänge haben denselben Platz.";
      if (slots.some(s => s === a.number || s === b.number)) return "Ein Übergang liegt auf dem Platz von A oder B.";
      return null;
    }

    function recompute() {
      results.replaceChildren();
      current = null;
      const a = resolve(pickA.select.value), b = resolve(pickB.select.value);
      if (!a || !b) { results.append(el("p", { className: "muted", textContent: "Wähle A und B." })); return; }
      if (!Number.isInteger(T.count) || T.count < 1 || T.count > 8) { results.append(el("p", { className: "cee-error", textContent: "Die Zahl der Übergänge liegt zwischen 1 und 8." })); return; }
      if (!T.slotsTouched || T.slots.length !== T.count) {
        T.slots = pool.file && a.number ? pickSlots(pool.file, T.count, a.number, [a.number, b.number].filter(Boolean)) : [];
        T.slots = T.slots.length === T.count ? T.slots : [];
      }
      const slotProblem = T.slots.length ? slotsOk(a, b, T.slots) : null;
      const useSlots = T.slots.length === T.count && !slotProblem;
      let result;
      try {
        result = makeTransitions(a.pattern, b.pattern, {
          count: T.count, direction: T.direction, tempo: T.tempo, pad: T.pad, sweep: T.sweep,
          valley: T.valley === "none" ? "none" : undefined, accent: T.accent === "none" ? "none" : undefined, arrive: T.arrive,
          thinBefore: T.thin ? 0.6 : null, insertMotion: T.insertMotion,
          slots: useSlots ? T.slots : null, slotB: Number(T.slotB) || undefined, chain: T.chain && useSlots, names: T.names,
        });
      } catch (e) {
        results.append(el("p", { className: "cee-error", textContent: e.message }));
        return;
      }
      result.items.forEach((it, k) => { it.slot = useSlots ? T.slots[k] : null; });
      const sa = summarize(a.pattern), sb = summarize(b.pattern);
      const items = result.items.map(it => ({ ...it, findings: checkTransition(it.pattern, a.pattern) }));
      current = { a, b, items, result };
      render(a, b, sa, sb, items, result, slotProblem);
    }

    function render(a, b, sa, sb, items, result, slotProblem) {
      const blocked = items.some(it => it.findings.some(f => f.severity === "error"));
      const text = describe({ ...result, items }, sa, sb, a.pattern, b.pattern, a.number, b.number);
      const head = el("p", { id: "cee-pt-t-summary", textContent: text.split("\n")[0] });
      const fx = result.arrivalFx.length ? `Beim Wechsel nach B ändern sich ${result.arrivalFx.length} Effekt-Slots (${result.arrivalFx.join(", ")}): hergeleitet, am Gerät nicht gemessen, eine kurze Lücke im Ton, einmal in der ganzen Kette.` : "Beim Wechsel nach B ändert sich kein Effekt.";
      const detail = el("details", { className: "ui-details", id: "cee-pt-t-detail" }, [el("summary", { textContent: "Ausführliche Übersicht" }), el("div", { className: "ui-details-body" }, [el("pre", { className: "cee-pt-text", textContent: text })])]);
      const cards = items.map((it, k) => {
        const name = textField(`cee-pt-t-name-${k}`, "Name", { value: it.name, onChange: v => { T.names[k] = v; recompute(); }, help: `Bis zu ${NAME_LENGTH} Zeichen, die das Display zeigen kann.` });
        const slot = numberField(`cee-pt-t-slot-${k}`, "Platz", { min: 1, max: SLOTS, value: T.slots[k] || "", onChange: () => {} });
        slot.input.classList.add("cee-pt-slot");
        slot.input.addEventListener("change", () => {
          T.slotsTouched = true;
          T.slots = [...results.querySelectorAll(".cee-pt-slot")].map(i => Number(i.value));
          recompute();
        });
        const stop = it.findings.some(f => f.severity === "error");
        const save = el("button", { type: "button", className: "btn", id: `cee-pt-t-save-${k}`, textContent: ".e2spat speichern", disabled: stop });
        save.addEventListener("click", () => saveSingle(it.pattern, `T${it.index}${it.slot ? `_${String(it.slot).padStart(3, "0")}` : ""}_${safe(it.name)}.e2spat`));
        const send = el("button", { type: "button", className: "btn", id: `cee-pt-t-send-${k}`, textContent: "An Gerät senden", disabled: stop || !device.session });
        send.addEventListener("click", () => sendToDevice(it.pattern, it.name));
        return el("li", { className: "cee-pt-card" }, [
          el("h3", { textContent: `Übergang ${it.index}` }),
          el("div", { className: "cee-grid" }, [name.node, slot.node]),
          el("ul", { className: "cee-pt-notes" }, it.notes.map(n => el("li", { textContent: n }))),
          it.findings.length ? findingsList(it.findings) : null,
          el("div", { className: "actions" }, [save, send]),
        ]);
      });
      const intoFile = el("button", { type: "button", className: "btn cee-primary", id: "cee-pt-t-backup", textContent: "In Sicherung einsetzen und speichern", disabled: blocked || !pool.file || items.some(it => !it.slot) });
      intoFile.addEventListener("click", () => {
        let chainA = null;
        if (T.chainA && a.number) {
          const p = new Pattern(a.pattern.bytes);
          p.setRaw("pattern.chainTo", [], items[0].slot);
          p.setRaw("pattern.chainRepeat", [], 0);
          chainA = { number: a.number, pattern: p };
        }
        intoBackup(items, { chainA });
      });
      const why = !pool.file ? "Dafür eine Pattern-Sicherung laden." : items.some(it => !it.slot) ? "Dafür Plätze vergeben." : "";
      results.replaceChildren(...[
        head,
        slotProblem ? el("p", { className: "cee-hint", id: "cee-pt-t-slots", textContent: slotProblem }) : null,
        partGrid([{ label: "A", pattern: a.pattern }, ...items.map(it => ({ label: `Übergang ${it.index}`, pattern: it.pattern })), { label: "B", pattern: b.pattern }]),
        el("p", { className: "muted", textContent: fx }),
        detail,
        el("ol", { className: "cee-pt-cards" }, cards),
        el("div", { className: "actions" }, [intoFile, why ? el("span", { className: "muted", textContent: why }) : null]),
      ].filter(Boolean));
      if (blocked) results.prepend(el("p", { className: "cee-error", textContent: "Ein Befund sperrt die Ausgabe. Siehe bei den Übergängen." }));
    }

    return { node, sourceChanged, recompute };
  })();

  /** Audible steps per part, one row per pattern; a muted part with steps shows its count in brackets. */
  function partGrid(rows) {
    const table = el("table", { className: "cee-pt-grid" });
    table.append(el("caption", { textContent: "Steps je Part. In Klammern: Part ist gemutet." }));
    table.append(el("thead", {}, [el("tr", {}, [el("th", { scope: "col", textContent: "Pattern" }), ...Array.from({ length: 16 }, (_, i) => el("th", { scope: "col", textContent: String(i + 1) }))])]));
    table.append(el("tbody", {}, rows.map(r => {
      const s = summarize(r.pattern);
      return el("tr", {}, [el("th", { scope: "row", textContent: r.label }), ...s.parts.map(x => {
        const shown = x.on.length && x.sample !== NO_SAMPLE;
        return el("td", { textContent: shown ? (x.audible ? String(x.on.length) : `(${x.on.length})`) : "", className: x.audible ? "cee-pt-on" : "" });
      })]);
    })));
    return el("div", { className: "cee-pt-scroll" }, table);
  }

  // ---- Würfeln ----
  const dice = (() => {
    const D = { ...DEFAULTS, seed: randomSeed(), name: "", swingOn: false, swingValue: 0 };
    let rolled = null;
    const doc = {
      get: (id, ix = []) => rolled.pattern.raw(id, ix),
      set: (id, ix, raw) => { rolled.pattern.setRaw(id, ix, raw); showFindings(); },
      group: fn => fn(),
    };
    const steps = stepEditor(doc);
    const base = picker("cee-pt-dice-base", "Basis-Pattern", 0, () => roll());
    const status = el("p", { id: "cee-pt-d-text", role: "status" });
    const warn = el("ul", { className: "cee-pt-notes", id: "cee-pt-d-warnings" });
    const findings = el("div", { id: "cee-pt-d-findings" });
    const slot = numberField("cee-pt-d-slot", "Platz in der Sicherung", { min: 1, max: SLOTS, value: "", onChange: () => syncButtons() });
    const save = el("button", { type: "button", className: "btn", id: "cee-pt-d-save", textContent: ".e2spat speichern" });
    const send = el("button", { type: "button", className: "btn", id: "cee-pt-d-send", textContent: "An Gerät senden", disabled: true });
    const intoFile = el("button", { type: "button", className: "btn cee-primary", id: "cee-pt-d-backup", textContent: "In Sicherung einsetzen und speichern" });
    const hint = el("span", { className: "muted", id: "cee-pt-d-hint" });

    const seed = numberField("cee-pt-seed", "Seed", { min: 0, max: 4294967295, value: D.seed, onChange: v => { D.seed = Number(v); roll(); } });
    const again = el("button", { type: "button", className: "btn", id: "cee-pt-reroll", textContent: "Neu würfeln" });
    again.addEventListener("click", () => { D.seed = randomSeed(); seed.input.value = String(D.seed); roll(); });
    const nameField = textField("cee-pt-d-name", "Name des Patterns", { placeholder: "automatisch", help: "Leer: der Name des Basis-Patterns bleibt.", onChange: v => { D.name = v; roll(); } });
    const kind = selectField("cee-pt-kind", "Art", [["drums", "Drums: eine Note, starke Zählzeiten zuerst"], ["melody", "Melodie: Noten aus der Tonleiter"]], D.kind, v => { D.kind = v; syncKind(); roll(); });
    const part = selectField("cee-pt-part", "Part", Array.from({ length: 16 }, (_, i) => [i, `Part ${i + 1}`]), D.part, v => { D.part = Number(v); roll(); });
    const density = rangeField("cee-pt-density", "Dichte", { min: 0, max: 100, value: D.density * 100, show: v => `${v} %`, onChange: v => { D.density = v / 100; roll(); } });
    const scale = selectField("cee-pt-scale", "Tonleiter", SCALES.map(s => [s.name, s.name]), D.scale, v => { D.scale = v; roll(); });
    const rootF = selectField("cee-pt-root", "Grundton", ROOTS.map((r, i) => [i, r]), D.root, v => { D.root = Number(v); roll(); });
    const octave = selectField("cee-pt-octave", "tiefste Oktave", [1, 2, 3, 4, 5, 6].map(o => [o, `C${o}`]), D.octave, v => { D.octave = Number(v); roll(); });
    const span = selectField("cee-pt-span", "Umfang", [[1, "1 Oktave"], [2, "2 Oktaven"], [3, "3 Oktaven"]], D.span, v => { D.span = Number(v); roll(); });
    const gate = rangeField("cee-pt-gate", "Gate-Länge", { min: 0, max: 100, value: D.gate * 100, show: v => `${v} %`, onChange: v => { D.gate = v / 100; roll(); } });
    const accent = rangeField("cee-pt-accent", "Velocity-Spielraum", { min: 0, max: 100, value: D.accent * 100, show: v => `${v} %`, onChange: v => { D.accent = v / 100; roll(); } });
    const bars = selectField("cee-pt-bars", "Länge", [["", "wie das Pattern"], [1, "1 Takt"], [2, "2 Takte"], [3, "3 Takte"], [4, "4 Takte"]], "", v => { D.bars = v === "" ? null : Number(v); roll(); });
    const swingOn = switchField("cee-pt-swing-on", "Swing setzen", D.swingOn, v => { D.swingOn = v; swing.input.disabled = !v; roll(); });
    const swing = numberField("cee-pt-swing", "Swing", { min: -48, max: 48, value: 0, onChange: v => { D.swingValue = Number(v); roll(); } });
    swing.input.disabled = true;
    const unmute = switchField("cee-pt-unmute", "Gemuteten Part einschalten", D.unmute, v => { D.unmute = v; roll(); });
    const writeScale = switchField("cee-pt-write-scale", "Tonart und Tonleiter ins Pattern schreiben (Melodie)", D.writeScale, v => { D.writeScale = v; roll(); });
    const melodyOnly = [scale, rootF, octave, span, writeScale];
    function syncKind() { for (const f of melodyOnly) { f.node.hidden = D.kind !== "melody"; } }
    syncKind();

    const node = el("section", { className: "ui-section" }, [
      el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Würfeln" })]),
      el("p", { className: "muted", textContent: "Würfelt die Steps eines Parts in eine Kopie des Basis-Patterns: Noten, Velocity und Gate aus wenigen Reglern. Derselbe Seed mit denselben Reglern gibt dasselbe Ergebnis. Der Part braucht ein Sample im Basis-Pattern, sonst klingt er nicht." }),
      el("div", { className: "cee-grid" }, [base.node, part.node, kind.node, density.node, seed.node, el("div", { className: "ui-field" }, [again])]),
      el("div", { className: "cee-grid" }, [scale.node, rootF.node, octave.node, span.node, gate.node, accent.node, bars.node, swing.node]),
      el("div", { className: "cee-grid" }, [swingOn.node, unmute.node, writeScale.node]),
      status, warn,
      steps.node,
      el("p", { className: "muted", textContent: "Ändern im Step-Raster gilt für dieses Ergebnis, bis du Regler bewegst oder neu würfelst." }),
      findings,
      el("div", { className: "cee-grid" }, [nameField.node, slot.node]),
      el("div", { className: "actions" }, [intoFile, save, send, hint]),
    ]);

    function options() {
      return { part: D.part, kind: D.kind, density: D.density, seed: D.seed, root: D.root, scale: D.scale, octave: D.octave, span: D.span, gate: D.gate, accent: D.accent, swing: D.swingOn ? D.swingValue : null, bars: D.bars, unmute: D.unmute, writeScale: D.writeScale, name: D.name.trim() ? D.name : `DICE ${D.seed}` };
    }

    function roll() {
      const from = resolve(base.select.value);
      rolled = null;
      warn.replaceChildren();
      findings.replaceChildren();
      if (!from) { status.textContent = "Wähle ein Basis-Pattern."; steps.node.hidden = true; syncButtons(); return; }
      try {
        const r = rollPart(from.pattern, options());
        rolled = { ...r, from };
      } catch (e) {
        status.textContent = e.message;
        steps.node.hidden = true;
        syncButtons();
        return;
      }
      status.textContent = `${rolled.text} Name: ${rolled.pattern.name}.`;
      warn.replaceChildren(...rolled.warnings.map(w => el("li", { textContent: w })));
      steps.node.hidden = false;
      steps.show(D.part);
      if (pool.file && !slot.input.dataset.touched) {
        const free = pickSlots(pool.file, 1, from.number ?? 0, []);
        slot.input.value = String(free[0] ?? from.number ?? 1);
      }
      showFindings();
    }

    function showFindings() {
      if (!rolled) return;
      findings.replaceChildren(...(checkRoll(rolled.pattern).length ? [findingsList(checkRoll(rolled.pattern))] : []));
      syncButtons();
    }

    function syncButtons() {
      const stop = !rolled || checkRoll(rolled.pattern).some(f => f.severity === "error");
      save.disabled = stop;
      send.disabled = stop || !device.session;
      const n = Number(slot.input.value);
      const limit = pool.file?.count ?? 0;
      const okSlot = Number.isInteger(n) && n >= 1 && n <= limit;
      intoFile.disabled = stop || !pool.file || !okSlot;
      hint.textContent = !pool.file ? "Für die Sicherung eine Datei laden." : !okSlot ? `Platz von 1 bis ${limit}.` : pool.free.has(n) ? "Der Platz ist frei." : "Der Platz ist belegt und wird in der Kopie ersetzt.";
    }

    slot.input.addEventListener("input", () => { slot.input.dataset.touched = "1"; });
    save.addEventListener("click", () => saveSingle(rolled.pattern, `${safe(rolled.pattern.name)}.e2spat`));
    send.addEventListener("click", () => sendToDevice(rolled.pattern, rolled.pattern.name));
    intoFile.addEventListener("click", () => intoBackup([{ slot: Number(slot.input.value), pattern: rolled.pattern }]));
    return { node, roll, syncButtons };
  })();

  // ---- Zusammenbau ----
  const intro = el("p", { className: "cee-pt-intro", textContent: "Zwei Werkzeuge für Patterns: Übergänge zwischen zwei Patterns erzeugen und einen Part würfeln. Beide schreiben nie in die geladene Datei. Was herauskommt, geht als Datei, als Kopie der Sicherung oder durch Linter, Türsteher und deine Bestätigung ans Gerät." });
  root.replaceChildren(intro, source, transitions.node, dice.node);
  for (const p of pickers) p.fill({ reset: true });
  transitions.recompute();
  dice.roll();

  function sessionChanged() {
    const s = device.session;
    for (const p of pickers) p.fetch.disabled = !s;
    undoSend.disabled = !s || !s.history.some(h => h.pattern);
    dice.syncButtons();
    transitions.recompute();
  }

  return { sessionChanged };
}
