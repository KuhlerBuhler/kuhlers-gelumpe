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

export function samplesFilePage(root, { device = null } = {}) {
  let source = "file";
  let busy = false;
  let base = null;
  let parsed = null;
  let removed = new Set();
  let added = [];
  // Both files come in through the design's upload field (ui-dropzone): click to pick or drop on it.
  const dropzone = (input, drag, hint) => el("label", { className: "ui-dropzone" }, [
    input,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t(drag) }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t(hint) }),
    el("span", { className: "ui-dropzone-files" }),
  ]);
  const pick = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-sf-file", accept: ".all,.ALL" });
  const wavs = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-sf-wav", accept: ".wav,.WAV,audio/wav", multiple: true, disabled: true });
  const fromDevice = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-device", textContent: t("sampleset.device.read"), disabled: true, onclick: () => loadFromDevice() });
  const save = el("button", { type: "button", className: "btn cee-primary", id: "cee-sf-save", textContent: t("common.save"), disabled: true });
  const job = el("div", { className: "ui-job", id: "cee-sf-job", hidden: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-sf-reset", textContent: t("sampleset.reset"), disabled: true });
  const summary = el("p", { className: "muted", id: "cee-sf-summary", role: "status" });
  const list = el("ul", { className: "ui-list cee-sf-list", id: "cee-sf-list", hidden: true });
  const intro = el("p", { className: "cee-sf-intro" }, [
    ...tNodes("sampleset.intro", { path: el("code", { textContent: "KORG/…/Sample/e2sSample.all" }), restart: restart() }),
  ]);
  const wavZone = dropzone(wavs, "sampleset.wav.drag", "sampleset.wav.hint");
  const actions = el("div", { className: "actions" }, [save, reset]);
  root.replaceChildren(intro, el("div", { className: "actions" }, [fromDevice]), dropzone(pick, "sampleset.drop.drag", "sampleset.drop.hint"), wavZone, job, summary, list, actions);

  const taken = () => new Set([...parsed.samples.filter(s => !removed.has(s.slot)).map(s => s.slot), ...added.map(a => a.slot)]);
  const dirty = () => removed.size > 0 || added.length > 0;

  const session = () => (device?.session && !device.session.sender.disconnected ? device.session : null);

  function render() {
    list.replaceChildren();
    fromDevice.disabled = busy || !session();
    pick.disabled = busy;
    wavs.disabled = !parsed || busy;
    wavZone.hidden = actions.hidden = !parsed;
    save.textContent = source === "device" ? t("sampleset.device.write") : t("common.save");
    save.disabled = reset.disabled = !dirty() || busy;
    list.hidden = !parsed?.samples.length && !added.length;
    if (!parsed) { summary.textContent = ""; return; }
    const kept = parsed.samples.filter(s => !removed.has(s.slot));
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    summary.textContent = (dirty() ? t("sampleset.summary.changed", { count: kept.length + added.length, size: size(plan.size), before: size(parsed.size) }) : t("sampleset.summary", { count: kept.length + added.length, size: size(plan.size) }));
    const rows = [
      ...parsed.samples.map(s => ({ ...s, state: removed.has(s.slot) ? "removed" : "kept" })),
      ...added.map(a => ({ slot: a.slot, name: a.name, rate: a.rate, bits: a.bits, channels: a.channels, frames: a.frames, length: a.bytes.length, problem: null, state: "new" })),
    ].sort((a, b) => a.slot - b.slot);
    for (const s of rows) {
      const button = el("button", { type: "button", className: "btn sm", textContent: s.state === "removed" ? t("sampleset.keep") : t("common.remove"), disabled: busy });
      button.dataset.slot = String(s.slot + 1);
      button.addEventListener("click", () => {
        if (s.state === "new") added = added.filter(a => a.slot !== s.slot);
        else if (removed.has(s.slot)) removed.delete(s.slot); else removed.add(s.slot);
        render();
      });
      const row = el("li", { className: "ui-row cee-sf-row" }, [
        el("span", { className: "ui-row-icon cee-sf-nr", textContent: String(s.slot + 1) }),
        el("span", { className: "ui-row-text" }, [
          el("span", { className: "ui-row-title cee-sf-name", textContent: s.name || t("sampleset.noName") }),
          s.problem ? null : el("span", { className: "ui-row-meta", textContent: `${format(s)}, ${seconds(s)}, ${size(s.length)}` }),
        ]),
        el("div", { className: "ui-row-actions" }, [
          s.problem ? pill("error", s.problem) : s.state === "new" ? pill("ok", t("sampleset.new")) : s.state === "removed" ? pill("warn", t("sampleset.removing")) : null,
          button,
        ]),
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
    await busyWith(t("sampleset.device.reading"), async p => {
      let got = await readDeviceSamples(s, (done, total) => p.step(t("sampleset.device.readStep", { done, total }), done, total));
      if (got.temp) {
        const state = await inspectTemp(s);
        if (state === "finished") {
          const yes = await window.ui?.confirm({ title: t("sampleset.temp.finished.title"), text: t("sampleset.temp.finished.text"), confirmLabel: t("sampleset.temp.finished.confirm") });
          if (yes) {
            await finishTemp(s, q => p.step(q.phase, q.done, q.total));
            toast(t("sampleset.temp.finishedDone", { restart: restart() }), "ok");
            got = await readDeviceSamples(s);
          } else toast(t("sampleset.temp.kept"), "info");
        } else if (state === "broken") {
          const yes = await window.ui?.confirm({ title: t("sampleset.temp.broken.title"), text: t("sampleset.temp.broken.text"), confirmLabel: t("sampleset.temp.broken.confirm"), danger: true });
          if (yes) await discardTemp(s);
        }
      }
      source = "device";
      base = got.header;
      parsed = got.parsed;
      removed = new Set();
      added = [];
      toast(t("sampleset.device.read.done", { count: parsed.samples.length }), "ok");
    });
  }

  async function saveToDevice() {
    const s = session();
    if (!s) { toast(t("sampleset.device.gone"), "error"); return; }
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    const rebuild = needsCompaction(parsed, plan);
    const yes = await window.ui?.confirm({
      title: t("sampleset.device.confirm.title"),
      text: t("sampleset.device.confirm.text", { added: added.length, removed: removed.size, rebuild: rebuild ? t("sampleset.device.confirm.rebuild") : "", restart: restart() }),
      confirmLabel: t("sampleset.device.confirm.label"),
    });
    if (!yes) return;
    const ok = await busyWith(t("sampleset.device.write"), async p => {
      await writeDeviceChange(s, parsed, plan, q => p.step(q.phase, q.done, q.total));
      return true;
    });
    if (ok) {
      toast(t("sampleset.device.written", { restart: restart() }), "ok");
      await loadFromDevice();
    } else if (session()) await loadFromDevice();
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
    if (source === "device") { saveToDevice(); return; }
    const plan = planChange(base, parsed, { remove: removed, add: added.map(a => ({ slot: a.slot, bytes: a.bytes })) });
    const out = applyPlan(base, plan);
    saveFile(out, "e2sSample.all", { note: restart() });
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
