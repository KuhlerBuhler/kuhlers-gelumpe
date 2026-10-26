/**
 * The Samples page: the samples on the card (KORG/<folder>/Sample/e2sSample.all), listed, added and removed. The file comes
 * from a card reader. Changes are staged and written in one go; what is removed leaves no gap (src/sample-file.mjs).
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { parseSampleFile, planChange, applyPlan, entryFromWav, freeSlot, cleanSampleName, SampleFileError, FIRST_USER, LAST_USER } from "../../src/sample-file.mjs";
import { t, tNodes } from "./i18n.mjs";

const restart = () => t("sampleset.restart");

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const size = bytes => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
const seconds = s => `${s.frames && s.rate ? (s.frames / s.rate).toFixed(2).replace(".", ",") : "0"} s`;
const format = s => t("sampleset.format", { rate: s.rate / 1000, bits: s.bits, channels: s.channels === 2 ? t("sampleset.stereo") : t("sampleset.mono") }).replace(".", ",");

export function samplesFilePage(root) {
  let base = null;
  let parsed = null;
  let removed = new Set();
  let added = [];
  const pick = el("input", { type: "file", className: "ui-sr-only", id: "cee-sf-file", accept: ".all,.ALL", tabIndex: -1 });
  const wavs = el("input", { type: "file", className: "ui-sr-only", id: "cee-sf-wav", accept: ".wav,.WAV,audio/wav", multiple: true, tabIndex: -1 });
  for (const input of [pick, wavs]) input.setAttribute("aria-hidden", "true");
  const open = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-open", textContent: t("sampleset.open"), onclick: () => pick.click() });
  const add = el("button", { type: "button", className: "btn", id: "cee-sf-add", textContent: t("sampleset.add"), disabled: true, onclick: () => wavs.click() });
  const save = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-save", textContent: t("common.save"), disabled: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-sf-reset", textContent: t("sampleset.reset"), disabled: true });
  const summary = el("p", { className: "muted", id: "cee-sf-summary", role: "status" });
  const list = el("ul", { className: "ui-list cee-sf-list", id: "cee-sf-list" });
  const intro = el("p", { className: "cee-sample-intro" }, [
    ...tNodes("sampleset.intro", { path: el("code", { textContent: "KORG/…/Sample/e2sSample.all" }), restart: restart() }),
  ]);
  root.replaceChildren(intro, el("div", { className: "actions" }, [open, add, save, reset, pick, wavs]), summary, list);

  const taken = () => new Set([...parsed.samples.filter(s => !removed.has(s.slot)).map(s => s.slot), ...added.map(a => a.slot)]);
  const dirty = () => removed.size > 0 || added.length > 0;

  function render() {
    list.replaceChildren();
    add.disabled = !parsed;
    save.disabled = reset.disabled = !dirty();
    if (!parsed) { summary.textContent = ""; return; }
    const kept = parsed.samples.filter(s => !removed.has(s.slot));
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    summary.textContent = (dirty() ? t("sampleset.summary.changed", { count: kept.length + added.length, size: size(plan.size), before: size(parsed.size) }) : t("sampleset.summary", { count: kept.length + added.length, size: size(plan.size) }));
    const rows = [
      ...parsed.samples.map(s => ({ ...s, state: removed.has(s.slot) ? "removed" : "kept" })),
      ...added.map(a => ({ slot: a.slot, name: a.name, rate: a.rate, bits: a.bits, channels: a.channels, frames: a.frames, length: a.bytes.length, problem: null, state: "new" })),
    ].sort((a, b) => a.slot - b.slot);
    for (const s of rows) {
      const button = el("button", { type: "button", className: "btn sm", textContent: s.state === "removed" ? t("sampleset.keep") : t("common.remove") });
      button.dataset.slot = String(s.slot + 1);
      button.addEventListener("click", () => {
        if (s.state === "new") added = added.filter(a => a.slot !== s.slot);
        else if (removed.has(s.slot)) removed.delete(s.slot); else removed.add(s.slot);
        render();
      });
      const row = el("li", { className: "ui-row cee-sf-row" }, [
        el("span", { className: "cee-sf-nr", textContent: String(s.slot + 1) }),
        el("span", { className: "cee-sf-name", textContent: s.name || t("sampleset.noName") }),
        el("span", { className: "muted", textContent: s.problem ? "" : `${format(s)}, ${seconds(s)}, ${size(s.length)}` }),
        s.problem ? pill("error", s.problem) : s.state === "new" ? pill("ok", t("sampleset.new")) : s.state === "removed" ? pill("warn", t("sampleset.removing")) : null,
        button,
      ]);
      row.dataset.state = s.state;
      list.append(row);
    }
  }

  function load(bytes) {
    base = bytes;
    parsed = parseSampleFile(bytes);
    removed = new Set();
    added = [];
    render();
  }

  pick.addEventListener("change", async () => {
    const file = pick.files?.[0];
    pick.value = "";
    if (!file) return;
    try {
      load(new Uint8Array(await file.arrayBuffer()));
      toast(t("sampleset.read", { name: file.name, count: parsed.samples.length }), "ok");
    } catch (e) {
      toast(e instanceof SampleFileError ? e.message : t("sampleset.unreadable", { error: e.message }), "error");
    }
  });

  wavs.addEventListener("change", async () => {
    const files = [...(wavs.files ?? [])];
    wavs.value = "";
    for (const file of files) {
      const slot = freeSlot(new Set([...taken(), ...added.map(a => a.slot)]));
      if (slot === null) { toast(t("sampleset.full", { first: FIRST_USER + 1, last: LAST_USER + 1 }), "error"); break; }
      try {
        const name = cleanSampleName(file.name.replace(/\.wav$/i, "")) || `Sample${slot + 1}`;
        const bytes = entryFromWav(new Uint8Array(await file.arrayBuffer()), slot, name);
        const probe = parseSampleFile(entryAsFile(bytes, slot)).samples[0];
        added.push({ slot, name, bytes, rate: probe.rate, bits: probe.bits, channels: probe.channels, frames: probe.frames });
        if (probe.bits === 24 || probe.channels === 2) toast(t("sampleset.unchecked", { name: file.name, bits: probe.bits }), "info");
      } catch (e) {
        toast(t("sampleset.rejected", { name: file.name, error: e instanceof SampleFileError ? e.message : e.message }), "error");
      }
    }
    render();
  });

  save.addEventListener("click", () => {
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    const out = applyPlan(base, plan);
    saveFile(out, "e2sSample.all", { note: restart() });
    load(out);
  });
  reset.addEventListener("click", () => { removed = new Set(); added = []; render(); });
  render();
}

/** One entry as a file of its own, so the parser can read its facts. */
function entryAsFile(entry, slot) {
  const out = new Uint8Array(4096 + entry.length);
  out.set(new TextEncoder().encode("e2s sample all"), 0);
  out[14] = 0x1a;
  const at = 16 + 4 * slot;
  out[at] = 4096 & 255; out[at + 1] = 4096 >> 8;
  out.set(entry, 4096);
  return out;
}
