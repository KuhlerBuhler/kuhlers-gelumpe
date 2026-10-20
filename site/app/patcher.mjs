/** The Patcher page: the user's own SYSTEM.VSB, BLECH patched on in the browser, checked in the emulator, then offered for download. Logic: src/patcher.mjs. */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { toast } from "./toast.mjs";
import { applyPatches } from "../../src/patch.mjs";
import { fetchUpdateFile, storeUpdateFile } from "../../src/usb-update.mjs";
import { buildOf } from "../../src/firmware.mjs";
import { wayOf, classify, convertStock, cardFolder, sampleFolder, loadBlechSet, itemsFor, checkName, checkDetail, checkProgress, clock, newFlow, step, allowed, verifiedReport, VERIFIED_URL, BLECH_FOLDER, DOOM_FOLDER, DOOM_FILES, hasDoom, VSB_SIZE, HACKTRIBE_PATCH_URL, BLECH_SET_URL, BLECH_SYNTH_SET_URL } from "../../src/patcher.mjs";

const STYLE = new URL("./patcher.css", import.meta.url).href;

/** Where the update test put the file, in the words of the device. */
const hintFor = folder => `Die gepatchte Datei liegt auf der Karte im Emulator unter KORG/${folder}/System. DATA UTILITY > SOFTWARE UPDATE, ENTER, danach neu starten.`;

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const tick = () => new Promise(r => setTimeout(r, 0));

/** What the verdict line says for a file that cannot be patched or is ready. */
function verdict(flow, items) {
  const { input } = flow;
  if (!input) return null;
  const size = input.size.toLocaleString("de-DE");
  switch (input.kind) {
    // A file the page takes says nothing: the user knows what was dropped, the button and the route say what comes next.
    case "hacktribe":
    case "synth":
    case "stock": return null;
    case "blech": return { tone: "ok", word: "Schon BLECH", text: "In dieser Datei steckt BLECH bereits, hier ist nichts mehr zu patchen." };
    case "partial": return { tone: "warn", word: "Teils gepatcht", text: `Die Datei trägt schon einen Teil von BLECH (${input.present.map(id => items.find(p => p.id === id)?.label ?? id).join(", ")}). Nimm die unveränderte Datei, damit alles zusammenpasst.` };
    case "wrong-size": return { tone: "error", word: "Keine SYSTEM.VSB", text: `Die Datei ist ${size} Byte groß, eine SYSTEM.VSB für 2.02 hat ${VSB_SIZE.toLocaleString("de-DE")}.` };
    default: return { tone: "error", word: "Nicht erkannt", text: `${input.reasons[0] ?? ""} Dieser Patcher ist für Hacktribe auf Korgs Sampler 2.02 gebaut.` };
  }
}

export function patcherPage(root, { emulator, show = () => {}, session = () => null }) {
  if (!document.querySelector("link[data-cee-patcher]")) {
    const css = el("link", { rel: "stylesheet", href: STYLE });
    css.setAttribute("data-cee-patcher", "");
    document.head.append(css);
  }

  let flow = newFlow();
  let original = null;          // the file as the user dropped it: what the trial runs, before the update
  let input = null;             // the bytes the patches go on: the dropped file, or Korg's original turned into Hacktribe's
  let stockFile = null;         // Korg's original as dropped, and what classify made of it, to go back to on the other route
  let passed = null;            // the patched copy that passed the check
  let applied = null;           // what applyPatches gave for it: the spans the check needs again for the thorough run
  let blech = null;             // the BLECH set (data/patches/blech.json) with its patches parsed, once loaded
  let hint = null;
  let usb = null;               // the file came over USB: { fromOriginal }; null for a dropped file (then the unpatched one goes to the card too)

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-file", accept: ".VSB,.vsb" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "SYSTEM.VSB hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "Deine Hacktribe-Datei oder Korgs Original 2.02 für electribe sampler oder electribe (blau)" }),
    el("span", { className: "ui-dropzone-files" }),
  ]);

  const usbGet = el("button", { type: "button", className: "btn primary", id: "cee-patch-usb-get", textContent: "Update auf Gerät" });
  const usbNote = el("p", { className: "muted", id: "cee-patch-usb-note", role: "status", hidden: true });
  const usbBox = el("section", { className: "cee-patch-usb", id: "cee-patch-usb" }, [
    el("h2", { className: "cee-patch-usb-title", textContent: "Update direkt über USB" }),
    el("p", { className: "cee-patch-lead", textContent: "Ist BLECH schon auf deiner Electribe, schließ sie nur per USB an und verbinde sie auf der Seite Gerät. Der Knopf holt die Firmware-Datei von der Karte, setzt das neueste BLECH drauf, prüft sie im Emulator und legt sie zurück. Am Gerät drückst du danach nur noch DATA UTILITY > SOFTWARE UPDATE." }),
    el("div", { className: "actions" }, [usbGet]),
    usbNote,
  ]);
  const usbPut = el("button", { type: "button", className: "btn primary", id: "cee-patch-usb-put", textContent: "Über USB aufs Gerät schreiben", hidden: true });
  const way = el("ol", { className: "cee-patch-way", id: "cee-patch-way" });
  way.setAttribute("aria-label", "Weg zur neuen Firmware");
  const verdictBox = el("div", { className: "cee-patch-verdict", id: "cee-patch-verdict", role: "status" });
  const synthSet = el("p", { className: "muted", id: "cee-patch-synth-set", hidden: true });
  const routeInputs = [["direct", "BLECH direkt (kein Hacktribe-Patch nötig)"], ["hacktribe", "BLECH mit Hacktribe (hacktribe-2.patch selbst mitbringen)"]].map(([value, text]) => {
    const radio = el("input", { type: "radio", name: "cee-patch-route", value });
    radio.addEventListener("change", () => radio.checked && chooseRoute(value));
    return { value, radio, label: el("label", { className: "ui-segmented-option" }, [radio, el("span", { textContent: text })]) };
  });
  const routeGroup = el("div", { className: "ui-segmented", id: "cee-patch-route-group" }, routeInputs.map(r => r.label));
  routeGroup.setAttribute("role", "radiogroup");
  routeGroup.setAttribute("aria-label", "Weg zu BLECH");
  const routeBox = el("div", { className: "cee-patch-route", id: "cee-patch-route", hidden: true }, [
    routeGroup,
    el("p", { className: "muted", id: "cee-patch-route-note", textContent: "Hacktribe ergänzt Filter für den Synth, zusätzliche Effekte und SysEx zum Lesen und Schreiben im RAM, das der Live-Modus des Editors braucht." }),
  ]);
  const patchInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-hacktribe-file" });
  const patchDrop = el("label", { className: "ui-dropzone" }, [
    patchInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "hacktribe-2.patch hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "Die Datei, die du von Hacktribe heruntergeladen hast" }),
  ]);
  const patchBox = el("div", { className: "cee-patch-needs", id: "cee-patch-needs", hidden: true }, [
    el("p", {}, ["Dafür braucht es ", el("a", { className: "cee-text-link", id: "cee-patch-hacktribe-link", href: HACKTRIBE_PATCH_URL, target: "_blank", rel: "noopener noreferrer", textContent: "hacktribe-2.patch" }),
      ". Wir können sie nicht mitliefern, ihre Lizenz erlaubt keine Weitergabe. Lade sie bei Hacktribe herunter und zieh sie hierher; sie wird nur in deinem Browser angewendet."]),
    patchDrop,
  ]);
  const run = el("button", { type: "button", className: "btn primary", id: "cee-patch-run", textContent: "Patchen und im Emulator prüfen", hidden: true });
  const bar = el("div", { className: "ui-progress cee-patch-bar", id: "cee-patch-bar", hidden: true });
  const groupList = el("ul", { className: "cee-patch-groups", id: "cee-patch-groups", hidden: true });
  const checkList = el("ul", { className: "ui-list", id: "cee-patch-checks" });
  const checksBox = el("details", { className: "ui-details", id: "cee-patch-details", hidden: true }, [el("summary", { id: "cee-patch-details-title" }), el("div", { className: "ui-details-body" }, [checkList])]);
  const note = el("p", { className: "muted", id: "cee-patch-note", role: "status", hidden: true });
  const download = el("button", { type: "button", className: "btn primary", id: "cee-patch-download", textContent: "SYSTEM.VSB herunterladen", disabled: true });
  const afraid = el("button", { type: "button", className: "btn", id: "cee-patch-afraid", textContent: "Ich hab angst dass mein Gerät kaputt geht", disabled: true });
  const thorough = el("button", { type: "button", className: "btn", id: "cee-patch-thorough", textContent: "Gründlich prüfen", hidden: true });
  const result = el("div", { className: "actions cee-patch-result", id: "cee-patch-result", hidden: true }, [usbPut, download, afraid, thorough]);
  const done = el("section", { className: "cee-patch-done", id: "cee-patch-done", hidden: true });

  root.replaceChildren(el("div", { className: "cee-patch" }, [
    el("h1", { className: "cee-patch-title", textContent: "Firmware patchen" }),
    el("p", { className: "cee-patch-lead", textContent: "Zieh deine eigene SYSTEM.VSB hierher. Es wird nichts hochgeladen, gepatcht wird in deinem Browser. Eine fertige Firmware gibt es hier nie, nur deine eigene mit BLECH drauf." }),
    el("p", { className: "cee-patch-lead" }, ["Falls danach etwas nicht startet: ", el("a", { className: "cee-text-link", id: "cee-patch-rescue", href: "#rescue", textContent: "Rettung" }), " zeigt den dokumentierten Weg zurück."]),
    way, usbBox, drop, verdictBox, synthSet, routeBox, patchBox, run, bar, note, groupList, checksBox, result, done,
  ]));

  async function loadPatches(build = input ? buildOf(input) : "hacktribe") {
    const setUrl = build === "synth" ? BLECH_SYNTH_SET_URL : BLECH_SET_URL;
    if (blech?.setUrl === setUrl) return blech;
    blech = { ...await loadBlechSet(async url => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${url} ließ sich nicht laden.`);
      return res.json();
    }, setUrl), setUrl };
    return blech;
  }

  /** The list of copies that passed already; without it every copy is checked. */
  async function loadVerified() {
    try {
      const res = await fetch(VERIFIED_URL);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  }

  const dispatch = event => { flow = step(flow, event); render(); };

  // The emulator service reports how far the check is (tools/emu/progress.py); the page polls it while the check request runs.
  // Until the first report is in, or with a service that has none, the bar just runs without a value.
  let toasted = null;
  let startedAt = 0;
  let latest = null;
  const showProgress = () => {
    const p = checkProgress(latest);
    const elapsed = clock(Date.now() - startedAt);
    note.textContent = p ? `${p.text}, ${elapsed}` : `Prüfung läuft, ${elapsed}`;
    window.ui?.setProgress(bar, p ? p.value : null, "Prüfung im Emulator");
    groupList.hidden = !p;
    groupList.replaceChildren(...(p?.groups ?? []).map(g => {
      const li = el("li", {}, [el("span", { textContent: g.name }), el("span", { className: "cee-patch-group-state", textContent: g.text })]);
      li.dataset.state = g.state;
      return li;
    }));
  };
  let clockTimer = null;
  const stopClock = () => { if (clockTimer) { clearInterval(clockTimer); clockTimer = null; } };
  function startClock() {
    startedAt = Date.now();
    latest = null;
    clockTimer = setInterval(showProgress, 1000);
    showProgress();
  }

  function renderProgress(can) {
    const checking = flow.phase === "checking";
    if (checking && !clockTimer) startClock();
    if (!checking) { stopClock(); groupList.hidden = true; }
    const passed_ = flow.phase === "passed" || flow.phase === "downloaded";
    bar.hidden = !(can.busy || passed_);
    bar.dataset.tone = passed_ ? "ok" : "";
    if (passed_) window.ui?.setProgress(bar, 100, "Prüfung im Emulator", { valueText: "bestanden" });
    else if (flow.phase === "patching") window.ui?.setProgress(bar, null, "Patches anwenden");
    const failed = flow.report && !flow.report.ok ? failureLine(flow.report) : null;
    note.hidden = !can.busy;
    if (flow.phase === "patching") note.textContent = "Patches anwenden";
    // A result is told once, as a toast; the line is only for the run itself.
    const result = passed_ ? ["Im Emulator bestanden.", "ok"] : can.busy ? null : flow.error ? [flow.error, "error"] : failed ? [failed, "error"] : null;
    const key = result ? `${flow.phase}|${result[0]}` : null;
    if (key !== toasted) { toasted = key; if (result) toast(result[0], result[1]); }
  }

  /** One short line for a check that ran and did not pass; the list of all checks sits behind the disclosure. */
  function failureLine(report) {
    const bad = report.checks.filter(c => !c.ok);
    if (!bad.length) return "Nicht bestanden.";
    return `Nicht bestanden: ${checkName(bad[0].id)}${bad.length > 1 ? ` und ${bad.length - 1} weitere` : ""}.`;
  }

  function render() {
    const can = allowed(flow);
    way.replaceChildren(...wayOf(flow).map((s, i) => {
      const li = el("li", { className: "cee-patch-way-step" }, [el("span", { className: "cee-patch-way-n", textContent: s.state === "done" ? "✓" : String(i + 1) }), el("span", { textContent: s.label })]);
      li.dataset.state = s.state;
      if (s.state === "current") li.setAttribute("aria-current", "step");
      return li;
    }));
    const v = verdict(flow, blech?.items ?? []);
    verdictBox.replaceChildren(...(v ? [pill(v.tone, v.word), el("span", { textContent: ` ${v.text}` }), ...(v.link ? [" ", el("a", { className: "cee-text-link", href: v.link[1], target: "_blank", rel: "noopener noreferrer", textContent: v.link[0] })] : [])] : []));
    verdictBox.hidden = !v;
    routeBox.hidden = flow.origin !== "stock";
    synthSet.hidden = flow.origin !== "synth";
    if (!synthSet.hidden) synthSet.textContent = `Synth-Satz: ${itemsFor(blech, "synth").map(p => p.label).join(", ")}. BLECH-Menü, Plugins und Startbild-Editor sind noch nicht enthalten.`;
    for (const r of routeInputs) { r.radio.checked = r.value === flow.route; r.radio.disabled = can.busy; }
    patchBox.hidden = flow.phase !== "needs-patch";
    patchInput.disabled = can.busy;
    run.hidden = !(flow.phase === "ready" || flow.phase === "failed" || can.busy);
    run.disabled = !can.patch;
    run.textContent = flow.phase === "failed" ? "Noch einmal patchen und prüfen" : "Patchen und im Emulator prüfen";
    fileInput.disabled = can.busy;

    renderProgress(can);

    const checks = flow.report?.checks ?? [];
    checksBox.hidden = !checks.length;
    document.getElementById("cee-patch-details-title").textContent = `Alle Prüfungen des Emulators (${checks.length})`;
    checkList.replaceChildren(...checks.map(c => el("li", { className: "ui-row" }, [
      pill(c.ok ? "ok" : "error", c.ok ? "bestanden" : "nicht bestanden"), el("strong", { textContent: ` ${checkName(c.id)}` }), el("span", { className: "ui-break muted", textContent: ` ${checkDetail(c.detail)}` }),
    ])));

    result.hidden = !can.download;
    usbPut.hidden = !session();
    usbPut.disabled = !can.download;
    usbGet.disabled = can.busy;
    thorough.hidden = !(flow.report?.checks ?? []).some(c => c.id === "quick");
    download.disabled = !can.download;
    afraid.disabled = !can.test;
    done.hidden = flow.phase !== "downloaded";
  }

  async function pick(file) {
    usb = null;
    fileInput.value = "";           // choosing the same path again, after it changed, must still fire
    await take(new Uint8Array(await file.arrayBuffer()));
  }

  async function take(bytes) {
    let kind;
    try {
      kind = await classify(bytes, (await loadPatches(buildOf(bytes))).patches);
    } catch (e) {
      kind = { kind: "unknown", size: bytes.length, reasons: [e.message], present: [] };
    }
    input = bytes;
    original = bytes;
    stockFile = kind.kind === "stock" ? { bytes, kind } : null;
    passed = null;
    dispatch({ type: "input", input: kind });
  }

  function chooseRoute(route) {
    if (!stockFile || route === flow.route || allowed(flow).busy) return;
    input = stockFile.bytes;
    passed = null;
    dispatch({ type: "route", route, input: stockFile.kind });
  }

  async function pickPatch(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    patchInput.value = "";
    await tick();
    const res = await convertStock(stockFile.bytes, bytes);
    if (!res.ok) { dispatch({ type: "convert-failed", message: res.reason }); return; }
    input = res.bytes;
    passed = null;
    dispatch({ type: "converted", input: { kind: "hacktribe", size: res.bytes.length, reasons: [], present: [] }, detail: `SHA-256 ${res.sha256.slice(0, 12)}…` });
  }

  patchInput.addEventListener("change", () => {
    const file = patchInput.files?.[0];
    if (file && flow.phase === "needs-patch") pickPatch(file);
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) pick(file);
  });

  run.addEventListener("click", () => patchAndCheck());

  /** Applies the set to the input and checks the copy in the emulator; afterwards `passed` holds it when it passed. */
  async function patchAndCheck() {
    if (!allowed(flow).patch) return;
    const build = buildOf(input);
    dispatch({ type: "patching", patches: blech ? itemsFor(blech, build) : [] });
    passed = null;
    try {
      const { patches: list, items: all } = await loadPatches();
      const items = itemsFor({ items: all, patches: list }, build);
      await tick();
      const res = await applyPatches(input, list);
      if (!res.ok) {
        for (const p of items) {
          const own = res.reasons.filter(r => r.startsWith(`${p.id}:`)).map(r => r.slice(p.id.length + 2));
          dispatch({ type: "patch", id: p.id, ok: false, detail: own.length ? own.join(" ") : "wartet auf die anderen" });
        }
        throw new Error(`Die Patches ließen sich nicht anwenden: ${res.reasons.join(" ")}`);
      }
      for (const p of items) {
        const n = res.spans.filter(s => s.patch === p.id).length;
        dispatch({ type: "patch", id: p.id, ok: true, detail: `${n} Stelle${n === 1 ? "" : "n"} geschrieben` });
      }
      dispatch({ type: "checking" });
      await tick();
      // a copy nobody checked before gets the quick check (start and rescue paths); the thorough one is a button after it
      const report = await verifiedReport(input, res.bytes, await loadVerified())
        ?? await emulator.check(input, res.bytes, res.allow, res.allowCode, snapshot => { latest = snapshot; showProgress(); }, { quick: true });
      applied = res;
      if (report.ok) passed = res.bytes;
      dispatch({ type: "checked", report });
    } catch (e) {
      dispatch({ type: "error", message: e.message });
    }
  }

  thorough.addEventListener("click", async () => {
    if (!passed || !applied) return;
    const copy = passed;
    dispatch({ type: "recheck" });
    try {
      const report = await emulator.check(input, copy, applied.allow, applied.allowCode, snapshot => { latest = snapshot; showProgress(); });
      if (!report.ok) passed = null;
      dispatch({ type: "checked", report });
    } catch (e) {
      passed = null;
      dispatch({ type: "error", message: e.message });
    }
  });

  function buildDone() {
    const folder = cardFolder(flow.origin);
    const old = sampleFolder(flow.origin);
    const moves = blech?.items.some(p => p.id === "blechtribe");
    done.replaceChildren(
      el("h2", { textContent: "Viel Spaß beim BLECHEN" }),
      el("ol", { className: "cee-patch-guide" }, [
        el("li", { textContent: "Sichere die SD-Karte, am besten komplett auf den Rechner kopieren." }),
        moves ? el("li", { id: "cee-patch-guide-copy" }, [
          "Kopiere auf der Karte den Ordner ", el("code", { textContent: old }), " nach ", el("code", { textContent: `KORG/${BLECH_FOLDER}/` }),
          ". Kopieren, nicht umbenennen: Nach dem Update liest BLECH seine Dateien aus ", el("code", { textContent: `KORG/${BLECH_FOLDER}/` }),
          ", deine Samples und Patterns findet es nur dort. Der alte Ordner bleibt, wie er ist.",
        ]) : null,
        blech && hasDoom(blech) ? el("li", { id: "cee-patch-guide-doom" }, [
          "Für Doom (SHIFT + TAP beim Einschalten): ",
          ...DOOM_FILES.flatMap((file, i) => [i ? " und " : "", el("a", { className: "cee-text-link", href: file, download: file.split("/").pop(), textContent: file.split("/").pop() })]),
          " laden und auf der Karte nach ", el("code", { textContent: DOOM_FOLDER }), " legen. ",
          el("a", { className: "cee-text-link", id: "cee-patch-doom-licences", href: "third_party/doom/README.md", target: "_blank", rel: "noopener noreferrer", textContent: "Quellen und Lizenzen" }), ".",
        ]) : null,
        el("li", { id: "cee-patch-guide-vsb" }, [
          "Kopiere die heruntergeladene ", el("code", { textContent: "SYSTEM.VSB" }), " nach ", el("code", { textContent: folder }),
          ", also in den Ordner der Firmware, die jetzt auf dem Gerät läuft", moves ? ", nicht nach blechtribe" : "", ". Die Datei dort wird ersetzt.",
        ]),
        el("li", { textContent: "Lege die Karte bei ausgeschaltetem Gerät ein und schalte es ein. Nimm das Netzteil oder frische Batterien." }),
        flow.origin === "synth" ? el("li", { textContent: "Im Ordner KORG/electribe/System darf nur SYSTEM.VSB liegen. BOOT.VSB, USER.VSB und PCM.VSB gehören dort nicht hinein." }) : null,
        el("li", { textContent: "Gehe unter DATA UTILITY auf SOFTWARE UPDATE und drücke ENTER. Starte das Gerät neu, wenn es dich auffordert." }),
        el("li", { textContent: "Schalte das Gerät während des Updates nicht aus." }),
      ].filter(Boolean)),
      el("p", { className: "cee-patch-exit" }, [el("strong", { textContent: "Notausgang: " }), "Halte EXIT beim Einschalten gedrückt, dann startet das Gerät ohne die BLECH-Funktionen. Wenn das nicht reicht: ", el("a", { href: "#rescue", textContent: "Rettung" }), "."]),
    );
  }

  const percent = (done, total) => Math.round(done * 100 / total);

  /** The update file from the card into the page. False when it cannot go on by itself (no ORIGINAL.BIN beside a patched file). */
  async function fetchFromDevice(s) {
    const got = await fetchUpdateFile(s, (done, total) => { usbNote.textContent = `Vom Gerät lesen, ${percent(done, total)} %`; });
    usb = { fromOriginal: got.fromOriginal };
    await take(got.bytes);
    if (flow.input?.kind === "blech") {
      usbNote.textContent = "Auf der Karte liegt schon eine gepatchte SYSTEM.VSB und keine ORIGINAL.BIN daneben. Zieh deine unveränderte SYSTEM.VSB oben hinein und schreib sie nach der Prüfung über USB aufs Gerät; sie kommt dann als ORIGINAL.BIN mit auf die Karte, jedes weitere Update startet von ihr.";
      return false;
    }
    return true;
  }

  /** The checked copy onto the card; the first time the unpatched file goes beside it as ORIGINAL.BIN. */
  async function storeToDevice(s) {
    await storeUpdateFile(s, passed, usb?.fromOriginal ? null : original, (done, total) => { usbNote.textContent = `Aufs Gerät schreiben, ${percent(done, total)} %`; });
    usbNote.textContent = "Fertig. Auf der Karte liegt die neue SYSTEM.VSB. Am Gerät DATA UTILITY > SOFTWARE UPDATE, ENTER, danach neu starten. Während des Updates nicht ausschalten.";
    usb = { fromOriginal: true };
    toast("Über USB geschrieben.", "ok");
  }

  usbGet.addEventListener("click", async () => {
    const s = session();
    if (!s) { toast("Erst auf der Seite Gerät die Electribe verbinden.", "error"); return; }
    usbGet.disabled = true;
    usbNote.hidden = false;
    try {
      if (!await fetchFromDevice(s)) return;
      if (flow.phase !== "ready") { usbNote.textContent = "Die Datei vom Gerät braucht noch eine Entscheidung, siehe unten."; return; }
      usbNote.textContent = "Patchen und im Emulator prüfen, das dauert ein paar Minuten.";
      await patchAndCheck();
      if (!passed) { usbNote.textContent = "Die Prüfung im Emulator ist nicht bestanden, auf das Gerät kam nichts. Details unten."; return; }
      await storeToDevice(s);
    } catch (e) {
      usbNote.hidden = true;
      toast(e.message, "error");
    } finally {
      usbGet.disabled = allowed(flow).busy;
    }
  });

  usbPut.addEventListener("click", async () => {
    const s = session();
    if (!passed || !allowed(flow).download) return;
    if (!s) { toast("Erst auf der Seite Gerät die Electribe verbinden.", "error"); return; }
    usbPut.disabled = true;
    usbNote.hidden = false;
    try {
      await storeToDevice(s);
    } catch (e) {
      usbNote.hidden = true;
      toast(e.message, "error");
    } finally {
      usbPut.disabled = !allowed(flow).download;
    }
  });

  download.addEventListener("click", () => {
    if (!passed || !allowed(flow).download) return;
    const a = el("a", { href: URL.createObjectURL(new Blob([passed], { type: "application/octet-stream" })), download: "SYSTEM.VSB" });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
    dispatch({ type: "downloaded" });
    buildDone();
  });

  function showHint(folder) {
    hint?.remove();
    const close = el("button", { type: "button", className: "btn icon", id: "cee-patch-hint-close", ariaLabel: "Hinweis schließen", title: "Hinweis schließen" }, [icon("x")]);
    hint = el("div", { className: "cee-patch-hint", id: "cee-patch-hint", role: "note" }, [el("p", { textContent: hintFor(folder) }), close]);
    close.addEventListener("click", () => { hint.remove(); hint = null; });
    document.getElementById("cee-area-emu").prepend(hint);
  }

  afraid.addEventListener("click", async () => {
    if (!passed || !allowed(flow).test) return;
    afraid.disabled = true;
    try {
      showHint(await emulator.rehearseUpdate(original, passed));
      show("emu");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      afraid.disabled = !allowed(flow).test;
    }
  });

  render();
}
