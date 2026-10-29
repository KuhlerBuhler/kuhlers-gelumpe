/**
 * The Samples page: name and tune of a sample in RAM, sent through the same gate, rehearsal and
 * read-back as every other live edit. Logic: src/samples.mjs, src/sample-rules.mjs, src/plan.mjs.
 */
import { toast } from "./toast.mjs";
import { el } from "./fields.mjs";
import { field, typeOf } from "../../src/map/index.mjs";
import { SAMPLE_COUNT } from "../../src/samples.mjs";
import { lintSample, TUNE_SEEN } from "../../src/sample-rules.mjs";
import { ensureFirmware } from "../../src/korg.mjs";
import { t } from "./i18n.mjs";

const SEVERITY = {
  fatal: ["error", "samples.severity.fatal"], silent: ["error", "levels.muted"], error: ["error", "common.error"],
  warn: ["warn", "device.log.warn"], note: ["neutral", "mod.hint"],
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
    el("p", { textContent: t("samples.intro") }),
  ]);
  const note = el("p", { className: "cee-note", id: "cee-sample-note" }, [
    el("strong", { textContent: t("samples.ramOnly") }),
    t("samples.ramOnly.text"),
  ]);
  const status = el("p", { className: "muted", id: "cee-sample-status", role: "status" });
  const listButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-sample-list", textContent: t("samples.readNames") });
  const numberId = "cee-sample-number";
  const number = el("input", { type: "number", className: "input cee-num", id: numberId, min: 1, max: SAMPLE_COUNT, step: 1, value: "501" });
  const openButton = el("button", { type: "button", className: "btn", id: "cee-sample-open", textContent: t("samples.readSample") });
  const hideDefault = el("input", { type: "checkbox", id: "cee-sample-hide-default", checked: true });
  hideDefault.setAttribute("role", "switch");
  const bar = el("div", { className: "cee-sample-bar" }, [
    listButton,
    el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: numberId, textContent: t("samples.number") }), number]),
    openButton,
    el("label", { className: "ui-switch" }, [hideDefault, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("samples.hideDefault")]),
  ]);
  const list = el("ul", { className: "ui-list cee-pattern-list", id: "cee-sample-names" });
  const side = el("aside", { className: "ui-split-side", id: "cee-sample-side" }, [el("h2", { className: "ui-section-title", textContent: t("samples.named") }), list]);
  const form = el("div", { className: "cee-sample-form", id: "cee-sample-form" });
  const toggle = el("button", { type: "button", className: "btn ui-split-toggle", textContent: t("samples.list") });
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "cee-sample-side");
  const split = el("div", { className: "ui-split", id: "cee-sample-split", hidden: true }, [toggle, side, el("div", { className: "ui-split-main" }, [form])]);

  root.replaceChildren(intro, note, bar, status, split);

  /** The session to read from and send to: the attached device or emulator, else the running emulator. */
  async function pick() {
    return device.session ?? (emulator.port.running ? await probe().catch(() => null) : null);
  }

  // Messages go to the toast; a running read ("Lese die Namenstabelle …") and the hint before the first read stand in the line.
  const say = (text, tone = "") => {
    const progress = tone === "progress" || tone === "hint";
    status.textContent = progress ? text : "";
    if (!progress) toast(text, tone === "error" ? "error" : tone === "ok" ? "ok" : "info");
  };
  const where = s => (s.port.emulator ? "emu" : "device");
  const busy = on => { for (const b of [listButton, openButton]) b.disabled = on; };

  async function withSession(fn) {
    const s = await pick();
    if (!s) { say(t("levels.nothing"), "error"); return null; }
    const release = s.reserve();
    busy(true);
    try {
      await s.idle();
      return await fn(s);
    } catch (e) {
      say(t("samples.readFailed", { error: e.message }), "error");
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
      say(t("samples.reading"), "progress");
      const got = await s.readSampleNames({ onProgress: (n, total) => say(t("samples.readingPercent", { percent: Math.round((n / total) * 100) }), "progress") });
      state.source = where(s);
      return got;
    });
    if (!names) return;
    state.names = names;
    const n = drawList();
    say(n ? t(state.source === "emu" ? "samples.listRead.emu" : "samples.listRead.device", { count: n }) : t("samples.noNames"));
  }

  async function openSample(index) {
    const mine = ++state.opening;
    const entry = await withSession(s => s.readSample(index).then(e => { state.source = where(s); return e; }));
    if (!entry || mine !== state.opening) return;
    Object.assign(state, { index, entry, name: entry.name, tune: entry.tune, nameError: null, tuneError: false });
    number.value = String(index + 1);
    split.hidden = false;
    for (const b of list.querySelectorAll("button")) b.setAttribute("aria-current", String(Number(b.dataset.n) === index));
    say(t(state.source === "emu" ? "samples.sampleRead.emu" : "samples.sampleRead.device", { n: index + 1 }));
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
  const sendButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-sample-send", textContent: t("samples.send"), disabled: true });
  const undoButton = el("button", { type: "button", className: "btn", id: "cee-sample-undo", textContent: t("samples.undo"), disabled: true });
  const job = el("div", { className: "ui-job cee-job", id: "cee-sample-job", hidden: true, role: "status" });

  function refreshVerdict() {
    const edit = buildEdit();
    const changed = Object.keys(changes()).length > 0;
    sendButton.disabled = !changed || !!state.nameError || state.tuneError;
    if (!changed) { verdict.replaceChildren(el("p", { className: "muted", textContent: t("samples.unchanged") })); return; }
    const findings = lintSample(edit);
    const items = el("ul", { className: "ui-list" });
    for (const f of findings) {
      const [tone, word] = SEVERITY[f.severity];
      items.append(el("li", { className: "ui-row" }, [pill(tone, t(word)), el("span", { className: "ui-break", textContent: ` ${t(f.text)}` })]));
    }
    verdict.replaceChildren(el("h3", { textContent: t("samples.gate") }), findings.length ? items : el("p", {}, [pill("ok", t("samples.clean")), ` ${t("samples.noFindings")}`]));
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
      el("h3", { textContent: (e.name ? t("samples.title.named", { n: e.index + 1, name: e.name }) : t("samples.title", { n: e.index + 1 })) }),
      empty ? el("p", { className: "cee-hint", textContent: t("samples.empty") }) : "",
      el("div", { className: "cee-grid" }, [
        el("div", { className: "ui-field" }, [
          el("label", { className: "ui-field-label", htmlFor: nameId, textContent: t("mod.field.name") }), nameInput,
          el("p", { className: "ui-field-help", textContent: t("samples.name.help") }),
        ]),
        el("div", { className: "ui-field" }, [
          el("label", { className: "ui-field-label", htmlFor: tuneId, textContent: t("samples.tune") }), tuneInput,
          el("p", { className: "ui-field-help", textContent: t("samples.tune.help", { low: TUNE_SEEN[0], high: TUNE_SEEN[1] }) }),
        ]),
      ]),
      el("dl", { className: "cee-facts", id: "cee-sample-facts" }, [
        ...fact(t("samples.fact.rate"), `${e.rate} Hz`),
        ...fact(t("samples.fact.length"), t("samples.fact.lengthValue", { bytes: e.pcmBytes })),
        ...fact(t("samples.fact.channels"), e.stereo ? t("sampleset.stereo") : t("sampleset.mono")),
        ...fact(t("samples.fact.category"), String(e.category)),
        ...fact(t("samples.fact.import"), String(e.importNumber)),
        ...fact(t("samples.fact.oneShot"), e.oneShot ? t("common.yes") : t("common.no")),
      ]),
      el("p", { className: "muted", textContent: t("samples.readOnly") }),
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
    const pillNode = el("span", { className: "cee-status", textContent: t("samples.job.running") });
    pillNode.dataset.tone = "running";
    const meta = el("span", { className: "ui-job-meta" });
    job.replaceChildren(el("div", { className: "ui-job-head" }, [el("span", { className: "ui-job-name", textContent: name }), pillNode]), bar, meta);
    return {
      step(n, total) { window.ui?.setProgress(bar, Math.round((n / total) * 100), name); meta.textContent = t("samples.job.step", { n, total }); },
      done(ok, text) {
        pillNode.textContent = ok ? t("samples.job.done") : t("samples.job.failed");
        pillNode.dataset.tone = ok ? "ok" : "error";
        bar.dataset.tone = ok ? "ok" : "error";
        window.ui?.setProgress(bar, 100, name, ok ? undefined : { valueText: t("samples.job.failed") });
        meta.textContent = text;
      },
    };
  }

  function showBlocked(reasons) {
    const items = el("ul", { className: "ui-list", id: "cee-sample-blocked" });
    for (const r of reasons) {
      const [tone, word] = SEVERITY[r.severity] ?? ["error", "backup.locked"];
      items.append(el("li", { className: "ui-row" }, [pill(tone, t(word)), el("span", { className: "ui-break", textContent: ` ${t(r.text ?? r.message)}` })]));
    }
    verdict.replaceChildren(el("h3", { textContent: t("samples.blocked") }), items);
    device.log?.(t("backup.blocked", { reasons: reasons[0]?.message ?? "" }), "error");
  }

  async function reread(s) {
    try {
      state.entry = await s.readSample(state.index);
      Object.assign(state, { name: state.entry.name, tune: state.entry.tune, nameError: null, tuneError: false });
    } catch (e) { say(t("samples.rereadFailed", { error: e.message }), "error"); }
  }

  async function send() {
    const s = await pick();
    if (!s) { say(t("levels.nothing"), "error"); return; }
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
        const text = checked.reasons.map(r => `${SEVERITY[r.severity] ? t(SEVERITY[r.severity][1]) : r.severity}: ${r.message}`).join("\n");
        const yes = await window.ui.confirm({ title: t("samples.confirm.title"), text, confirmLabel: t("backup.send.confirm"), danger: false });
        if (!yes) return;
      }
      p = progress(t("samples.job.name", { n: state.index + 1 }));
      const result = await s.apply(edit, { confirmed: checked.token, onStep: p.step });
      if (result.needsConfirmation) { p.done(false, t("backup.changed")); return; }
      if (result.gate?.verdict === "blocked") { p.done(false, t("samples.blockedByGate")); showBlocked(result.gate.reasons); return; }
      if (result.ok) {
        await reread(s);
        p.done(true, t("samples.sent"));
        device.log?.(t("samples.sentLog", { n: state.index + 1 }), "ok");
        render();
        return;
      }
      const text = result.error ? `${result.error.message}${result.pending?.now ? ` ${result.pending.now.text}` : ""}` : t("samples.aborted");
      p.done(false, text);
      device.log?.(t("samples.failedLog", { n: state.index + 1, error: text }), "error");
      if (s.blocked) { showBlocked([{ severity: "error", code: "target-blocked", message: t("samples.decide", { reason: s.blocked }) }]); device.showDecision?.(); }
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
    const p = progress(t("samples.undo"));
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
    p.done(res.ok, res.ok ? t("samples.undone") : res.error.message);
    device.log?.(res.ok ? t("samples.undoneLog") : t("backup.undoFailed", { error: res.error.message }), res.ok ? "ok" : "error");
    if (state.entry) render();
  }

  listButton.addEventListener("click", readList);
  hideDefault.addEventListener("change", () => { if (state.names.length) say(t("samples.inList", { count: drawList() })); });
  openButton.addEventListener("click", () => {
    const n = Number(number.value);
    if (!Number.isInteger(n) || n < 1 || n > SAMPLE_COUNT) { say(t("samples.numberRange", { max: SAMPLE_COUNT }), "error"); return; }
    openSample(n - 1);
  });
  list.addEventListener("click", e => {
    const b = e.target.closest("button[data-n]");
    if (b) openSample(Number(b.dataset.n));
  });
  sendButton.addEventListener("click", send);
  undoButton.addEventListener("click", undo);
  say(t("samples.hint"), "hint");
}
