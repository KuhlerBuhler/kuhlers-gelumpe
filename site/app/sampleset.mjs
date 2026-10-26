/**
 * The Samples page: the samples on the card (KORG/<folder>/Sample/e2sSample.all), listed, added and removed. The file comes
 * from a card reader or from the connected Electribe over USB (src/usb-sample-file.mjs). Changes are staged and written in one
 * go; what is removed leaves no gap (src/sample-file.mjs).
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { parseSampleFile, planChange, applyPlan, entryFromWav, freeSlot, cleanSampleName, SampleFileError, FIRST_USER, LAST_USER } from "../../src/sample-file.mjs";
import { readDeviceSamples, writeDeviceChange, needsCompaction, inspectTemp, finishTemp, discardTemp, SwapInterrupted } from "../../src/usb-sample-file.mjs";

const RESTART = "Die Electribe lädt Samples nur beim Start: nach dem Kopieren auf die Karte neu starten.";

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const size = bytes => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
const seconds = s => `${s.frames && s.rate ? (s.frames / s.rate).toFixed(2).replace(".", ",") : "0"} s`;
const format = s => `${s.rate / 1000} kHz, ${s.bits} Bit, ${s.channels === 2 ? "Stereo" : "Mono"}`.replace(".", ",");

export function samplesFilePage(root, { device = null } = {}) {
  let source = "file";
  let busy = false;
  let base = null;
  let parsed = null;
  let removed = new Set();
  let added = [];
  const pick = el("input", { type: "file", className: "ui-sr-only", id: "cee-sf-file", accept: ".all,.ALL", tabIndex: -1 });
  const wavs = el("input", { type: "file", className: "ui-sr-only", id: "cee-sf-wav", accept: ".wav,.WAV,audio/wav", multiple: true, tabIndex: -1 });
  for (const input of [pick, wavs]) input.setAttribute("aria-hidden", "true");
  const open = el("button", { type: "button", className: "btn", id: "cee-sf-open", textContent: "e2sSample.all öffnen", onclick: () => pick.click() });
  const fromDevice = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-device", textContent: "Von der Electribe lesen", disabled: true, onclick: () => loadFromDevice() });
  const add = el("button", { type: "button", className: "btn", id: "cee-sf-add", textContent: "WAV hinzufügen", disabled: true, onclick: () => wavs.click() });
  const save = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-save", textContent: "Speichern", disabled: true });
  const job = el("div", { className: "ui-job", id: "cee-sf-job", hidden: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-sf-reset", textContent: "Änderungen verwerfen", disabled: true });
  const summary = el("p", { className: "muted", id: "cee-sf-summary", role: "status" });
  const list = el("ul", { className: "ui-list cee-sf-list", id: "cee-sf-list" });
  const intro = el("p", { className: "cee-sample-intro" }, [
    "Hier siehst du die Samples auf der SD-Karte, in ",
    el("code", { textContent: "KORG/…/Sample/e2sSample.all" }),
    ". Du kannst welche hinzufügen oder rausnehmen. Entweder liest du sie von der angesteckten Electribe (dazu muss sie verbunden sein) und schreibst die Änderung dorthin zurück, oder du öffnest die Datei von der Karte aus dem Kartenleser, speicherst sie und kopierst sie zurück. ",
    RESTART,
  ]);
  root.replaceChildren(intro, el("div", { className: "actions" }, [fromDevice, open, add, save, reset, pick, wavs]), job, summary, list);

  const taken = () => new Set([...parsed.samples.filter(s => !removed.has(s.slot)).map(s => s.slot), ...added.map(a => a.slot)]);
  const dirty = () => removed.size > 0 || added.length > 0;

  const session = () => (device?.session && !device.session.sender.disconnected ? device.session : null);

  function render() {
    list.replaceChildren();
    fromDevice.disabled = busy || !session();
    open.disabled = busy;
    add.disabled = !parsed || busy;
    save.textContent = source === "device" ? "Auf die Karte schreiben" : "Speichern";
    save.disabled = reset.disabled = !dirty() || busy;
    if (!parsed) { summary.textContent = ""; return; }
    const kept = parsed.samples.filter(s => !removed.has(s.slot));
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    summary.textContent = `${kept.length + added.length} Samples, ${size(plan.size)}${dirty() ? ` (vorher ${size(parsed.size)})` : ""}`;
    const rows = [
      ...parsed.samples.map(s => ({ ...s, state: removed.has(s.slot) ? "removed" : "kept" })),
      ...added.map(a => ({ slot: a.slot, name: a.name, rate: a.rate, bits: a.bits, channels: a.channels, frames: a.frames, length: a.bytes.length, problem: null, state: "new" })),
    ].sort((a, b) => a.slot - b.slot);
    for (const s of rows) {
      const button = el("button", { type: "button", className: "btn sm", textContent: s.state === "removed" ? "Doch behalten" : "Entfernen", disabled: busy });
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
    source = "file";
    base = bytes;
    parsed = parseSampleFile(bytes);
    removed = new Set();
    added = [];
    render();
  }

  /** The progress of a running job in the page: its phase and how far it is. */
  function progress(name) {
    job.hidden = false;
    const bar = el("div", { className: "ui-progress", role: "progressbar" }, [el("span", { className: "ui-progress-bar" })]);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    const meta = el("span", { className: "ui-job-meta" });
    job.replaceChildren(el("div", { className: "ui-job-head" }, [el("span", { className: "ui-job-name", textContent: name })]), bar, meta);
    return {
      step(phase, done, total) { window.ui?.setProgress(bar, total ? Math.round((done / total) * 100) : 0, name); meta.textContent = phase; },
      end() { job.hidden = true; job.replaceChildren(); },
    };
  }

  /** Runs `work` with the buttons held; a thrown error becomes a toast. */
  async function busyWith(name, work) {
    busy = true;
    render();
    const p = progress(name);
    try { return await work(p); }
    catch (e) {
      toast(e instanceof SampleFileError || e instanceof SwapInterrupted ? e.message : `${name}: ${e.message}`, "error");
      return undefined;
    } finally {
      p.end();
      busy = false;
      render();
    }
  }

  /** Reads the list from the Electribe. A temp file of an interrupted swap is dealt with first. */
  async function loadFromDevice() {
    const s = session();
    if (!s) return;
    await busyWith("Samples von der Electribe lesen", async p => {
      let got = await readDeviceSamples(s, (done, total) => p.step(`Lese Sample ${done} von ${total}`, done, total));
      if (got.temp) {
        const state = await inspectTemp(s);
        if (state === "finished") {
          const yes = await window.ui?.confirm({ title: "Ein Austausch auf der Karte ist unterbrochen", text: "Auf der Karte liegt die fertige neue Sample-Datei als Tauschdatei, der Austausch wurde nicht zu Ende gebracht. Jetzt fertigstellen?", confirmLabel: "Fertigstellen" });
          if (yes) {
            await finishTemp(s, q => p.step(q.phase, q.done, q.total));
            toast("Der Austausch ist fertig. " + RESTART, "ok");
            got = await readDeviceSamples(s);
          } else toast("Die Tauschdatei bleibt auf der Karte, bis du sie fertigstellst oder verwirfst.", "info");
        } else if (state === "broken") {
          const yes = await window.ui?.confirm({ title: "Eine unbrauchbare Tauschdatei liegt auf der Karte", text: "Der Rest eines unterbrochenen Vorgangs, ihr Inhalt ist nicht vollständig. Die Sample-Datei daneben ist unberührt. Tauschdatei löschen?", confirmLabel: "Löschen", danger: true });
          if (yes) await discardTemp(s);
        }
      }
      source = "device";
      base = got.header;
      parsed = got.parsed;
      removed = new Set();
      added = [];
      toast(`Von der Electribe gelesen: ${parsed.samples.length} Samples.`, "ok");
    });
  }

  async function saveToDevice() {
    const s = session();
    if (!s) { toast("Die Electribe ist nicht mehr verbunden. Verbinde sie neu und lies die Samples nochmal.", "error"); return; }
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    const rebuild = needsCompaction(parsed, plan);
    const yes = await window.ui?.confirm({
      title: "Änderung auf die Karte der Electribe schreiben?",
      text: `${added.length} neu, ${removed.size} entfernt. ${rebuild ? "Beim Entfernen baut die Electribe die Datei auf der Karte neu auf: erst als Tauschdatei, geprüft, dann ausgetauscht. Das dauert je nach Größe eine Weile, die Electribe nicht ausschalten und das Kabel nicht ziehen. " : ""}Eine Sicherung der Karte vorher schadet nicht. ${RESTART}`,
      confirmLabel: "Schreiben",
    });
    if (!yes) return;
    const ok = await busyWith("Auf die Karte schreiben", async p => {
      await writeDeviceChange(s, parsed, plan, q => p.step(q.phase, q.done, q.total));
      return true;
    });
    if (ok) {
      toast(`Auf die Karte geschrieben. ${RESTART}`, "ok");
      await loadFromDevice();
    } else if (session()) await loadFromDevice();
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
    if (source === "device") { saveToDevice(); return; }
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    const out = applyPlan(base, plan);
    saveFile(out, "e2sSample.all", { note: RESTART });
    load(out);
  });
  reset.addEventListener("click", () => { removed = new Set(); added = []; render(); });
  render();
  return { sessionChanged: render };
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
