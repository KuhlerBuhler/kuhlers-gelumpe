/**
 * The Samples page: name and tune of a sample in RAM, sent through the same gate, rehearsal and
 * read-back as every other live edit. Logic: src/samples.mjs, src/sample-rules.mjs, src/plan.mjs.
 */
import { el } from "./fields.mjs";
import { field, typeOf } from "../../src/map/index.mjs";
import { SAMPLE_COUNT } from "../../src/samples.mjs";
import { lintSample, TUNE_SEEN } from "../../src/sample-rules.mjs";
import { ensureFirmware } from "../../src/korg.mjs";

const SEVERITY = {
  fatal: ["error", "tödlich"], silent: ["error", "stumm"], error: ["error", "Fehler"],
  warn: ["warn", "Warnung"], note: ["neutral", "Hinweis"],
};

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const NAME = typeOf(field("sample.name"));

export function samplesPage(root, { device, emulator, probe }) {
  const state = { index: null, entry: null, name: "", tune: 0, nameError: null, tuneError: false, names: [], opening: 0 };

  const intro = el("div", { className: "cee-sample-intro" }, [
    el("p", { textContent: "Hier änderst du Name und Tune eines Samples im Arbeitsspeicher der Electribe. Der Editor liest die Namenstabelle, du wählst ein Sample, änderst es und schickst es live ins RAM. Es geht wie jede Änderung durch den Türsteher, bei einem echten Gerät zuerst durch den Emulator, und wird danach zurückgelesen." }),
  ]);
  const note = el("p", { className: "cee-note", id: "cee-sample-note" }, [
    el("strong", { textContent: "Nur im RAM. " }),
    "Gemessen ist: Name und Tune wirkten am Gerät sofort (das Display zeigte den neuen Namen, die Tonhöhe änderte sich hörbar), und die SD-Datei mit den Samples blieb dabei unverändert. Nicht gemessen ist, ob eine Änderung einen Neustart überlebt oder ob DATA UTILITY, 11 EXPORT ALL SAMPLE sie auf die Karte schreibt. Rechne damit, dass sie weg ist, wenn du das Gerät ausschaltest.",
  ]);
  const status = el("p", { className: "muted", id: "cee-sample-status", role: "status" });
  const listButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-sample-list", textContent: "Namen lesen" });
  const numberId = "cee-sample-number";
  const number = el("input", { type: "number", className: "input cee-num", id: numberId, min: 1, max: SAMPLE_COUNT, step: 1, value: "501" });
  const openButton = el("button", { type: "button", className: "btn", id: "cee-sample-open", textContent: "Sample lesen" });
  const hideDefault = el("input", { type: "checkbox", id: "cee-sample-hide-default", checked: true });
  hideDefault.setAttribute("role", "switch");
  const bar = el("div", { className: "cee-sample-bar" }, [
    listButton,
    el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: numberId, textContent: "Sample-Nummer" }), number]),
    openButton,
    el("label", { className: "ui-switch" }, [hideDefault, el("span", { className: "ui-switch-track", ariaHidden: "true" }), "Standardnamen (SampleNNN) ausblenden"]),
  ]);
  const list = el("ul", { className: "ui-list cee-pattern-list", id: "cee-sample-names" });
  const side = el("aside", { className: "ui-split-side", id: "cee-sample-side" }, [el("h2", { className: "ui-section-title", textContent: "Samples mit Namen" }), list]);
  const form = el("div", { className: "cee-sample-form", id: "cee-sample-form" });
  const toggle = el("button", { type: "button", className: "btn ui-split-toggle", textContent: "Samples" });
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "cee-sample-side");
  const split = el("div", { className: "ui-split", id: "cee-sample-split", hidden: true }, [toggle, side, el("div", { className: "ui-split-main" }, [form])]);

  root.replaceChildren(intro, note, bar, status, split);

  /** The session to read from and send to: the attached device or emulator, else the running emulator. */
  async function pick() {
    return device.session ?? (emulator.port.running ? await probe().catch(() => null) : null);
  }

  const say = (text, tone = "") => { status.textContent = text; status.dataset.tone = tone; };
  const where = s => (s.port.emulator ? "Emulator" : "Gerät");
  const busy = on => { for (const b of [listButton, openButton]) b.disabled = on; };

  async function withSession(fn) {
    const s = await pick();
    if (!s) { say("Nichts verbunden. Schalte im Bereich Emulator die Electribe ein, oder steck dein Gerät per USB an und wähl dort oben „Echtes Gerät“.", "error"); return null; }
    const release = s.reserve();
    busy(true);
    try {
      await s.idle();
      return await fn(s);
    } catch (e) {
      say(`Lesen hat nicht geklappt. Ist die Electribe noch verbunden? (${e.message})`, "error");
      return null;
    } finally {
      release();
      busy(false);
    }
  }

  function drawList() {
    // Measured in the emulator: a slot nobody filled holds the name SampleNNN with NNN its number.
    const named = state.names.map((name, index) => ({ name, index })).filter(x => x.name && !(hideDefault.checked && x.name === `Sample${x.index + 1}`));
    list.replaceChildren(...named.map(({ name, index }) => {
      const b = el("button", { type: "button", className: "cee-pattern-item" }, [
        el("span", { className: "cee-pattern-num", textContent: String(index + 1) }),
        el("span", { className: "ui-truncate", textContent: name }),
      ]);
      b.dataset.n = String(index);
      b.setAttribute("aria-current", String(index === state.index));
      return el("li", {}, b);
    }));
    split.hidden = false;
    return named.length;
  }

  async function readList() {
    const names = await withSession(async s => {
      say("Lese die Namenstabelle …");
      const got = await s.readSampleNames({ onProgress: (n, total) => say(`Lese die Namenstabelle: ${Math.round((n / total) * 100)} %`) });
      state.source = where(s);
      return got;
    });
    if (!names) return;
    state.names = names;
    const n = drawList();
    say(n ? `${n} Samples mit Namen, gelesen aus dem ${state.source}.` : `Keine Sample-Namen gefunden. Im Emulator ist das normal, wenn keine Samples auf der Karte sind. Über die Sample-Nummer kannst du trotzdem einen Platz öffnen.`);
  }

  async function openSample(index) {
    const mine = ++state.opening;
    const entry = await withSession(s => s.readSample(index).then(e => { state.source = where(s); return e; }));
    if (!entry || mine !== state.opening) return;
    Object.assign(state, { index, entry, name: entry.name, tune: entry.tune, nameError: null, tuneError: false });
    number.value = String(index + 1);
    split.hidden = false;
    for (const b of list.querySelectorAll("button")) b.setAttribute("aria-current", String(Number(b.dataset.n) === index));
    say(`Sample ${index + 1} gelesen aus dem ${state.source}.`);
    render();
  }

  const changes = () => ({
    ...(state.name !== state.entry.name ? { name: state.name } : {}),
    ...(state.tune !== state.entry.tune ? { tune: state.tune } : {}),
  });
  const buildEdit = () => ({
    kind: "sample", index: state.index, ...changes(),
    before: { name: state.entry.name, tune: state.entry.tune, rate: state.entry.rate, pcmBytes: state.entry.pcmBytes },
  });

  const verdict = el("div", { className: "cee-verdict", id: "cee-sample-verdict", ariaLive: "polite" });
  const sendButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-sample-send", textContent: "Live ins RAM", disabled: true });
  const undoButton = el("button", { type: "button", className: "btn", id: "cee-sample-undo", textContent: "Zurücknehmen", disabled: true });
  const job = el("div", { className: "ui-job cee-job", id: "cee-sample-job", hidden: true, role: "status" });

  function refreshVerdict() {
    const edit = buildEdit();
    const changed = Object.keys(changes()).length > 0;
    sendButton.disabled = !changed || !!state.nameError || state.tuneError;
    if (!changed) { verdict.replaceChildren(el("p", { className: "muted", textContent: "Nichts geändert." })); return; }
    const findings = lintSample(edit);
    const items = el("ul", { className: "ui-list" });
    for (const f of findings) {
      const [tone, word] = SEVERITY[f.severity];
      items.append(el("li", { className: "ui-row" }, [pill(tone, word), el("span", { className: "ui-break", textContent: ` ${f.message}` })]));
    }
    verdict.replaceChildren(el("h3", { textContent: "Türsteher" }), findings.length ? items : el("p", {}, [pill("ok", "sauber"), " Keine Befunde."]));
  }

  const fact = (term, value) => [el("dt", { textContent: term }), el("dd", { textContent: value })];

  function render() {
    const e = state.entry;
    const nameId = "cee-sample-name";
    const tuneId = "cee-sample-tune";
    const nameInput = el("input", { className: "input", id: nameId, type: "text", maxLength: NAME.width, spellcheck: false, autocomplete: "off", value: state.name });
    nameInput.addEventListener("input", () => {
      try {
        NAME.write(new Uint8Array(NAME.width), 0, nameInput.value);
        state.nameError = null;
        state.name = nameInput.value;
      } catch (err) { state.nameError = err.message; }
      window.ui?.setFieldError(nameInput, state.nameError);
      refreshVerdict();
    });
    const tuneInput = el("input", { className: "input cee-num", id: tuneId, type: "number", min: -128, max: 127, step: 1, value: String(state.tune) });
    tuneInput.addEventListener("input", () => {
      const v = Number(tuneInput.value);
      if (tuneInput.value === "" || !Number.isInteger(v) || v < -128 || v > 127) { state.tuneError = true; refreshVerdict(); return; }
      state.tuneError = false;
      state.tune = v;
      refreshVerdict();
    });
    const empty = e.pcmBytes === 0;
    form.replaceChildren(
      el("h3", { textContent: `Sample ${e.index + 1}${e.name ? `: ${e.name}` : ""}` }),
      empty ? el("p", { className: "cee-hint", textContent: "Der Platz sieht unbenutzt aus: die PCM-Länge ist 0. Ein Name oder eine Samplerate sagt das nicht, im Emulator tragen unbenutzte Plätze den Namen SampleNNN und 48000 Hz." }) : "",
      el("div", { className: "cee-grid" }, [
        el("div", { className: "ui-field" }, [
          el("label", { className: "ui-field-label", htmlFor: nameId, textContent: "Name" }), nameInput,
          el("p", { className: "ui-field-help", textContent: "Bis zu 16 Zeichen, die das Display zeigen kann (ASCII). Am Gerät geschrieben und am Display bestätigt." }),
        ]),
        el("div", { className: "ui-field" }, [
          el("label", { className: "ui-field-label", htmlFor: tuneId, textContent: "Tune (Rohwert)" }), tuneInput,
          el("p", { className: "ui-field-help", textContent: `Das Byte, wie das Gerät es hält, -128 bis 127. Gesehen sind ${TUNE_SEEN[0]} bis ${TUNE_SEEN[1]}; -12 änderte die Tonhöhe hörbar. Die Skala ist nicht gemessen, auch nicht, ob ein Schritt ein Halbton ist.` }),
        ]),
      ]),
      el("dl", { className: "cee-facts", id: "cee-sample-facts" }, [
        ...fact("Samplerate", `${e.rate} Hz`),
        ...fact("Länge", `${e.pcmBytes} Byte PCM`),
        ...fact("Kanäle", e.stereo ? "Stereo" : "Mono"),
        ...fact("Kategorie", String(e.category)),
        ...fact("Import-Nummer", String(e.importNumber)),
        ...fact("One-Shot", e.oneShot ? "ja" : "nein"),
      ]),
      el("p", { className: "muted", textContent: "Die Werte unter dem Namen sind gelesen und nicht änderbar: gemessen ist, wo sie im RAM stehen, nicht, was ein Schreiben bewirkt." }),
      verdict,
      el("div", { className: "actions" }, [sendButton, undoButton]),
      job,
    );
    refreshVerdict();
    undoButton.disabled = !canUndo();
  }

  const canUndo = () => { const s = device.session ?? probe.current?.(); return !!s && s.history.at(-1)?.edit.kind === "sample"; };

  function progress(name) {
    job.hidden = false;
    const bar = el("div", { className: "ui-progress", role: "progressbar" }, [el("span", { className: "ui-progress-bar" })]);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    const pillNode = el("span", { className: "cee-status", textContent: "Läuft" });
    pillNode.dataset.tone = "running";
    const meta = el("span", { className: "ui-job-meta" });
    job.replaceChildren(el("div", { className: "ui-job-head" }, [el("span", { className: "ui-job-name", textContent: name }), pillNode]), bar, meta);
    return {
      step(n, total) { window.ui?.setProgress(bar, Math.round((n / total) * 100), name); meta.textContent = `Schritt ${n} von ${total}`; },
      done(ok, text) {
        pillNode.textContent = ok ? "Fertig" : "Fehlgeschlagen";
        pillNode.dataset.tone = ok ? "ok" : "error";
        bar.dataset.tone = ok ? "ok" : "error";
        window.ui?.setProgress(bar, 100, name, ok ? undefined : { valueText: "Fehlgeschlagen" });
        meta.textContent = text;
      },
    };
  }

  function showBlocked(reasons) {
    const items = el("ul", { className: "ui-list", id: "cee-sample-blocked" });
    for (const r of reasons) {
      const [tone, word] = SEVERITY[r.severity] ?? ["error", "gesperrt"];
      items.append(el("li", { className: "ui-row" }, [pill(tone, word), el("span", { className: "ui-break", textContent: ` ${r.message}` })]));
    }
    verdict.replaceChildren(el("h3", { textContent: "Gesperrt" }), items);
    device.log?.(`Gesperrt: ${reasons[0]?.message ?? ""}`, "error");
  }

  async function reread(s) {
    try {
      state.entry = await s.readSample(state.index);
      Object.assign(state, { name: state.entry.name, tune: state.entry.tune, nameError: null, tuneError: false });
    } catch (e) { say(`Neu lesen hat nicht geklappt. Ist die Electribe noch verbunden? (${e.message})`, "error"); }
  }

  async function send() {
    const s = await pick();
    if (!s) { say("Nichts verbunden. Schalte im Bereich Emulator die Electribe ein, oder steck dein Gerät per USB an und wähl dort oben „Echtes Gerät“.", "error"); return; }
    sendButton.disabled = undoButton.disabled = true;
    const release = s.reserve();
    let p = null;
    try {
      await ensureFirmware(s, emulator.baseFirmware);
      await s.idle();
      const edit = buildEdit();
      const checked = await s.check(edit);
      if (checked.verdict === "blocked") { showBlocked(checked.reasons); return; }
      if (checked.verdict === "confirm") {
        const text = checked.reasons.map(r => `${SEVERITY[r.severity]?.[1] ?? r.severity}: ${r.message}`).join("\n");
        const yes = await window.ui.confirm({ title: "Trotz Warnungen senden?", text, confirmLabel: "Senden", danger: false });
        if (!yes) return;
      }
      p = progress(`Sample ${state.index + 1} ins RAM`);
      const result = await s.apply(edit, { confirmed: checked.token, onStep: p.step });
      if (result.needsConfirmation) { p.done(false, "Der Befund hat sich geändert, bitte noch einmal senden."); return; }
      if (result.gate?.verdict === "blocked") { p.done(false, "Vom Türsteher gesperrt."); showBlocked(result.gate.reasons); return; }
      if (result.ok) {
        await reread(s);
        p.done(true, "Gesendet und zurückgelesen, stimmt überein. Nur im RAM, nicht gespeichert.");
        device.log?.(`Sample ${state.index + 1} live geschrieben.`, "ok");
        render();
        return;
      }
      const text = result.error ? `${result.error.message}${result.pending?.now ? ` ${result.pending.now.text}` : ""}` : "abgebrochen";
      p.done(false, text);
      device.log?.(`Sample ${state.index + 1}: ${text}`, "error");
      if (s.blocked) { showBlocked([{ severity: "error", code: "target-blocked", message: `${s.blocked} Entscheiden im Bereich Gerät.` }]); device.showDecision?.(); }
    } catch (e) {
      if (p) p.done(false, e.message);
      else say(e.message, "error");
    } finally {
      release();
      refreshVerdict();
      undoButton.disabled = !canUndo();
    }
  }

  async function undo() {
    const s = await pick();
    if (!s) return;
    const release = s.reserve();
    undoButton.disabled = sendButton.disabled = true;
    const p = progress("Zurücknehmen");
    let res;
    try {
      await s.idle();
      res = await s.undo({ onStep: p.step });
      if (res.ok && state.index !== null) await reread(s);
    } catch (e) {
      res = { ok: false, error: e };
    } finally {
      release();
    }
    p.done(res.ok, res.ok ? "Alter Stand ist wieder im RAM." : res.error.message);
    device.log?.(res.ok ? "Letzte Änderung zurückgenommen." : `Zurücknehmen fehlgeschlagen: ${res.error.message}`, res.ok ? "ok" : "error");
    if (state.entry) render();
  }

  listButton.addEventListener("click", readList);
  hideDefault.addEventListener("change", () => { if (state.names.length) say(`${drawList()} Samples in der Liste.`); });
  openButton.addEventListener("click", () => {
    const n = Number(number.value);
    if (!Number.isInteger(n) || n < 1 || n > SAMPLE_COUNT) { say(`Die Sample-Nummer geht von 1 bis ${SAMPLE_COUNT}.`, "error"); return; }
    openSample(n - 1);
  });
  list.addEventListener("click", e => {
    const b = e.target.closest("button[data-n]");
    if (b) openSample(Number(b.dataset.n));
  });
  sendButton.addEventListener("click", send);
  undoButton.addEventListener("click", undo);
  say("Noch nichts gelesen. Schalte im Bereich Emulator die Electribe ein oder verbinde dein Gerät, dann die Namen lesen.");
}
