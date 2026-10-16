/**
 * The levels of the pattern in the device's buffer side by side (play level,
 * part levels, output levels of the insert presets in use), scaled together
 * with a preview and sent over the normal pattern send path. The insert levels
 * are shown, not scaled: a preset can serve several parts and patterns, and
 * changing it is the effect editor's job.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { Pattern } from "../../src/pattern.mjs";
import { FxRecord } from "../../src/record.mjs";
import { profileKey } from "../../src/profile.mjs";
import { readLevels, planScale, applyScale, outputLevels, judgeOutput, LEVEL_MAX } from "../../src/gain.mjs";

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const number = n => String(Math.round(n * 100) / 100).replace(".", ",");

/**
 * @param {HTMLElement} root
 * @param {object} opts
 * @param {() => Promise<object | null>} opts.session the session to read the buffer from and send to: the attached device, else the running emulator
 * @param {() => {list: (kind: string) => {slot: number, name: string, record: object}[], units: object, profile: object | null} | null} opts.presets the presets of the loaded firmware, null before one is loaded
 * @param {(slot: number) => void} opts.openPreset show an insert preset in the effect editor
 * @param {{log?: Function, showDecision?: Function}} [opts.device]
 */
export function levelsPanel(root, { session, presets, openPreset, device = {} }) {
  const state = { block: null, name: "", mode: "factor", value: "1", master: false, sendable: false };

  const fetchButton = el("button", { type: "button", className: "btn", id: "cee-lv-fetch", textContent: "Pattern aus dem Puffer holen" });
  const sendButton = el("button", { type: "button", className: "btn primary", id: "cee-lv-send", textContent: "Skalierung senden", disabled: true });
  const undoButton = el("button", { type: "button", className: "btn", id: "cee-lv-undo", textContent: "Senden zurücknehmen", disabled: true });
  const body = el("div", { className: "cee-levels", id: "cee-lv-body", hidden: true });
  const say = text => {
    toast(text, /fehlgeschlagen|Gesperrt|Abgebrochen|nicht lesen|Weder|Befund|Entscheiden/.test(text) ? "error" : /^(Geholt|Gesendet|Der vorherige)/.test(text) ? "ok" : "info");
  };
  const attached = async () => {
    try {
      const s = await session();
      if (!s) say("Weder Emulator noch Gerät verbunden. Schalte den Emulator ein oder verbinde das Gerät.");
      return s;
    } catch (e) { say(e.message); return null; }
  };

  const modes = el("div", { className: "ui-segmented" });
  modes.setAttribute("role", "radiogroup");
  modes.setAttribute("aria-label", "Skalieren");
  const modeInputs = [["factor", "Faktor"], ["target", "Zielwert für den lautesten Part"]].map(([value, text]) => {
    const input = el("input", { type: "radio", name: "cee-lv-mode", value, checked: value === state.mode });
    input.addEventListener("change", () => {
      if (!input.checked) return;
      state.mode = value;
      state.value = value === "factor" ? "1" : String(readLevels(pattern()).parts.reduce((m, p) => Math.max(m, p.value), 0));
      valueInput.value = state.value;
      draw();
    });
    modes.append(el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: text })]));
    return input;
  });
  const valueInput = el("input", { type: "number", className: "input", id: "cee-lv-value", min: "0", step: "0.05", value: state.value });
  const valueLabel = el("label", { className: "ui-field-label", htmlFor: "cee-lv-value", textContent: "Faktor" });
  valueInput.addEventListener("input", () => { state.value = valueInput.value; draw(); });
  const masterToggle = el("input", { type: "checkbox", id: "cee-lv-master" });
  masterToggle.setAttribute("role", "switch");
  masterToggle.addEventListener("change", () => { state.master = masterToggle.checked; draw(); });

  const summary = el("p", { id: "cee-lv-summary", ariaLive: "polite" });
  const rows = el("div", { className: "cee-level-rows", id: "cee-lv-rows" });
  const fxRows = el("div", { className: "cee-group", id: "cee-lv-fx" });
  const controls = el("div", { className: "cee-levels-controls" }, [
    el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: "Art" }), modes]),
    el("div", { className: "ui-field" }, [valueLabel, valueInput]),
    el("label", { className: "ui-switch" }, [masterToggle, el("span", { className: "ui-switch-track", ariaHidden: "true" }), "Pattern-Lautstärke mitskalieren"]),
  ]);
  body.append(controls, summary, rows, fxRows, el("div", { className: "actions" }, [sendButton, undoButton]));

  const pattern = () => new Pattern(state.block);
  const plan = () => planScale(readLevels(pattern()), { mode: state.mode, value: Number(String(state.value).replace(",", ".")), master: state.master });

  function meter(node, value, label) {
    node.className = "ui-meter";
    node.dataset.size = "sm";
    window.ui?.setMeter?.(node, (value / LEVEL_MAX) * 100, { label, valueText: String(value) });
  }

  function draw() {
    valueLabel.textContent = state.mode === "factor" ? "Faktor" : "Zielwert";
    valueInput.step = state.mode === "factor" ? "0.05" : "1";
    const p = plan();
    rows.replaceChildren();
    const levels = readLevels(pattern());
    const shown = p.error ? [levels.master, ...levels.parts].map(l => ({ ...l, before: l.value, after: l.value, delta: 0 })) : p.rows;
    const all = new Map(shown.map(r => [r.id + r.indices, r]));
    for (const l of [levels.master, ...levels.parts]) {
      const r = all.get(l.id + l.indices) ?? { before: l.value, after: l.value, delta: 0 };
      const bar = el("span", { className: "cee-level-bar" });
      meter(bar, r.after, l.label);
      const text = r.delta === 0 ? String(r.before) : `${r.before} zu ${r.after}`;
      const row = el("div", { className: "cee-level-row", id: `cee-lv-row-${l.part ?? "pattern"}` }, [
        el("span", { className: "cee-level-name", textContent: l.id === "pattern.playLevel" ? "Pattern-Lautstärke" : l.label }),
        bar,
        el("span", { className: "cee-level-value", textContent: text }),
        l.muted ? pill("neutral", "stumm") : null,
      ]);
      row.dataset.changed = String(r.delta !== 0);
      rows.append(row);
    }
    if (p.error) {
      summary.textContent = p.error;
      summary.className = "cee-hint";
    } else {
      summary.className = "";
      const changed = p.rows.filter(r => r.delta !== 0).length;
      summary.textContent = p.changed
        ? `Faktor ${number(p.factor)}: der lauteste Pegel geht von ${p.peakBefore} auf ${p.peakAfter}, ${changed} ${changed === 1 ? "Pegel ändert" : "Pegel ändern"} sich.${p.limited ? ` Der gewünschte Faktor ${number(p.requested)} ließe den lautesten über ${LEVEL_MAX} steigen und wurde auf ${number(p.factor)} begrenzt, damit das Verhältnis bleibt.` : ""}`
        : "Nichts ändert sich.";
    }
    sendButton.disabled = !!p.error || !p.changed || !state.sendable;
  }

  function drawFx(found) {
    fxRows.replaceChildren(el("h3", { textContent: "Insert-Effekte der Parts" }));
    if (!found) {
      fxRows.append(el("p", { className: "muted", textContent: "Für die Pegel der Insert-Presets fehlt die Firmware: wähle sie im Bereich Emulator." }));
      return;
    }
    if (!found.length) {
      fxRows.append(el("p", { className: "muted", textContent: "Kein Part benutzt einen Insert-Effekt." }));
      return;
    }
    const list = el("ul", { className: "ui-list" });
    for (const f of found) {
      const text = f.levels.length
        ? f.levels.map(l => `${l.param} ${l.value}`).join(", ")
        : f.missing ? "Preset nicht gefunden" : "kein Ausgangspegel";
      const verdicts = f.levels.map(l => judgeOutput(l.device, l.param, l.value, f.profile?.params[profileKey("ifx", l.device, l.param)])).filter(Boolean);
      const open = el("button", { type: "button", className: "btn sm", textContent: "Im Editor öffnen" });
      open.setAttribute("aria-label", `IFX ${f.slot} im Effekt-Editor öffnen`);
      open.addEventListener("click", () => openPreset(f.slot));
      const item = el("li", { className: "ui-row" }, [
        el("span", { className: "ui-break", textContent: `Part ${f.parts.join(", ")}: IFX ${f.slot} ${f.name}. ${text}. ` }),
        verdicts.length ? pill("warn", verdicts.some(v => v.measured) ? "gehört, zu laut" : verdicts.some(v => v.code === "output-too-loud") ? "zu laut" : "ungetestet") : null,
        open,
      ]);
      item.dataset.fxSlot = String(f.slot);
      list.append(item);
    }
    fxRows.append(list, el("p", { className: "muted cee-small", textContent: `${found.source}. Die Zuordnung Part zu Preset (Menüplatz = gespeicherter Typ plus 1) ist aus der Menülänge hergeleitet, am Gerät nicht geprüft.` }));
  }

  /** The output levels of the insert presets the parts use, from the device's RAM where it can be read, else from the firmware file. */
  async function readFx(s) {
    const known = presets();
    if (!known) return null;
    const { units, profile } = known;
    const byPart = new Map();
    for (const part of readLevels(pattern()).parts) {
      if (part.ifx === null) continue;
      byPart.set(part.ifx, [...(byPart.get(part.ifx) ?? []), part.part + 1]);
    }
    const list = known.list("ifx");
    let fromRam = 0;
    const found = [];
    for (const [slot, parts] of [...byPart].sort((a, b) => a[0] - b[0])) {
      let record = list.find(x => x.slot === slot)?.record ?? null;
      const name = list.find(x => x.slot === slot)?.name ?? "";
      if (s && !s.busy && !s.reserved) {
        try {
          const entry = known.address("ifx", slot);
          record = new FxRecord(await s.readRamBlock(entry.ram, entry.size), "ifx");
          fromRam++;
        } catch { /* the firmware file's copy stands in */ }
      }
      found.push({ slot, parts, name: record?.name || name, levels: record ? outputLevels(record, units) : [], missing: !record, profile });
    }
    const source = fromRam === found.length && found.length ? "Gelesen aus dem RAM"
      : fromRam ? "Teils aus dem RAM gelesen, sonst Stand der Firmware-Datei" : "Stand der Firmware-Datei, nicht aus dem RAM gelesen";
    found.source = source;
    return found;
  }

  function resetControls() {
    state.mode = "factor";
    state.value = "1";
    state.master = false;
    modeInputs[0].checked = true;
    valueInput.value = "1";
    masterToggle.checked = false;
  }

  async function load() {
    const s = await attached();
    if (!s) return;
    fetchButton.disabled = true;
    try {
      await s.idle();
      const block = await s.fetchPattern();
      state.block = Uint8Array.from(block);
      state.sendable = true;
      const p = new Pattern(block);
      state.name = p.name || "ohne Namen";
      resetControls();
      body.hidden = false;
      say(`Geholt: "${state.name}" aus dem Puffer.`);
      draw();
      drawFx(await readFx(s));
      undoButton.disabled = !s.history.some(h => h.pattern);
    } catch (e) {
      say(`Holen fehlgeschlagen: ${e.message}`);
    } finally {
      fetchButton.disabled = false;
    }
  }

  async function send() {
    const s = await attached();
    if (!s || !state.block) return;
    const p = plan();
    if (p.error || !p.changed) return;
    const edited = pattern();
    applyScale(edited, p);
    const edit = { kind: "patternSend", block: Uint8Array.from(edited.bytes) };
    const buttons = [sendButton, undoButton, fetchButton];
    buttons.forEach(b => { b.disabled = true; });
    const release = s.reserve();
    try {
      await s.idle();
      let active;
      try { active = new Pattern(await s.fetchPattern()).name || "ohne Namen"; } catch (e) {
        say(`Der Puffer am Gerät ließ sich nicht lesen (${e.message}); ohne Sicherung wird nichts gesendet.`);
        return;
      }
      const checked = await s.check(edit);
      if (checked.verdict === "blocked") { say(`Gesperrt: ${checked.reasons.map(r => r.message).join(" ")}`); return; }
      const warnings = checked.reasons.map(r => `Warnung: ${r.message}`).join("\n");
      const changes = p.rows.filter(r => r.delta !== 0).map(r => `${r.label} ${r.before} zu ${r.after}`).join(", ");
      const yes = await window.ui.confirm({
        title: "Skalierte Pegel ans Gerät senden?",
        text: `${changes}.\n\nAm Gerät ist gerade "${active}" im Puffer. Er wird vorher gesichert und lässt sich zurückholen. Dauerhaft wird das gesendete Pattern erst mit Write am Gerät.${warnings ? `\n\n${warnings}` : ""}`,
        confirmLabel: "Senden",
      });
      if (!yes) return;
      say("Sende …");
      const res = await s.apply(edit, { confirmed: checked.token });
      if (res.ok) {
        state.block = edit.block;
        resetControls();
        say(`Gesendet und zurückgelesen. Vorher im Puffer: "${active}", mit "Senden zurücknehmen" zurückzuholen.`);
        device.log?.("Pegel skaliert und gesendet.", "ok");
      } else if (res.needsConfirmation) say("Der Befund hat sich geändert, bitte noch einmal senden.");
      else if (res.gate?.verdict === "blocked") say(`Gesperrt: ${res.gate.reasons.map(r => r.message).join(" ")}`);
      else say(`${res.error?.message ?? "Abgebrochen."}${res.pending?.now ? ` ${res.pending.now.text}` : ""}${s.blocked ? " Entscheiden im Bereich Gerät." : ""}`);
      if (s.blocked) device.showDecision?.();
    } catch (e) {
      say(`Abgebrochen: ${e.message}`);
    } finally {
      release();
      fetchButton.disabled = false;
      undoButton.disabled = !s.history.some(h => h.pattern);
      draw();
    }
  }

  async function undo() {
    const s = await attached();
    if (!s) return;
    const release = s.reserve();
    try {
      await s.idle();
      const res = await s.undo();
      say(res.ok ? "Der vorherige Puffer ist wieder am Gerät. Zum Anzeigen noch einmal holen." : `Zurücknehmen fehlgeschlagen: ${res.error.message}`);
    } catch (e) {
      say(`Zurücknehmen fehlgeschlagen: ${e.message}`);
    } finally {
      release();
      undoButton.disabled = !s.history.some(h => h.pattern);
    }
  }

  fetchButton.addEventListener("click", load);
  sendButton.addEventListener("click", send);
  undoButton.addEventListener("click", undo);
  root.replaceChildren(
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Pegel eines Patterns" })]),
    el("p", { className: "muted", textContent: "Zeigt die Pegel des Patterns im Puffer nebeneinander und skaliert sie zusammen, ohne das Verhältnis zu verschieben. Gesendet wird wie sonst: mit Sicherung des Puffers, Bestätigung, Zurücklesen und Rücknahme." }),
    el("div", { className: "actions" }, [fetchButton]),
    body,
  );

  return { load, draw: () => { if (state.block) draw(); } };
}
