/**
 * The Samples page: the samples on the card (KORG/<folder>/Sample/e2sSample.all), listed, added and removed. The file comes
 * from a card reader. Changes are staged and written in one go; what is removed leaves no gap (src/sample-file.mjs).
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { parseSampleFile, planChange, applyPlan, entryFromWav, freeSlot, cleanSampleName, SampleFileError, FIRST_USER, LAST_USER } from "../../src/sample-file.mjs";

const RESTART = "Die Electribe lädt Samples nur beim Start: nach dem Kopieren auf die Karte neu starten.";

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const size = bytes => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
const seconds = s => `${s.frames && s.rate ? (s.frames / s.rate).toFixed(2).replace(".", ",") : "0"} s`;
const format = s => `${s.rate / 1000} kHz, ${s.bits} Bit, ${s.channels === 2 ? "Stereo" : "Mono"}`.replace(".", ",");

export function samplesFilePage(root) {
  let base = null;
  let parsed = null;
  let removed = new Set();
  let added = [];
  const pick = el("input", { type: "file", className: "ui-sr-only", id: "cee-sf-file", accept: ".all,.ALL", tabIndex: -1 });
  const wavs = el("input", { type: "file", className: "ui-sr-only", id: "cee-sf-wav", accept: ".wav,.WAV,audio/wav", multiple: true, tabIndex: -1 });
  for (const input of [pick, wavs]) input.setAttribute("aria-hidden", "true");
  const open = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-open", textContent: "e2sSample.all öffnen", onclick: () => pick.click() });
  const add = el("button", { type: "button", className: "btn", id: "cee-sf-add", textContent: "WAV hinzufügen", disabled: true, onclick: () => wavs.click() });
  const save = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-save", textContent: "Speichern", disabled: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-sf-reset", textContent: "Änderungen verwerfen", disabled: true });
  const summary = el("p", { className: "muted", id: "cee-sf-summary", role: "status" });
  const list = el("ul", { className: "ui-list cee-sf-list", id: "cee-sf-list" });
  const intro = el("p", { className: "cee-sample-intro" }, [
    "Hier siehst du die Samples auf der SD-Karte, in ",
    el("code", { textContent: "KORG/…/Sample/e2sSample.all" }),
    ". Du kannst welche hinzufügen oder rausnehmen. Wo du die Datei hernimmst: Karte in den Kartenleser, die Datei hier öffnen, speichern, zurück auf die Karte kopieren. ",
    RESTART,
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
    summary.textContent = `${kept.length + added.length} Samples, ${size(plan.size)}${dirty() ? ` (vorher ${size(parsed.size)})` : ""}`;
    const rows = [
      ...parsed.samples.map(s => ({ ...s, state: removed.has(s.slot) ? "removed" : "kept" })),
      ...added.map(a => ({ slot: a.slot, name: a.name, rate: a.rate, bits: a.bits, channels: a.channels, frames: a.frames, length: a.bytes.length, problem: null, state: "new" })),
    ].sort((a, b) => a.slot - b.slot);
    for (const s of rows) {
      const button = el("button", { type: "button", className: "btn sm", textContent: s.state === "removed" ? "Doch behalten" : "Entfernen" });
      button.dataset.slot = String(s.slot + 1);
      button.addEventListener("click", () => {
        if (s.state === "new") added = added.filter(a => a.slot !== s.slot);
        else if (removed.has(s.slot)) removed.delete(s.slot); else removed.add(s.slot);
        render();
      });
      const row = el("li", { className: "ui-row cee-sf-row" }, [
        el("span", { className: "cee-sf-nr", textContent: String(s.slot + 1) }),
        el("span", { className: "cee-sf-name", textContent: s.name || "(ohne Namen)" }),
        el("span", { className: "muted", textContent: s.problem ? "" : `${format(s)}, ${seconds(s)}, ${size(s.length)}` }),
        s.problem ? pill("error", s.problem) : s.state === "new" ? pill("ok", "neu") : s.state === "removed" ? pill("warn", "wird entfernt") : null,
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
      toast(`„${file.name}“ gelesen: ${parsed.samples.length} Samples.`, "ok");
    } catch (e) {
      toast(e instanceof SampleFileError ? e.message : `Die Datei ließ sich nicht lesen: ${e.message}`, "error");
    }
  });

  wavs.addEventListener("change", async () => {
    const files = [...(wavs.files ?? [])];
    wavs.value = "";
    for (const file of files) {
      const slot = freeSlot(new Set([...taken(), ...added.map(a => a.slot)]));
      if (slot === null) { toast(`Alle Plätze von ${FIRST_USER + 1} bis ${LAST_USER + 1} sind belegt.`, "error"); break; }
      try {
        const name = cleanSampleName(file.name.replace(/\.wav$/i, "")) || `Sample${slot + 1}`;
        const bytes = entryFromWav(new Uint8Array(await file.arrayBuffer()), slot, name);
        const probe = parseSampleFile(entryAsFile(bytes, slot)).samples[0];
        added.push({ slot, name, bytes, rate: probe.rate, bits: probe.bits, channels: probe.channels, frames: probe.frames });
        if (probe.bits === 24 || probe.channels === 2) toast(`„${file.name}“: ${probe.bits} Bit oder Stereo lädt die Electribe laut Messung im Emulator, am Gerät ist es nicht geprüft.`, "info");
      } catch (e) {
        toast(`„${file.name}“ geht nicht: ${e instanceof SampleFileError ? e.message : e.message}`, "error");
      }
    }
    render();
  });

  save.addEventListener("click", () => {
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    const out = applyPlan(base, plan);
    saveFile(out, "e2sSample.all", { note: RESTART });
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
