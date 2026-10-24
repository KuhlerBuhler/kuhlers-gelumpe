/** The Patcher page: the user's own SYSTEM.VSB, BLECH patched on in the browser, checked in the emulator, then offered for download. Logic: src/patcher.mjs. */
import { e2Outline } from "./e2-art.mjs";
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { applyPatches } from "../../src/patch.mjs";
import { applyPatchFile, parsePatchFile } from "../../src/patchfile.mjs";
import { NEWS } from "../../data/news.mjs";
import { fetchUpdateFile, storeUpdateFile } from "../../src/usb-update.mjs";
import { buildOf } from "../../src/firmware.mjs";
import { wayOf, classify, convertStock, cardFolder, sampleFolder, loadBlechSet, itemsFor, checkName, checkDetail, checkProgress, clock, newFlow, step, allowed, verifiedReport, VERIFIED_URL, BLECH_FOLDER, DOOM_FOLDER, DOOM_FILES, hasDoom, VSB_SIZE, HACKTRIBE_PATCH_URL, BLECH_SET_URL, BLECH_SYNTH_SET_URL } from "../../src/patcher.mjs";

const STYLE = new URL("./patcher.css", import.meta.url).href;

/** Where the update test put the file, in the words of the device. */
const hintFor = folder => `Die gepatchte Datei liegt auf der Karte im Emulator unter KORG/${folder}/System. Am Gerät Menü -> DATA UTILITY -> SOFTWARE UPDATE, MENU drücken, danach neu starten.`;

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
    case "blech": return { tone: "ok", word: "Schon BLECHTRIBE", text: "Auf dieser Datei ist BLECHTRIBE schon drauf. Nimm deine unveränderte SYSTEM.VSB, zum Beispiel die Sicherung vom Schreibtisch." };
    case "partial": return { tone: "warn", word: "Teils gepatcht", text: `Diese Datei wurde schon teilweise verändert (${input.present.map(id => items.find(p => p.id === id)?.label ?? id).join(", ")}). Nimm deine unveränderte SYSTEM.VSB, zum Beispiel die Sicherung vom Schreibtisch.` };
    case "wrong-size": return { tone: "error", word: "Keine Firmware", text: `Das ist keine Firmware-Datei (${size} statt ${VSB_SIZE.toLocaleString("de-DE")} Byte). Nimm die SYSTEM.VSB aus dem Ordner KORG › dein Ordner › System auf der SD-Karte.` };
    default: return { tone: "error", word: "Nicht erkannt", text: `Diese Firmware kennt der Patcher nicht. Er braucht Hacktribe 2.02 oder Korgs Original 2.02. Grund: ${input.reasons[0] ?? "unbekannt"}` };
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
  let blech = null;             // the BLECH set (data/patches/blech.json) with its patches parsed, once loaded
  let ownPatch = null;          // a BLECH.patch the user brought instead of the set of this version: { bytes, file }
  let hint = null;
  let usb = null;               // the file came over USB: { fromOriginal }; null for a dropped file (then the unpatched one goes to the card too)

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-file", accept: ".VSB,.vsb" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "SYSTEM.VSB hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "Deine Hacktribe-Datei oder Korgs Original 2.02 für electribe sampler oder electribe (blau)" }),
    el("span", { className: "ui-dropzone-files" }),
  ]);

  // Korg's System Updater holds the SYSTEM.VSB; in the app the link opens in the browser (src-tauri/src/main.rs).
  const korgCard = (device, name, url) => {
    const out = icon("popout");
    out.classList.add("cee-device-card-out");
    const a = el("a", { className: "cee-entry-step cee-device-card", id: `cee-patch-korg-${device}`, href: url, target: window.__GELUMPE_APP ? "_self" : "_blank", rel: "noopener noreferrer" }, [
      e2Outline(name), el("span", { className: "cee-device-card-text" }, [el("strong", { textContent: name }), el("span", { textContent: "System Updater bei Korg laden" })]), out,
    ]);
    a.dataset.device = device;
    return el("li", {}, [a]);
  };
  const korg = el("div", { className: "cee-patch-korg", id: "cee-patch-korg" }, [
    el("p", { className: "cee-patch-lead" }, ["Deine ", el("code", { textContent: "SYSTEM.VSB" }), " liegt auf der SD-Karte der Electribe, im Ordner ", el("code", { textContent: "KORG/…/System/" }), ". Hast du keine, lad Korgs System Updater 2.02, darin steckt sie."]),
    el("ul", { className: "cee-entry-steps", id: "cee-patch-firmware" }, [
      korgCard("red", "Electribe 2 Sampler (rot)", "https://www.korg.com/us/support/download/product/0/368/#software"),
      korgCard("blue", "Electribe 2 (blau)", "https://www.korg.com/us/support/download/product/0/367/#software"),
    ]),
  ]);
  const usbGet = el("button", { type: "button", className: "btn", id: "cee-patch-usb-get", textContent: "Update auf Gerät" });
  const usbNote = el("p", { className: "muted", id: "cee-patch-usb-note", role: "status", hidden: true });
  const usbBox = el("section", { className: "cee-patch-usb", id: "cee-patch-usb" }, [
    el("h2", { className: "cee-patch-usb-title", textContent: "Update direkt über USB" }),
    el("p", { className: "cee-patch-lead", textContent: "Ist BLECHTRIBE schon auf deiner Electribe, schließ sie nur per USB an und verbinde sie auf der Seite Gerät. Der Knopf holt die Firmware-Datei von der Karte, setzt das neueste BLECHTRIBE drauf, prüft sie im Emulator und legt sie zurück. Am Gerät gehst du danach nur noch auf Menü -> DATA UTILITY -> SOFTWARE UPDATE." }),
    el("div", { className: "actions" }, [usbGet]),
  ]);
  const usbPut = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-usb-put", textContent: "Über USB aufs Gerät schreiben", hidden: true });
  const way = el("ol", { className: "cee-patch-way", id: "cee-patch-way" });
  way.setAttribute("aria-label", "Weg zur neuen Firmware");
  // What the dropped file is not, said in the toast; the box only keeps it for screen readers and tests.
  const verdictBox = el("div", { className: "cee-patch-verdict ui-sr-only", id: "cee-patch-verdict", role: "status" });
  let toldVerdict = "";
  const synthSet = el("p", { className: "muted", id: "cee-patch-synth-set", hidden: true });
  // Step 2 chooses what goes on the file: BLECHTRIBE of this version or an own BLECH.patch, and on Korg's original Hacktribe as well.
  const release = NEWS[0].version.split(".").slice(0, 2).join(".");
  const useLatest = el("input", { type: "checkbox", id: "cee-patch-latest", checked: true });
  const blechInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-blech-file", accept: ".patch", disabled: true });
  const blechInfo = el("span", { className: "ui-dropzone-files", id: "cee-patch-blech-info" });
  const blechDrop = el("label", { className: "ui-dropzone", id: "cee-patch-blech-drop" }, [
    blechInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "BLECH.patch hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "Eine andere Version von BLECHTRIBE, als Patch-Datei" }),
    blechInfo,
  ]);
  const blechBox = el("section", { className: "cee-patch-choice", id: "cee-patch-blech" }, [
    el("label", { className: "cee-check" }, [useLatest, el("span", { textContent: `Nutze die neueste Version von BLECHTRIBE (${release})` })]),
    blechDrop,
  ]);
  const withHacktribe = el("input", { type: "checkbox", id: "cee-patch-hacktribe-use" });
  withHacktribe.addEventListener("change", () => chooseRoute(withHacktribe.checked ? "hacktribe" : "direct"));
  const routeBox = el("section", { className: "cee-patch-choice", id: "cee-patch-route", hidden: true }, [
    el("label", { className: "cee-check" }, [withHacktribe, el("span", { textContent: "Patche auch Hacktribe" })]),
    el("p", { className: "muted", id: "cee-patch-route-note", textContent: "Hacktribe ergänzt Filter für den Synth und zusätzliche Effekte. Den Live-Modus des Editors bringt BLECHTRIBE selbst mit." }),
  ]);
  const patchInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-hacktribe-file" });
  const patchDrop = el("label", { className: "ui-dropzone" }, [
    patchInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "hacktribe-2.patch hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "Die Datei, die du von Hacktribe heruntergeladen hast" }),
  ]);
  const patchBox = el("div", { className: "cee-patch-needs", id: "cee-patch-needs" }, [
    el("p", {}, ["Dafür braucht es ", el("a", { className: "cee-text-link", id: "cee-patch-hacktribe-link", href: HACKTRIBE_PATCH_URL, target: "_blank", rel: "noopener noreferrer", textContent: "hacktribe-2.patch" }),
      ". Wir können sie nicht mitliefern, ihre Lizenz erlaubt keine Weitergabe. Lade sie bei Hacktribe herunter und zieh sie hierher; sie wird nur in deinem Browser angewendet."]),
    patchDrop,
  ]);
  routeBox.append(patchBox);
  const run = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-run", textContent: "Patchen und testen", hidden: true });
  // How much of the emulator test runs: none (with consent), the quick one of today, or the full run that once took 90 minutes.
  const TESTS = [
    ["none", "Kein Test", "Die Datei wird nur gepatcht. Ob sie startet, siehst du erst am Gerät."],
    ["quick", "Schneller Test", "Der Emulator startet die neue Datei und prüft Start, Update-Abfrage, Startmodi und Notschalter. Ein paar Minuten."],
    ["full", "Voller Test", "Dazu alle Prüfungen des Emulators an jedem Patch. Kann auf langsamen Rechnern über eine Stunde dauern."],
  ];
  let testChoice = "quick";
  const testInputs = TESTS.map(([value, text]) => {
    const radio = el("input", { type: "radio", name: "cee-patch-test", value, checked: value === testChoice });
    radio.addEventListener("change", () => { if (radio.checked) { testChoice = value; render(); } });
    return { value, radio, label: el("label", { className: "ui-segmented-option" }, [radio, el("span", { textContent: text })]) };
  });
  const testGroup = el("div", { className: "ui-segmented", id: "cee-patch-test" }, testInputs.map(t => t.label));
  testGroup.setAttribute("role", "radiogroup");
  testGroup.setAttribute("aria-label", "Test im Emulator");
  const testNote = el("p", { className: "muted", id: "cee-patch-test-note" });
  const consent = el("input", { type: "checkbox", id: "cee-patch-consent" });
  consent.addEventListener("change", () => render());
  const consentBox = el("label", { className: "cee-patch-consent", id: "cee-patch-consent-box", hidden: true }, [consent,
    el("span", { textContent: "Ich kenne die Folgen: Startet die Datei nicht, weil beim Patchen etwas schiefging oder BLECHTRIBE einen Fehler hat, bin ich selbst verantwortlich. Keine Haftung." })]);
  const testBox = el("div", { className: "cee-patch-test-box", id: "cee-patch-test-box" }, [el("h2", { className: "cee-patch-usb-title", textContent: "Test im Emulator" }), testGroup, testNote, consentBox]);
  const planList = el("ul", { className: "cee-patch-plan", id: "cee-patch-plan" });
  const plan = el("div", { className: "cee-patch-plan-box" }, [
    el("p", { className: "cee-patch-lead", textContent: "Diese Patches kommen auf deine Firmware:" }),
    planList,
  ]);
  const bar = el("div", { className: "ui-progress cee-patch-bar", id: "cee-patch-bar", hidden: true });
  const groupList = el("ul", { className: "cee-patch-groups", id: "cee-patch-groups", hidden: true });
  const checkList = el("ul", { className: "ui-list", id: "cee-patch-checks" });
  const checksBox = el("details", { className: "ui-details", id: "cee-patch-details", hidden: true }, [el("summary", { id: "cee-patch-details-title" }), el("div", { className: "ui-details-body" }, [checkList])]);
  const note = el("p", { className: "muted", id: "cee-patch-note", role: "status", hidden: true });
  const download = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-download", textContent: "Speichern", disabled: true });
  // Step 4 names where the file goes before anything is saved: big, so it can be read off while copying.
  const targetPath = el("p", { className: "cee-patch-path", id: "cee-patch-path" });
  // Before the copy goes onto the device: what to do when it does not start (in step 1 only a file is loaded, nothing can break).
  const untested = el("span", { id: "cee-patch-untested", hidden: true, textContent: "Diese Datei ist nicht getestet. Halt beim ersten Start EXIT bereit: damit startet die Electribe ohne die Patches. " });
  const after = el("p", { className: "cee-note", id: "cee-patch-after" }, [
    untested,
    "Falls danach etwas nicht startet: ", el("a", { className: "cee-text-link", id: "cee-patch-rescue", href: "#rescue", textContent: "Rettung" }), " zeigt den dokumentierten Weg zurück.",
  ]);
  const target = el("div", { className: "cee-patch-target", id: "cee-patch-target" }, [
    el("p", { className: "cee-patch-lead", textContent: "Die neue Datei gehört auf die SD-Karte der Electribe, hierhin:" }),
    targetPath,
    after,
  ]);
  const afraid = el("button", { type: "button", className: "btn", id: "cee-patch-afraid", textContent: "Ich hab Angst, dass mein Gerät kaputt geht", disabled: true });
  const result = el("div", { className: "actions cee-patch-result", id: "cee-patch-result", hidden: true }, [usbPut, download, afraid]);
  const done = el("section", { className: "cee-patch-done", id: "cee-patch-done", hidden: true });

  // One panel per step of the way; Zurück and Weiter move between them, the flow decides how far Weiter may go.
  const panels = [
    [usbBox, el("p", { className: "cee-patch-or", id: "cee-patch-or", textContent: "Wenn nicht:" }), drop, verdictBox, korg],
    [blechBox, routeBox, plan, synthSet],
    [testBox, bar, note, groupList, checksBox],
    [target, result, done],
  ].map((children, i) => el("div", { className: "cee-patch-panel", id: `cee-patch-step-${i + 1}`, tabIndex: -1, hidden: i > 0 }, children));
  const back = el("button", { type: "button", className: "btn", id: "cee-patch-back", textContent: "Zurück", hidden: true });
  const next = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-next", textContent: "Weiter", disabled: true });
  let view = 0;

  root.replaceChildren(el("div", { className: "cee-patch" }, [
    el("h1", { className: "cee-patch-title ui-sr-only", textContent: "Firmware Patcher" }),
    way,
    usbNote,
    ...panels,
    el("div", { className: "cee-patch-nav", id: "cee-patch-nav" }, [back, next, run]),
  ]));

  /** The furthest step the flow allows: a file taken opens step 2, the patches chosen step 3 (test and run), a passed copy step 4. */
  function reach() {
    const p = flow.phase;
    if (p === "passed" || p === "downloaded") return 3;
    if (p === "needs-patch") return 1;
    if (p === "ready" || p === "failed" || p === "patching" || p === "checking") return useLatest.checked || ownPatch ? 2 : 1;
    return 0;
  }

  function go(to) {
    view = to;
    render();
    panels[view].focus({ preventScroll: true });
    panels[view].scrollIntoView?.({ block: "nearest" });
  }
  back.addEventListener("click", () => { if (view > 0 && !allowed(flow).busy) go(view - 1); });
  next.addEventListener("click", () => { if (view < reach() && !allowed(flow).busy) go(view + 1); });

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

  const dispatch = event => {
    flow = step(flow, event);
    // A run shows its check; a new file or a failed patch goes back as far as the flow still allows.
    if (allowed(flow).busy) view = 2;
    render();
  };

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
    // an untested copy has no bar and no "bestanden": nothing ran
    const passed_ = (flow.phase === "passed" || flow.phase === "downloaded") && !flow.untested;
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
    if (!bad.length) return "Die Prüfung ist nicht bestanden. Auf dein Gerät kommt nichts. Schick uns bitte einen Screenshot.";
    return `Die Prüfung hat einen Fehler gefunden (${checkName(bad[0].id)}${bad.length > 1 ? ` und ${bad.length - 1} weitere` : ""}). Auf dein Gerät kommt nichts. Schick uns bitte einen Screenshot.`;
  }

  function render() {
    const can = allowed(flow);
    view = Math.min(view, reach());
    way.replaceChildren(...wayOf(flow).map((s, i) => {
      const state = s.state === "error" ? "error" : i === view ? "current" : i < reach() || s.state === "done" ? "done" : "todo";
      const li = el("li", { className: "cee-patch-way-step" }, [el("span", { className: "cee-patch-way-n", textContent: state === "done" ? "✓" : String(i + 1) }), el("span", { textContent: s.label })]);
      li.dataset.state = state;
      if (state === "current") li.setAttribute("aria-current", "step");
      return li;
    }));
    panels.forEach((p, i) => { p.hidden = i !== view; });
    back.hidden = view === 0;
    back.disabled = can.busy;
    next.hidden = view === 3 || (view === 2 && reach() < 3);
    next.disabled = can.busy || view >= reach();
    planList.replaceChildren(...planItems().map(p => el("li", { textContent: p.label })));
    blechInput.disabled = useLatest.checked || can.busy;
    blechDrop.toggleAttribute("data-disabled", useLatest.checked);
    useLatest.disabled = can.busy;
    blechInfo.textContent = ownPatch ? `${ownPatch.file.name} ${ownPatch.file.version}` : "";
    const v = verdict(flow, blech?.items ?? []);
    verdictBox.replaceChildren(...(v ? [pill(v.tone, v.word), el("span", { textContent: ` ${v.text}` }), ...(v.link ? [" ", el("a", { className: "cee-text-link", href: v.link[1], target: "_blank", rel: "noopener noreferrer", textContent: v.link[0] })] : [])] : []));
    verdictBox.hidden = !v;
    if (v && v.text !== toldVerdict) toast(v.text, v.tone === "error" ? "error" : "info", { stay: true });
    toldVerdict = v?.text ?? "";
    routeBox.hidden = flow.origin !== "stock";
    synthSet.hidden = flow.origin !== "synth";
    if (!synthSet.hidden) synthSet.textContent = `Synth-Satz: ${itemsFor(blech, "synth").map(p => p.label).join(", ")}. Den Startbild-Editor am Gerät gibt es auf der blauen noch nicht, das Startbild kommt aus der App.`;
    withHacktribe.checked = flow.route === "hacktribe";
    withHacktribe.disabled = can.busy;
    patchBox.toggleAttribute("data-disabled", flow.phase !== "needs-patch");
    patchInput.disabled = can.busy || flow.phase !== "needs-patch";
    run.hidden = view !== 2;
    run.disabled = !can.patch || (!useLatest.checked && !ownPatch) || (testChoice === "none" && !consent.checked);
    run.textContent = flow.phase === "failed" || flow.phase === "passed" || flow.phase === "downloaded" ? "Noch einmal patchen und prüfen" : testChoice === "none" ? "Patchen" : "Patchen und testen";
    for (const t of testInputs) { t.radio.checked = t.value === testChoice; t.radio.disabled = can.busy; }
    testNote.textContent = TESTS.find(([v]) => v === testChoice)[2];
    consentBox.hidden = testChoice !== "none";
    targetPath.textContent = `${cardFolder(flow.origin)}SYSTEM.VSB`;
    untested.hidden = !flow.untested;
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
    download.disabled = !can.download;
    afraid.disabled = !can.test;
    done.hidden = flow.phase !== "downloaded";
  }

  /** What goes on the file: the set of this version for its build, or the patches of the BLECH.patch the user brought. */
  function planItems() {
    if (ownPatch) return ownPatch.file.patches.map(p => ({ id: p.id, label: p.name ?? p.id }));
    return blech && input ? itemsFor(blech, buildOf(input)) : [];
  }

  useLatest.addEventListener("change", () => { if (useLatest.checked) ownPatch = null; render(); });
  blechInput.addEventListener("change", async () => {
    const file = blechInput.files?.[0];
    blechInput.value = "";
    if (!file) return;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      ownPatch = { bytes, file: await parsePatchFile(bytes) };
    } catch (e) {
      ownPatch = null;
      toast(`${file.name} ist keine BLECH.patch: ${e.message}`, "error");
    }
    render();
  });

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
    dispatch({ type: "patching", patches: planItems() });
    passed = null;
    try {
      const items = planItems();
      await tick();
      const res = ownPatch ? await applyPatchFile(input, ownPatch.bytes) : await applyPatches(input, (await loadPatches()).patches);
      if (!res.ok) {
        for (const p of items) {
          const own = res.reasons.filter(r => r.startsWith(`${p.id}:`)).map(r => r.slice(p.id.length + 2));
          dispatch({ type: "patch", id: p.id, ok: false, detail: own.length ? own.join(" ") : "wartet auf die anderen" });
        }
        throw new Error(`Das Patchen hat nicht geklappt. Nimm deine unveränderte SYSTEM.VSB und versuch es nochmal. Grund: ${res.reasons.join(" ")}`);
      }
      for (const p of items) {
        const n = res.spans.filter(s => s.patch === p.id).length;
        dispatch({ type: "patch", id: p.id, ok: true, detail: `${n} Stelle${n === 1 ? "" : "n"} geschrieben` });
      }
      if (testChoice === "none") {
        passed = res.bytes;
        dispatch({ type: "untested" });
        go(3);
        return;
      }
      dispatch({ type: "checking" });
      await tick();
      // a copy checked before needs no run; otherwise the quick check (start and rescue paths) or the full one
      const report = (testChoice === "quick" ? await verifiedReport(input, res.bytes, await loadVerified()) : null)
        ?? await emulator.check(input, res.bytes, res.allow, res.allowCode, snapshot => { latest = snapshot; showProgress(); }, { quick: testChoice === "quick" });
      if (report.ok) passed = res.bytes;
      dispatch({ type: "checked", report });
    } catch (e) {
      dispatch({ type: "error", message: e.message });
    }
  }

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
          ". Kopieren, nicht umbenennen: Nach dem Update liest BLECHTRIBE seine Dateien aus ", el("code", { textContent: `KORG/${BLECH_FOLDER}/` }),
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
        el("li", { textContent: "Gehe zu Menü -> DATA UTILITY -> SOFTWARE UPDATE und drücke MENU. Starte das Gerät neu, wenn es dich auffordert." }),
        el("li", { textContent: "Schalte das Gerät während des Updates nicht aus." }),
      ].filter(Boolean)),
      el("p", { className: "cee-patch-exit" }, [el("strong", { textContent: "Notausgang: " }), "Halte EXIT beim Einschalten gedrückt, dann startet das Gerät ohne die BLECHTRIBE-Funktionen. Wenn das nicht reicht: ", el("a", { href: "#rescue", textContent: "Rettung" }), "."]),
    );
  }

  const percent = (done, total) => Math.round(done * 100 / total);

  /** The update file from the card into the page. False when it cannot go on by itself (no ORIGINAL.BIN beside a patched file). */
  async function fetchFromDevice(s) {
    const got = await fetchUpdateFile(s, (done, total) => { usbNote.textContent = `Vom Gerät lesen, ${percent(done, total)} %`; });
    usb = { fromOriginal: got.fromOriginal };
    await take(got.bytes);
    if (flow.input?.kind === "blech") {
      usbNote.hidden = true;
      toast("Auf der Karte ist schon eine veränderte SYSTEM.VSB, aber keine Sicherung davon. Zieh deine unveränderte SYSTEM.VSB (die Sicherung vom Schreibtisch) oben in das Feld. Nach der Prüfung geht es hier über USB weiter.", "info", { stay: true });
      return false;
    }
    return true;
  }

  /** The checked copy onto the card; the first time the unpatched file goes beside it as ORIGINAL.BIN. */
  async function storeToDevice(s) {
    await storeUpdateFile(s, passed, usb?.fromOriginal ? null : original, (done, total) => { usbNote.textContent = `Aufs Gerät schreiben, ${percent(done, total)} %`; });
    usbNote.hidden = true;
    usb = { fromOriginal: true };
    toast("Fertig, die neue Firmware liegt auf der Karte. Jetzt am Gerät: MENU, mit EDIT ◀ zu DATA UTILITY, MENU, mit EDIT ▶ zu SOFTWARE UPDATE, dann MENU drücken, bis „OK. Please Reboot.“ kommt. Dazwischen nicht ausschalten. Danach aus- und wieder einschalten.", "ok", { stay: true });
  }

  usbGet.addEventListener("click", async () => {
    const s = session();
    if (!s) { toast("Die Electribe ist nicht verbunden. Steck sie per USB an und schalte sie ein. Dann im Bereich Emulator oben „Echtes Gerät“ wählen und auf „Mit Electribe verbinden“ klicken.", "error"); return; }
    usbGet.disabled = true;
    usbNote.hidden = false;
    try {
      if (!await fetchFromDevice(s)) return;
      if (flow.phase !== "ready") { usbNote.hidden = true; toast("Die Datei vom Gerät braucht noch eine Entscheidung, siehe unten.", "info", { stay: true }); return; }
      usbNote.textContent = "Patchen und im Emulator prüfen, das dauert ein paar Minuten.";
      await patchAndCheck();
      if (!passed) { usbNote.hidden = true; toast("Die Prüfung im Emulator ist nicht bestanden, auf das Gerät kam nichts. Details unten.", "error"); return; }
      await storeToDevice(s);
      go(3);
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
    if (!s) { toast("Die Electribe ist nicht verbunden. Steck sie per USB an und schalte sie ein. Dann im Bereich Emulator oben „Echtes Gerät“ wählen und auf „Mit Electribe verbinden“ klicken.", "error"); return; }
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
    saveFile(passed, "SYSTEM.VSB");
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
