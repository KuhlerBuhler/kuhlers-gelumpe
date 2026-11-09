/** The Patcher page: the user's own SYSTEM.VSB, BLECH patched on in the browser, checked in the emulator, then offered for download. Logic: src/patcher.mjs. */
import { e2Outline } from "./e2-art.mjs";
import { el } from "./fields.mjs";
import { stateText } from "./state.mjs";
import { icon } from "./icons.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { applyPatches } from "../../src/patch.mjs";
import { applyPatchFile, parsePatchFile, patchesFor } from "../../src/patchfile.mjs";
import { NEWS } from "../../data/news.mjs";
import { fetchUpdateFile, storeUpdateFile } from "../../src/usb-update.mjs";
import { buildOf, hardwareOf } from "../../src/firmware.mjs";
import { recogniseBlech } from "../../src/blech-update.mjs";
import { t, tNodes } from "./i18n.mjs";
import { number } from "../../src/text.mjs";
import { isZip, unzipEntry } from "../../src/zip.mjs";
import { wayOf, classify, convertStock, KORG_DOWNLOADS, withHead, headFor, folderOf, choosesDevice, hardwareOfFlow, sampleFolder, loadBlechSet, itemsFor, checkName, checkDetail, checkProgress, clock, newFlow, step, allowed, verifiedReport, VERIFIED_URL, BLECH_FOLDER, DOOM_FOLDER, DOOM_FILES, hasDoom, VSB_SIZE, HACKTRIBE_PATCH_URL, HACKTRIBE_PATCH_RAW, HACKTRIBE_SHA256, BLECH_SET_URL, BLECH_SYNTH_SET_URL, USB_NAME_URLS, optionFor, patchLabel, withLoadingAnim, restoreOriginal, canRestore, runsHacktribe, runningFolder, goalsFor, goalMismatch, korgBlueForSampler } from "../../src/patcher.mjs";
import { LOADING_ANIM_ID } from "../../src/loading-anim.mjs";
import { storedAnimation } from "./loading-anim.mjs";
import { testFailure } from "../../data/rescue.mjs";
import { RESCUE_EVENT } from "./rescue.mjs";

const STYLE = new URL("./patcher.css", import.meta.url).href;

/** Where the update test put the file, in the words of the device. */
const hintFor = folder => t("patcher.hint", { folder });


const tick = () => new Promise(r => setTimeout(r, 0));

/** The tick on the corner of a chosen card, drawn by patcher.css only while the card is chosen. */
const mark = () => {
  const m = el("span", { className: "cee-patch-mark" }, [icon("check")]);
  m.setAttribute("aria-hidden", "true");
  return m;
};

/** What the verdict line says for a file that cannot be patched or is ready. */
/** What the dropped file was taken for, after its name in the field. */
const FOUND = { hacktribe: "patcher.found.hacktribe", stock: "patcher.found.stock", synth: "patcher.found.synth" };

function verdict(flow, items, waiting = false) {
  const { input } = flow;
  if (!input) return null;
  const v = verdictText(input, items, waiting);
  // every "not this file" names the file by its checksum, so a screenshot tells support what was dropped
  return v && input.sha256 ? { ...v, text: t("patcher.verdict.sha", { text: v.text, sha: input.sha256.slice(0, 8) }) } : v;
}

function verdictText(input, items, waiting) {
  const size = number(input.size);
  switch (input.kind) {
    // A file the page takes says nothing: the user knows what was dropped, the button and the route say what comes next.
    case "hacktribe":
    case "synth":
    case "stock": return null;
    case "blech": return { tone: "ok", word: t("patcher.verdict.blech"), text: t(waiting ? "patcher.restore.needKorg" : "patcher.verdict.blech.text") };
    case "partial": if (waiting) return { tone: "warn", word: t("patcher.verdict.partial"), text: t("patcher.restore.needKorg") };
      // an older BLECH on Hacktribe: the app cannot rebuild Hacktribe's original, the user's backup or Korg's file can
      if (input.oldOnHacktribe) return { tone: "warn", word: t("patcher.verdict.partial"), text: t("patcher.verdict.oldHacktribe", { sha: HACKTRIBE_SHA256.slice(0, 8) }) };
      return { tone: "warn", word: t("patcher.verdict.partial"), text: t("patcher.verdict.partial.text", { patches: input.present.map(id => t(items.find(p => p.id === id)?.label ?? id)).join(", ") }) };
    case "wrong-size": return { tone: "error", word: t("patcher.verdict.size"), text: t("patcher.verdict.size.text", { size, expected: number(VSB_SIZE) }) };
    default: return { tone: "error", word: t("patcher.verdict.unknown"), text: t("patcher.verdict.unknown.text", { reason: input.reasons[0] ?? t("patcher.verdict.unknown.reason") }) };
  }
}

/** `onTest(failure)` hears the last test as testFailure (data/rescue.mjs) gives it: null when it passed, for the Rettung page. */
export function patcherPage(root, { emulator, show = () => {}, session = () => null, onTarget = () => {}, onTest = () => {} }) {
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
  let failure = null;           // what the last run that did not pass is about (testFailure), for Blechy
  // An error of the patcher leads to the Rettung page by name, at the node of what failed (FLOW in data/rescue.mjs).
  const testHelp = () => (failure ? (failure.group ? `test:${failure.group}` : "test") : null);
  const toRescue = help => ({ helpLabel: t("patcher.toRescue"), ...(help ? { help } : {}) });
  let blech = null;             // the BLECH set (data/patches/blech.json) with its patches parsed, once loaded
  let ownPatch = null;          // a .patch the user brought instead of the set of this version: { bytes, file }
  let usbNames = null;          // the variants of the optional patch usb-name, once loaded
  let hint = null;
  let updating = null;          // the file already carries BLECH of a known release: { present, options }, the set goes over it (src/blech-update.mjs)
  let knownReleases;            // data/known-releases.json, loaded when a file with BLECH is taken; null when it cannot be had
  let pending = null;          // a file with BLECH on it, waiting for Korg's own to rebuild the original from: { bytes, usb }
  let usb = null;               // the file came over USB: { fromOriginal }; null for a dropped file (then the unpatched one goes to the card too)
  let taken = null;             // what classify made of the file taken last, to take it anew when the goal changes

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-file", accept: ".VSB,.vsb" });
  const fileInfo = el("span", { className: "ui-dropzone-files", id: "cee-patch-file-info" });
  let fileName = "";            // the name of the file the page holds, said in the field
  const dropHint = el("span", { className: "ui-dropzone-hint" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("patcher.drop.drag") }), t("common.pick")]),
    dropHint,
    fileInfo,
  ]);

  // Korg's System Updater holds the SYSTEM.VSB. The card only shows which file comes, it is no control: the licence box
  // below and Weiter load it. The app loads the zip itself (korg_firmware); the browser has Korg's zip downloaded and
  // the user drops it into the field. Korg's page with its agreement is the link in the licence box.
  const native = () => globalThis.__TAURI__?.core?.invoke;
  const licence = el("input", { type: "checkbox", id: "cee-patch-korg-licence" });
  const korgCards = [["red", t("patcher.device.red")], ["blue", t("patcher.device.blue")]].map(([device, name]) => {
    const out = el("span", { className: "cee-device-card-out" });
    const say = el("span");
    const card = el("div", { className: "cee-entry-step cee-device-card cee-patch-korg-card", id: `cee-patch-korg-${device}` }, [
      e2Outline(name), el("span", { className: "cee-device-card-text" }, [el("strong", { textContent: name }), say]), out,
    ]);
    card.dataset.device = device;
    return { device, card, say, out, li: el("li", {}, [card]) };
  });
  function renderKorg() {
    for (const c of korgCards) {
      c.say.textContent = t(!licence.checked ? "patcher.korg.needLicence" : native() ? "patcher.korg.native" : "patcher.korg.zip");
      c.out.replaceChildren(icon("download"));
      c.out.dataset.icon = "download";
    }
  }
  licence.addEventListener("change", renderKorg);
  licence.addEventListener("change", () => render());
  licence.addEventListener("change", () => {
    if (!licence.checked || !pending || !native()) return;
    const waiting = pending;
    usb = waiting.usb;
    take(waiting.bytes);
  });
  // Opt-in, under Korg's licence: hacktribe-2.patch straight from Hacktribe's repository, ticked when the wizard's target
  // needs Hacktribe (docs/ideen/86-patcher-startseite.md). convertStock still checks the result against Hacktribe's hash.
  const fetchHt = el("input", { type: "checkbox", id: "cee-patch-hacktribe-fetch" });
  const fetchHtBox = el("label", { className: "cee-check", id: "cee-patch-hacktribe-fetch-box", hidden: true }, [fetchHt, el("span", {}, tNodes("patcher.korg.hacktribe", { file: el("code", { textContent: "hacktribe-2.patch" }) }))]);
  const korgLead = el("p", { className: "cee-patch-lead", id: "cee-patch-korg-lead" });
  // Why Weiter waits on the first step: neither the licence for Korg's file nor a file of the user's own.
  const korgHint = el("p", { className: "muted", id: "cee-patch-korg-hint", textContent: t("patcher.korg.nextHint"), hidden: true });
  // A file that does not fit the goal the wizard named: Weiter waits, the toast said why when it came in.
  const goalHint = el("p", { className: "muted", id: "cee-patch-goal-hint", textContent: t("patcher.goal.hint"), hidden: true });
  // The update over the SD card: the file from the card goes into the field, nothing from Korg.
  const updateLead = el("p", { className: "cee-patch-lead", id: "cee-patch-update-lead", hidden: true });
  const korg = el("div", { className: "cee-patch-korg", id: "cee-patch-korg" }, [
    korgLead,
    el("ul", { className: "cee-entry-steps", id: "cee-patch-firmware" }, korgCards.map(c => c.li)),
    el("label", { className: "cee-check", id: "cee-patch-korg-licence-box" }, [licence, el("span", {}, tNodes("patcher.korg.licence", {
      link: el("a", { className: "cee-text-link", id: "cee-patch-korg-licence-link", href: KORG_DOWNLOADS.red.page, target: window.__GELUMPE_APP ? "_self" : "_blank", rel: "noopener noreferrer", textContent: t("patcher.korg.licence.link") }),
    }))]),
    fetchHtBox,
    korgHint,
  ]);
  renderKorg();
  const usbGet = el("button", { type: "button", className: "btn", id: "cee-patch-usb-get", textContent: t("patcher.usb.get") });
  const usbNote = el("p", { className: "muted", id: "cee-patch-usb-note", role: "status", hidden: true });
  const usbBox = el("section", { className: "cee-patch-usb", id: "cee-patch-usb" }, [
    el("h2", { className: "cee-patch-usb-title", textContent: t("patcher.usb.title") }),
    el("p", { className: "cee-patch-lead", textContent: t("patcher.usb.lead") }),
    el("div", { className: "actions" }, [usbGet]),
  ]);
  const usbPut = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-usb-put", textContent: t("patcher.usb.put"), hidden: true });
  const way = el("ol", { className: "cee-patch-way", id: "cee-patch-way" });
  way.setAttribute("aria-label", t("patcher.way"));
  // What the dropped file is not, said in the toast; the box only keeps it for screen readers and tests.
  const verdictBox = el("div", { className: "cee-patch-verdict ui-sr-only", id: "cee-patch-verdict", role: "status" });
  let toldVerdict = "";
  let closeVerdict = () => {};
  const synthSet = el("p", { className: "muted", id: "cee-patch-synth-set", hidden: true });
  // Hacktribe is the Sampler's code: it is made from Korg's red file (or brought as a Hacktribe file), never from the blue one.
  const blueHacktribe = el("p", { className: "muted", id: "cee-patch-blue-hacktribe", hidden: true },
    t("patcher.blueHacktribe"));
  // A copy with Hacktribe runs on the red and the blue: the user says which, the cable says it too when one is connected.
  // the Electribes as on the Korg cards of step 1: drawn in lines in the colour of the case
  const deviceInputs = [["red", t("patcher.device.red")], ["blue", t("patcher.device.blue")]].map(([value, name]) => {
    const radio = el("input", { type: "radio", name: "cee-patch-device", value, className: "ui-sr-only" });
    radio.addEventListener("change", () => { if (radio.checked) chooseDevice(value); });
    const card = el("label", { className: "cee-entry-step cee-device-card cee-patch-device-card cee-patch-card" }, [
      radio, e2Outline(name), el("span", { className: "cee-device-card-text" }, [el("strong", { textContent: name })]), mark(),
    ]);
    card.dataset.device = value;
    return { value, radio, label: el("li", {}, [card]) };
  });
  const deviceGroup = el("ul", { className: "cee-entry-steps", id: "cee-patch-device" }, deviceInputs.map(d => d.label));
  deviceGroup.setAttribute("role", "radiogroup");
  deviceGroup.setAttribute("aria-label", t("patcher.device.label"));
  const deviceNote = el("p", { className: "muted", id: "cee-patch-device-note" });
  const deviceBox = el("section", { className: "cee-patch-choice", id: "cee-patch-device-box", hidden: true }, [
    el("p", { className: "cee-patch-lead", textContent: t("patcher.device.lead") }), deviceGroup, deviceNote,
  ]);
  let cable = null;             // "red" or "blue": what the Electribe connected over USB said it is, null when none is or it cannot tell
  // Step 2 chooses what goes on the file: BLECHTRIBE of this version or any own .patch file, and on Korg's original Hacktribe as well.
  const release = NEWS[0].version;
  const useLatest = el("input", { type: "checkbox", id: "cee-patch-latest", checked: true });
  const blechInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-blech-file", accept: ".patch", disabled: true });
  const blechInfo = el("span", { className: "ui-dropzone-files", id: "cee-patch-blech-info" });
  const blechDrop = el("label", { className: "ui-dropzone", id: "cee-patch-blech-drop" }, [
    blechInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("patcher.blech.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("patcher.blech.hint") }),
    blechInfo,
  ]);
  // Optional, off by default: the computer sees the Electribe as "Electribe 3" (docs/ideen/69-geraetename.md).
  const usbName = el("input", { type: "checkbox", id: "cee-patch-usb-name" });
  usbName.addEventListener("change", () => { passed = null; dispatch({ type: "options" }); });
  const usbNameNote = el("p", { className: "muted", id: "cee-patch-usb-name-note", textContent: t("patcher.usbName.note") });
  const blechBox = el("section", { className: "cee-patch-choice", id: "cee-patch-blech" }, [
    el("label", { className: "cee-check" }, [useLatest, el("span", { textContent: t("patcher.blech.latest", { version: release }) })]),
    blechDrop,
    el("label", { className: "cee-check", id: "cee-patch-usb-name-box" }, [usbName, el("span", { textContent: t("patcher.usbName") })]),
    usbNameNote,
  ]);
  const withHacktribe = el("input", { type: "checkbox", id: "cee-patch-hacktribe-use" });
  withHacktribe.addEventListener("change", () => chooseRoute(withHacktribe.checked ? "hacktribe" : "direct"));
  const routePick = el("label", { className: "cee-check", id: "cee-patch-route-pick" }, [withHacktribe, el("span", { textContent: t("patcher.route.hacktribe") })]);
  const routeNote = el("p", { className: "muted", id: "cee-patch-route-note", textContent: t("patcher.route.note") });
  const routeBox = el("section", { className: "cee-patch-choice", id: "cee-patch-route", hidden: true }, [routePick, routeNote]);
  const patchInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-patch-hacktribe-file" });
  const patchInfo = el("span", { className: "ui-dropzone-files", id: "cee-patch-hacktribe-info" });
  const patchDrop = el("label", { className: "ui-dropzone" }, [
    patchInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("patcher.hacktribe.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("patcher.hacktribe.hint") }),
    patchInfo,
  ]);
  let patchName = "";           // the hacktribe-2.patch the original was turned into Hacktribe with, said in its field
  const patchBox = el("div", { className: "cee-patch-needs", id: "cee-patch-needs" }, [
    el("p", {}, tNodes("patcher.hacktribe.needs", { link: el("a", { className: "cee-text-link", id: "cee-patch-hacktribe-link", href: HACKTRIBE_PATCH_URL, target: "_blank", rel: "noopener noreferrer", textContent: "hacktribe-2.patch" }) })),
    patchDrop,
  ]);
  routeBox.append(patchBox);
  const run = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-run", textContent: t("patcher.run"), hidden: true });
  // How much of the emulator test runs: none (with consent), the quick one of today, or the full run that once took 90 minutes.
  const TESTS = [
    ["none", "patcher.test.none", "patcher.test.none.note"],
    ["quick", "patcher.test.quick", "patcher.test.quick.note"],
    ["full", "patcher.test.full", "patcher.test.full.note"],
  ];
  let testChoice = "quick";
  /** A list item inside a radiogroup is only layout: role none, so the group holds its radios directly. */
  const choiceItem = children => { const li = el("li", {}, children); li.setAttribute("role", "none"); return li; };
  // the same cards as every choice of the patcher: the chosen one framed in the accent with a tick on its corner
  const testInputs = TESTS.map(([value, text, sub]) => {
    const radio = el("input", { type: "radio", name: "cee-patch-test", value, checked: value === testChoice, className: "ui-sr-only" });
    radio.addEventListener("change", () => { if (radio.checked) { testChoice = value; render(); } });
    return { value, radio, label: choiceItem([el("label", { className: "cee-entry-step cee-patch-card" }, [radio, el("strong", { textContent: t(text) }), el("span", { textContent: t(sub) }), mark()])]) };
  });
  const testGroup = el("ul", { className: "cee-entry-steps", id: "cee-patch-test" }, testInputs.map(input => input.label));
  testGroup.setAttribute("role", "radiogroup");
  testGroup.setAttribute("aria-label", t("patcher.test.title"));
  const consent = el("input", { type: "checkbox", id: "cee-patch-consent" });
  consent.addEventListener("change", () => render());
  const consentBox = el("label", { className: "cee-patch-consent", id: "cee-patch-consent-box", hidden: true }, [consent,
    el("span", { textContent: t("patcher.consent") })]);
  const testBox = el("div", { className: "cee-patch-test-box", id: "cee-patch-test-box" }, [el("h2", { className: "cee-patch-usb-title", textContent: t("patcher.test.title") }), testGroup, consentBox]);
  // Hacktribe takes the samples away (docs/messungen/2026-11-06-hacktribe-samples.md): the way on waits for the box.
  const htAck = el("input", { type: "checkbox", id: "cee-patch-ht-ack" });
  htAck.addEventListener("change", () => render());
  const htWarn = el("section", { className: "cee-patch-warn", id: "cee-patch-ht-warn", hidden: true }, [
    el("h2", { className: "cee-patch-warn-title", textContent: t("patcher.htWarn.title") }),
    el("p", { textContent: t("patcher.htWarn.slots") }),
    el("p", { textContent: t("patcher.htWarn.backup") }),
    el("p", {}, tNodes("patcher.htWarn.done", { rescue: el("a", { className: "cee-text-link", id: "cee-patch-ht-rescue", href: "#rescue", textContent: t("nav.rescue") }) })),
    el("label", { className: "cee-check", id: "cee-patch-ht-ack-box" }, [htAck, el("span", { textContent: t("patcher.htWarn.ack") })]),
  ]);
  const htWizWarn = el("p", { className: "cee-patch-warn-line", id: "cee-patch-wiz-ht-warn", textContent: t("patcher.htWarn.wiz"), hidden: true });
  /** A copy with Hacktribe goes onto an Electribe that does not run it yet: Korg's original or BLECH, or a dropped Hacktribe file the wizard did not name. */
  const installsHt = () => {
    if (updating) return false;
    if (flow.origin === "stock") return flow.route === "hacktribe" && !hasHt();
    return flow.origin === "hacktribe" && !hasHt();
  };
  const htReady = () => !installsHt() || htAck.checked;
  const planList = el("ul", { className: "cee-patch-plan", id: "cee-patch-plan" });
  const plan = el("div", { className: "cee-patch-plan-box" }, [
    el("p", { className: "cee-patch-lead", textContent: t("patcher.plan") }),
    planList,
  ]);
  const bar = el("div", { className: "ui-progress cee-patch-bar", id: "cee-patch-bar", hidden: true });
  const groupList = el("ul", { className: "cee-patch-groups", id: "cee-patch-groups", hidden: true });
  const checkList = el("ul", { className: "ui-list", id: "cee-patch-checks" });
  // a red test keeps its way to the Rettung page after the toast is gone
  const failRescue = el("a", { className: "cee-text-link", id: "cee-patch-fail-rescue", href: "#rescue", textContent: t("nav.rescue") });
  failRescue.addEventListener("click", () => window.dispatchEvent(new CustomEvent(RESCUE_EVENT, { detail: { message: failureLine(flow.report), to: testHelp() } })));
  const failHelp = el("p", { id: "cee-patch-fail-help", hidden: true }, tNodes("patcher.failed.rescue", { rescue: failRescue }));
  const checksBox = el("details", { className: "ui-details", id: "cee-patch-details", hidden: true }, [el("summary", { id: "cee-patch-details-title" }), el("div", { className: "ui-details-body" }, [checkList])]);
  const note = el("p", { className: "muted", id: "cee-patch-note", role: "status", hidden: true });
  // The main action of step 4 on its own row and large: it downloads the file, "save" alone made people look for something else.
  const download = el("button", { type: "button", className: "btn lg cee-primary cee-patch-download", id: "cee-patch-download", textContent: t("patcher.download"), disabled: true });
  // Step 4 names where the file goes before anything is saved: big, so it can be read off while copying.
  const targetPath = el("p", { className: "cee-patch-path", id: "cee-patch-path" });
  // Before the copy goes onto the device: what to do when it does not start (in step 1 only a file is loaded, nothing can break).
  const untested = el("span", { id: "cee-patch-untested", hidden: true, textContent: t("patcher.untested") });
  const after = el("p", { className: "cee-note", id: "cee-patch-after" }, [
    untested,
    ...tNodes("patcher.after", { rescue: el("a", { className: "cee-text-link", id: "cee-patch-rescue", href: "#rescue", textContent: t("nav.rescue") }) }),
  ]);
  const targetLead = el("p", { className: "cee-patch-lead", id: "cee-patch-target-lead" });
  const targetNot = el("p", { className: "muted", id: "cee-patch-target-not", textContent: t("patcher.target.not") });
  const originalHead = el("p", { className: "muted", id: "cee-patch-original-head", textContent: t("patcher.original.head"), hidden: true });
  const target = el("div", { className: "cee-patch-target", id: "cee-patch-target" }, [targetLead, targetPath, targetNot, originalHead, after]);
  const afraid = el("button", { type: "button", className: "btn", id: "cee-patch-afraid", textContent: t("patcher.afraid"), disabled: true });
  const result = el("div", { className: "actions cee-patch-result", id: "cee-patch-result", hidden: true }, [download, usbPut, afraid]);
  const done = el("section", { className: "cee-patch-done", id: "cee-patch-done", hidden: true });

  // The wizard in front of the way: which Electribe, which firmware runs on it, then what to do. A card only chooses,
  // Weiter goes on. The answers pick what step 1 shows, set the route and the device the flow needs, and take out of
  // the later steps what they ruled out (goalsFor, goalMismatch). A file dropped without them (tests) shows everything.
  const wiz = { step: 0, device: null, firmware: null, goal: null };
  /** The step where the way begins, after the wizard's three pages. */
  const WAY = 3;
  // the first Electribes (grey synth, black sampler) take the same firmware as the blue and the red
  const WIZ_DEVICES = [
    ["blue", "blue", "patcher.device.blue", "patcher.wiz.synth"],
    ["red", "red", "patcher.device.red", "patcher.wiz.sampler"],
    ["grey", "blue", "patcher.wiz.grey", "patcher.wiz.synth"],
    ["black", "red", "patcher.wiz.black", "patcher.wiz.sampler"],
  ];
  const WIZ_FIRMWARES = {
    korg: ["patcher.wiz.fw.korg", () => "patcher.wiz.korg"],
    ht: ["patcher.wiz.fw.ht", () => (hwOf() === "blue" ? "patcher.wiz.htBlue" : "patcher.wiz.ht")],
    blech: ["patcher.wiz.fw.blech", () => "patcher.wiz.fw.blech.note"],
    blechHt: ["patcher.wiz.fw.blechHt", () => "patcher.wiz.fw.blechHt.note"],
  };
  const hwOf = () => (WIZ_DEVICES.find(d => d[0] === wiz.device)?.[1] ?? "red");
  /** Hacktribe runs on the Electribe now, by the wizard's second page. */
  const hasHt = () => runsHacktribe(wiz.firmware);
  /** The goal is BLECH with Hacktribe. */
  const wantsHt = () => wiz.goal === "blechHt";
  /** The goal builds BLECH from a firmware file: with or without Hacktribe. */
  const patching = () => wiz.goal === "blech" || wiz.goal === "blechHt";
  const isOriginal = () => wiz.goal === "original";
  const overUsb = () => wiz.goal === "updateUsb";
  const isUpdate = () => wiz.goal === "updateUsb" || wiz.goal === "updateCard";
  const GOALS = {
    blech: ["patcher.wiz.blech", () => (hasHt() ? "patcher.wiz.blech.dropHt" : "patcher.wiz.becomes")],
    blechHt: ["patcher.wiz.blechHt", () => (hasHt() ? "patcher.wiz.becomes.onHt" : "patcher.wiz.becomes.ht")],
    updateUsb: ["patcher.wiz.updateUsb", () => "patcher.wiz.updateUsb.note"],
    updateCard: ["patcher.wiz.updateCard", () => "patcher.wiz.updateCard.note"],
    original: ["patcher.wiz.original", () => "patcher.wiz.original.note"],
  };

  /** A group of cards to choose one from (role radiogroup): the arrow keys move the choice, Space and Enter take it. */
  function choiceGroup(id, label) {
    const ul = el("ul", { className: "cee-entry-steps", id });
    ul.setAttribute("role", "radiogroup");
    ul.setAttribute("aria-label", label);
    ul.addEventListener("keydown", e => {
      const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (!step) return;
      const cards = [...ul.querySelectorAll("[role=radio]:not([aria-disabled=true])")];
      const at = cards.indexOf(document.activeElement);
      if (at < 0) return;
      e.preventDefault();
      const to = cards[(at + step + cards.length) % cards.length];
      to.focus();
      to.click();
    });
    return ul;
  }
  /** One card of a group: chooses `value` with `onPick`; a `locked` one says why it cannot be chosen and takes no click. */
  function choiceCard(id, value, children, onPick, { device, locked } = {}) {
    const b = el("button", { type: "button", className: `cee-entry-step cee-patch-pick${device ? " cee-device-card" : ""}`, id }, [...children, mark()]);
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", "false");
    b.dataset.value = value;
    if (device) b.dataset.device = device;
    if (locked) b.setAttribute("aria-disabled", "true");
    b.addEventListener("click", () => { if (!locked) { onPick(value); render(); } });
    return choiceItem([b]);
  }
  /** The chosen card of a group checked, and the one the Tab key lands on: the chosen one, else the first that can be chosen. */
  function markChoices(ul, chosen) {
    const cards = [...ul.querySelectorAll("[role=radio]")];
    const first = cards.find(c => c.dataset.value === chosen) ?? cards.find(c => c.getAttribute("aria-disabled") !== "true");
    for (const c of cards) {
      c.setAttribute("aria-checked", String(c.dataset.value === chosen));
      c.tabIndex = c === first ? 0 : -1;
    }
  }
  const cardText = (name, sub) => [el("strong", { textContent: t(name) }), el("span", { textContent: t(sub) })];

  const wizDevices = choiceGroup("cee-patch-wiz-devices", t("patcher.wiz.device"));
  wizDevices.replaceChildren(...WIZ_DEVICES.map(([id, , name, sub]) => choiceCard(`cee-patch-wiz-${id}`, id,
    [e2Outline(t(name)), el("span", { className: "cee-device-card-text" }, cardText(name, sub))],
    value => { if (wiz.device !== value) { wiz.device = value; wiz.firmware = null; wiz.goal = null; } }, { device: id })));
  const wizFirmwares = choiceGroup("cee-patch-wiz-firmwares", t("patcher.wiz.firmware"));
  function renderFirmwares() {
    wizFirmwares.replaceChildren(...Object.entries(WIZ_FIRMWARES).map(([id, [name, sub]]) => choiceCard(`cee-patch-wiz-fw-${id}`, id,
      cardText(name, sub()), value => { if (wiz.firmware !== value) { wiz.firmware = value; wiz.goal = null; } })));
  }
  const wizGoals = choiceGroup("cee-patch-wiz-goals", t("patcher.wiz.goal"));
  function renderGoals() {
    wizGoals.replaceChildren(...goalsFor(wiz.firmware, hwOf()).map(({ id, locked }) => {
      const [name, sub] = GOALS[id];
      return choiceCard(`cee-patch-wiz-${id}`, id, cardText(name, locked ?? sub()), value => { wiz.goal = value; }, { locked });
    }));
  }
  /** What the page of the wizard asks has an answer that can be taken. */
  const wizChosen = () => [wiz.device, wiz.firmware, wiz.goal][wiz.step] != null;
  const wizPanels = [
    [el("h2", { className: "cee-patch-ask", textContent: t("patcher.wiz.device") }), wizDevices, el("p", { className: "muted", id: "cee-patch-wiz-card", textContent: t("patcher.wiz.card") })],
    [el("h2", { className: "cee-patch-ask", textContent: t("patcher.wiz.firmware") }), wizFirmwares],
    [el("h2", { className: "cee-patch-ask", textContent: t("patcher.wiz.goal") }), wizGoals, el("p", { className: "muted", id: "cee-patch-wiz-keeps", textContent: t("patcher.wiz.keeps") }), htWizWarn],
  ].map((children, i) => el("div", { className: "cee-patch-panel", id: `cee-patch-wiz-${i + 1}`, tabIndex: -1, hidden: i > 0 }, children));
  const orLine = el("p", { className: "cee-patch-or", id: "cee-patch-or", textContent: t("patcher.or") });

  // One panel per step of the way; Zurück and Weiter move between them, the flow decides how far Weiter may go.
  const panels = [
    [usbBox, orLine, updateLead, korg, drop, goalHint, verdictBox],
    [htWarn, blechBox, routeBox, deviceBox, plan, synthSet, blueHacktribe],
    [testBox, bar, note, groupList, failHelp, checksBox],
    [target, result, done],
  ].map((children, i) => el("div", { className: "cee-patch-panel", id: `cee-patch-step-${i + 1}`, tabIndex: -1, hidden: i > 0 }, children));
  const back = el("button", { type: "button", className: "btn", id: "cee-patch-back", textContent: t("patcher.back"), hidden: true });
  const next = el("button", { type: "button", className: "btn cee-primary", id: "cee-patch-next", textContent: t("patcher.next"), disabled: true });
  let view = 0;

  root.replaceChildren(el("div", { className: "cee-patch" }, [
    el("h1", { className: "cee-patch-title ui-sr-only", textContent: t("nav.patcher") }),
    way,
    usbNote,
    ...wizPanels,
    ...panels,
    el("div", { className: "cee-patch-nav", id: "cee-patch-nav" }, [back, next, run]),
  ]));

  /** The key of why the taken file does not fit the wizard's goal, or null. */
  const mismatch = () => (wiz.goal ? goalMismatch(wiz.goal, flow, hwOf()) : null);
  /** The steps of the way this goal goes: back to the original has nothing to patch or test. */
  const views = () => (isOriginal() ? [0, 3] : [0, 1, 2, 3]);

  /** The furthest step the flow allows: a file taken opens step 2, the patches chosen step 3 (test and run), a passed copy step 4. */
  function reach() {
    if (mismatch()) return 0;
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
  function wizGo(to) {
    wiz.step = to;
    if (to === 1) renderFirmwares();
    if (to === 2) renderGoals();
    htWizWarn.hidden = true;
    if (to === WAY) view = 0;
    render();
    const panel = to < WAY ? wizPanels[to] : panels[view];
    panel.focus({ preventScroll: true });
    panel.scrollIntoView?.({ block: "nearest" });
  }

  /** Weiter on the goal: step 1 offers what it needs, the Hacktribe download is ticked when it needs that, a file taken fits it. */
  function pickGoal() {
    htAck.checked = false;
    fetchHt.checked = wantsHt();
    // a file that went back to Korg's original under another goal is taken anew
    if (flow.original && !isOriginal() && taken) { passed = null; dispatch({ type: "input", input: taken }); }
    wizGo(WAY);
    fitFlow();
    if (fetchHt.checked) fetchHacktribe();
  }

  /** Korg's original on the route the goal asks for, a copy with Hacktribe for the Electribe the wizard named. */
  function fitFlow() {
    if (!patching() && !isOriginal()) return;
    if (stockFile && flow.origin === "stock") chooseRoute(wantsHt() ? "hacktribe" : "direct");
    if (patching() && choosesDevice(flow) && !cable) chooseDevice(hwOf());
    if (isOriginal()) makeOriginal();
  }

  /** Back to Korg's firmware: Korg's own file as it is, on the blue under Hacktribe with the Sampler head its update takes. */
  async function makeOriginal() {
    if (flow.phase !== "ready" || mismatch()) return;
    let bytes = input;
    if (hwOf() === "blue" && hasHt()) {
      const res = await korgBlueForSampler(input);
      if (!res.ok) { toast(t("patcher.goal.wrong.original", { device: t(`patcher.device.${hwOf()}`) }), "error"); return; }
      bytes = res.bytes;
    }
    passed = bytes;
    dispatch({ type: "original" });
  }

  back.addEventListener("click", () => {
    if (allowed(flow).busy) return;
    if (wiz.step < WAY) { if (wiz.step > 0) wizGo(wiz.step - 1); return; }
    const at = views().indexOf(view);
    if (at > 0) go(views()[at - 1]);
    else wizGo(wiz.goal ? 2 : 0);
  });
  /** The Electribe whose Korg file step 1 loads: the red one for Hacktribe, else the one the wizard named. */
  const korgDevice = () => (wantsHt() ? "red" : hwOf());
  /** Weiter on step 1 loads Korg's file: only with the licence, and never over a file the user gave (or one waiting). */
  const loadsKorg = () => wiz.step === WAY && view === 0 && reach() === 0 && !flow.input && !pending && !korg.hidden && licence.checked;

  /** In the browser Korg's zip is downloaded as a file: Korg's server does not hand it to the page, the user drops it in. */
  function downloadKorg(device) {
    const a = el("a", { href: KORG_DOWNLOADS[device].file, target: window.__GELUMPE_APP ? "_self" : "_blank", rel: "noopener noreferrer" });
    a.click();
    toast(t("patcher.korg.started"), "info");
  }

  /** The next step of the way, when the flow allows it. */
  const goOn = () => {
    const to = views()[views().indexOf(view) + 1];
    if (to !== undefined && to <= reach()) go(to);
  };

  next.addEventListener("click", async () => {
    if (wiz.step < WAY) {
      if (!wizChosen()) return;
      if (wiz.step === 2) pickGoal();
      else wizGo(wiz.step + 1);
      return;
    }
    if (allowed(flow).busy) return;
    if (loadsKorg()) {
      if (!native()) { downloadKorg(korgDevice()); return; }
      next.disabled = true;
      await fromKorg(korgDevice());
      render();
      goOn();
      return;
    }
    goOn();
  });

  async function loadPatches(build = input ? buildOf(input) : "hacktribe") {
    const setUrl = build === "synth" ? BLECH_SYNTH_SET_URL : BLECH_SET_URL;
    if (blech?.setUrl === setUrl) return blech;
    blech = { ...await loadBlechSet(async url => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(t("patcher.loadFailed", { url }));
      return res.json();
    }, setUrl), setUrl };
    return blech;
  }

  /** The variants of the optional patch usb-name, one per hardware. */
  async function loadUsbNames() {
    usbNames ??= await Promise.all(USB_NAME_URLS.map(async url => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(t("patcher.loadFailed", { url }));
      return res.json();
    }));
    return usbNames;
  }

  /** The optional patches the user picked, in the variant for the input's build. */
  async function options() {
    if (!usbName.checked || !input) return [];
    const patch = optionFor(await loadUsbNames(), buildOf(input));
    return patch ? [patch] : [];
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
    note.textContent = p ? t("patcher.progress", { text: p.text, elapsed }) : t("patcher.progress.running", { elapsed });
    window.ui?.setProgress(bar, p ? p.value : null, t("patcher.progress.label"));
    groupList.hidden = !p;
    groupList.replaceChildren(...(p?.groups ?? []).map(g => {
      const li = el("li", {}, [el("span", { textContent: g.name }), el("span", { className: "cee-patch-group-state", textContent: t(g.text) })]);
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
    // an untested copy has no bar and no "bestanden": nothing ran; Korg's original is no copy of the patcher at all
    const passed_ = (flow.phase === "passed" || flow.phase === "downloaded") && !flow.untested && !flow.original;
    bar.hidden = !(can.busy || passed_);
    bar.dataset.tone = passed_ ? "ok" : "";
    if (passed_) window.ui?.setProgress(bar, 100, t("patcher.progress.label"), { valueText: t("patcher.check.ok") });
    else if (flow.phase === "patching") window.ui?.setProgress(bar, null, t("patcher.patching"));
    const failed = flow.report && !flow.report.ok ? failureLine(flow.report) : null;
    note.hidden = !can.busy;
    if (flow.phase === "patching") note.textContent = t("patcher.patching");
    // A result is told once, as a toast; the line is only for the run itself.
    const result = passed_ ? [t("patcher.passed"), "ok"] : can.busy ? null : flow.error ? [t(flow.error), "error"] : failed ? [failed, "error"] : null;
    const key = result ? `${flow.phase}|${result[0]}` : null;
    // an error's "Blechy fragen" goes straight to what this failure means
    if (key !== toasted) { toasted = key; if (result) toast(result[0], result[1], result[1] === "error" ? toRescue(testHelp()) : {}); }
  }

  /** One short line for a check that ran and did not pass; the list of all checks sits behind the disclosure. */
  function failureLine(report) {
    const bad = report.checks.filter(c => !c.ok);
    if (!bad.length) return t("patcher.failed");
    return bad.length > 1 ? t("patcher.failed.many", { check: checkName(bad[0].id), more: bad.length - 1 }) : t("patcher.failed.one", { check: checkName(bad[0].id) });
  }

  function render() {
    const can = allowed(flow);
    view = Math.min(view, reach());
    // the way shows the steps this goal goes, numbered as they come
    const shown = views();
    way.replaceChildren(...wayOf(flow).flatMap((s, i) => {
      if (!shown.includes(i)) return [];
      const state = s.state === "error" ? "error" : i === view ? "current" : i < reach() || s.state === "done" ? "done" : "todo";
      const li = el("li", { className: "cee-patch-way-step" }, [el("span", { className: "cee-patch-way-n", textContent: state === "done" ? "✓" : String(shown.indexOf(i) + 1) }), el("span", { textContent: t(s.label) })]);
      li.dataset.state = state;
      if (state === "current") li.setAttribute("aria-current", "step");
      return [li];
    }));
    const inWiz = wiz.step < WAY;
    wizPanels.forEach((p, i) => { p.hidden = wiz.step !== i; });
    markChoices(wizDevices, wiz.device);
    markChoices(wizFirmwares, wiz.firmware);
    markChoices(wizGoals, wiz.goal);
    way.hidden = inWiz;
    panels.forEach((p, i) => { p.hidden = inWiz || i !== view; });
    // Step 1 shows what the goal needs: the update over USB only the device's own file, the update over the card only
    // the field for the card's file, the others Korg's file of the Electribe that fits. Without a goal (a file dropped
    // before the wizard) it shows everything.
    const goal = wiz.goal;
    const usbWay = overUsb();
    // over USB the field and Korg's file come only when the device's own file needs them (a BLECH the app does not know)
    const usbFallback = usbWay && (!!pending || flow.input?.kind === "blech");
    usbBox.hidden = !!goal && !usbWay;
    orLine.hidden = !!goal;
    updateLead.hidden = goal !== "updateCard";
    updateLead.replaceChildren(...tNodes("patcher.update.card.lead", { file: el("code", { textContent: "SYSTEM.VSB" }), folder: el("code", { textContent: runningFolder(wiz.firmware, hwOf()) }) }));
    drop.hidden = usbWay && !usbFallback;
    korg.hidden = isUpdate() && !pending;
    // from Korg's original the field takes the one file that fits: the Electribe's own, or the red's for Hacktribe;
    // only BLECH with Hacktribe onto a Hacktribe that runs takes the user's Hacktribe file as well
    const korgOnly = isOriginal() || (patching() && !(wantsHt() && hasHt()));
    dropHint.textContent = korgOnly ? t("patcher.drop.hint.korg", { device: t(`patcher.device.${korgDevice()}`) })
      : isUpdate() && !pending ? t("patcher.drop.hint.update") : t("patcher.drop.hint");
    for (const c of korgCards) c.li.hidden = (patching() || isOriginal()) && c.device !== korgDevice();
    fetchHtBox.hidden = !wantsHt();
    korgLead.replaceChildren(...(isOriginal()
      ? tNodes("patcher.original.lead", { device: t(`patcher.device.${hwOf()}`), file: el("code", { textContent: "SYSTEM.VSB" }) })
      : patching()
        ? tNodes(wantsHt() ? "patcher.start.lead.hacktribe" : "patcher.start.lead", { file: el("code", { textContent: "SYSTEM.VSB" }) })
        : tNodes("patcher.korg.lead", { file: el("code", { textContent: "SYSTEM.VSB" }), folder: el("code", { textContent: "KORG/…/System/" }) })));
    back.hidden = wiz.step === 0;
    back.disabled = can.busy;
    // in the wizard Weiter waits for a choice; on the way it waits for what the flow needs
    next.hidden = !inWiz && (view === 3 || (view === 2 && reach() < 3));
    next.disabled = inWiz ? !wizChosen() : can.busy || (view >= reach() && !loadsKorg()) || (view === 1 && !htReady());
    korgHint.hidden = inWiz || view !== 0 || reach() > 0 || !!flow.input || !!pending || korg.hidden || licence.checked;
    goalHint.hidden = inWiz || view !== 0 || !mismatch();
    planList.replaceChildren(...planItems().map(p => el("li", { textContent: t(p.label) })));
    blechInput.disabled = useLatest.checked || can.busy;
    blechDrop.toggleAttribute("data-disabled", useLatest.checked);
    useLatest.disabled = can.busy;
    const locked = !!updating?.present.includes("usb-name");
    usbName.disabled = can.busy || locked;
    usbNameNote.textContent = t(locked ? "patcher.update.locked" : "patcher.usbName.note");
    blechInfo.textContent = ownPatch ? `${ownPatch.file.name} ${ownPatch.file.version}` : "";
    // The field says which file it holds and what it is; pick() empties the input, so ui.js cannot show the name.
    const found = flow.origin === "hacktribe" && flow.input?.hardware === "blue" ? t("patcher.found.hacktribeBlue") : FOUND[flow.origin] && t(FOUND[flow.origin]);
    const held = flow.input && fileName ? t("patcher.held", { file: fileName, found: found ?? t("patcher.found.none") }) : "";
    drop.toggleAttribute("data-selected", true);
    drop.toggleAttribute("data-filled", !!held && !!flow.origin);
    fileInfo.textContent = held;
    const v = verdict(flow, blech?.items ?? [], !!pending);
    verdictBox.replaceChildren(...(v ? [stateText(v.tone, v.word), el("span", { textContent: ` ${v.text}` }), ...(v.link ? [" ", el("a", { className: "cee-text-link", href: v.link[1], target: "_blank", rel: "noopener noreferrer", textContent: v.link[0] })] : [])] : []));
    verdictBox.hidden = !v;
    // A new file brings a new verdict: the toast of the old one goes, so two verdicts never stand side by side.
    if ((v?.text ?? "") !== toldVerdict) { closeVerdict(); closeVerdict = v ? toast(v.text, v.tone === "error" ? "error" : "info", { stay: true, ...toRescue("normal:patch") }) : () => {}; }
    toldVerdict = v?.text ?? "";
    // the goal decides whether Hacktribe goes on: then only the field for hacktribe-2.patch is left of the route
    routeBox.hidden = flow.origin !== "stock" || !!updating || (!!goal && flow.route !== "hacktribe");
    routePick.hidden = !!goal;
    routeNote.hidden = !!goal;
    htWarn.hidden = !installsHt();
    // the goal page warns only once a goal is chosen that puts Hacktribe on an Electribe that does not run it
    htWizWarn.hidden = wiz.step !== 2 || !wantsHt() || hasHt();
    synthSet.hidden = flow.origin !== "synth";
    blueHacktribe.hidden = flow.origin !== "synth" || !!goal;
    // The wizard's first page already names the Electribe: asked again only when the file came in without it,
    // or when the file or the cable says another one than the user named.
    const named = !!wiz.device && flow.device === hwOf() && !(cable && cable !== flow.device);
    deviceBox.hidden = !flow.origin || named;
    for (const d of deviceInputs) { d.radio.checked = d.value === flow.device; d.radio.disabled = can.busy || !choosesDevice(flow); }
    deviceNote.textContent = !flow.origin ? "" : [
      !choosesDevice(flow) ? (flow.device === "blue" ? t("patcher.device.only.blue") : t("patcher.device.only.red")) :
      flow.device === "blue" ? (flow.origin === "stock" ? t("patcher.device.head.stock") : t("patcher.device.head.hacktribe")) : "",
      cable && cable !== flow.device ? (cable === "blue" ? t("patcher.device.cable.blue") : t("patcher.device.cable.red")) : "",
    ].filter(Boolean).join(" ");
    if (!synthSet.hidden) synthSet.textContent = t("patcher.synthSet", { patches: itemsFor(blech, "synth").map(p => t(p.label)).join(", ") });
    withHacktribe.checked = flow.route === "hacktribe";
    withHacktribe.disabled = can.busy;
    // open on the whole Hacktribe route, so the field shows the file it took and takes another one
    patchBox.toggleAttribute("data-disabled", flow.route !== "hacktribe");
    patchInput.disabled = can.busy || flow.route !== "hacktribe";
    patchInfo.textContent = flow.route === "hacktribe" && flow.phase !== "needs-patch" && patchName ? t("patcher.hacktribe.converted", { file: patchName }) : "";
    run.hidden = inWiz || view !== 2;
    run.disabled = !can.patch || !htReady() || (!useLatest.checked && !ownPatch) || (testChoice === "none" && !consent.checked);
    run.textContent = flow.phase === "failed" || flow.phase === "passed" || flow.phase === "downloaded" ? t("patcher.run.again") : testChoice === "none" ? t("patcher.run.untested") : t("patcher.run");
    for (const input of testInputs) { input.radio.checked = input.value === testChoice; input.radio.disabled = can.busy; }
    consentBox.hidden = testChoice !== "none";
    const folder = targetFolder();
    targetLead.textContent = t(usbWay ? "patcher.target.usb" : "patcher.target");
    targetPath.textContent = `${folder}SYSTEM.VSB`;
    // a running BLECH reads its own folder; only a first BLECH must not go there
    targetNot.hidden = folder === `KORG/${BLECH_FOLDER}/System/` || isOriginal();
    originalHead.hidden = !(isOriginal() && hwOf() === "blue" && hasHt());
    untested.hidden = !flow.untested;
    fileInput.disabled = can.busy;

    renderProgress(can);

    const checks = flow.report?.checks ?? [];
    checksBox.hidden = !checks.length;
    failHelp.hidden = !flow.report || flow.report.ok;
    document.getElementById("cee-patch-details-title").textContent = t("patcher.checks", { count: checks.length });
    checkList.replaceChildren(...checks.map(c => el("li", { className: "ui-row" }, [
      stateText(c.skipped ? "info" : c.ok ? "ok" : "error", t(c.skipped ? "patcher.check.skipped" : c.ok ? "patcher.check.ok" : "patcher.check.failed")), el("strong", { textContent: ` ${t(checkName(c.id))}` }), el("span", { className: "ui-break muted", textContent: ` ${t(checkDetail(c.detail))}` }),
    ])));

    result.hidden = !can.download;
    // the way to the device is the goal's: over USB the app writes it, otherwise it is downloaded for the card
    usbPut.hidden = goal ? !usbWay : !session();
    usbPut.disabled = !can.download || !htReady();
    usbGet.disabled = can.busy;
    download.hidden = usbWay;
    download.disabled = !can.download || !htReady();
    afraid.disabled = !can.test;
    // the update test runs the dropped file; it stands for the device only when it is made for the same Electribe
    afraid.hidden = !rehearsable() || !!flow.original;
    done.hidden = flow.phase !== "downloaded";
  }

  /** What goes on the file: the set of this version for its build, or the patches of the BLECH.patch the user brought. */
  function planItems() {
    // one line per patch: the variant for this firmware (a BLECH.patch carries one per build)
    const extra = usbName.checked && input ? [{ id: "usb-name", label: t("patcher.usbName") }] : [];
    // the own loading animation from the Design page goes on only where load-bar does, which reads it
    const withAnim = items => (storedAnimation() && items.some(p => p.id === "load-bar") ? [...items, { id: LOADING_ANIM_ID, label: t("patcher.patch.loadingAnim") }] : items);
    if (ownPatch) return input ? [...withAnim(patchesFor(ownPatch.file, base()).map(p => ({ id: p.id, label: patchLabel(p) }))), ...extra] : [];
    return blech && input ? [...withAnim(itemsFor(blech, buildOf(input))), ...extra] : [];
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
      toast(t("patcher.blech.wrong", { file: file.name, error: e.message }), "error");
    }
    render();
  });

  async function pick(file) {
    usb = null;
    fileInput.value = "";           // choosing the same path again, after it changed, must still fire
    await takeFile(file.name, new Uint8Array(await file.arrayBuffer()));
  }

  /** A dropped or downloaded file: a VSB as it is, Korg's zip with the SYSTEM.VSB taken out of it. */
  async function takeFile(name, bytes) {
    if (isZip(bytes)) {
      let entry;
      try { entry = await unzipEntry(bytes); } catch (e) { toast(t("patcher.zip.error", { file: name, error: e.message }), "error"); return; }
      if (!entry) { toast(t("patcher.zip.none", { file: name }), "error"); return; }
      fileName = `${name} › SYSTEM.VSB`;
      await take(entry.bytes);
      return;
    }
    fileName = name;
    await take(bytes);
  }

  /** Korg's zip for `device`, loaded by the app itself after the licence was accepted, straight into the field. */
  async function fromKorg(device) {
    usb = null;
    const close = toast(t("patcher.korg.loading"), "info", { stay: true });
    try {
      const zip = new Uint8Array(await native()("korg_firmware", { device }));
      close();
      await takeFile(device === "red" ? "electribe_sampler_system_v202.zip" : "electribe_system_v202.zip", zip);
    } catch (e) {
      close();
      toast(t("patcher.korg.failed", { error: e?.message ?? e }), "error");
    }
  }

  async function classifyFile(bytes) {
    try {
      return await classify(bytes, (await loadPatches(buildOf(bytes))).patches);
    } catch (e) {
      return { kind: "unknown", size: bytes.length, reasons: [e.message], present: [] };
    }
  }

  /** The unpatched original of `patched`, rebuilt from Korg's file `korgBytes`; null when it is not made from it. */
  async function restoreWith(patched, korgBytes) {
    try {
      const res = await restoreOriginal(patched, korgBytes, (await loadPatches(buildOf(korgBytes))).patches);
      return res.ok ? res.bytes : null;
    } catch {
      return null;
    }
  }

  /** Without the accepted licence (or the app) the file waits in `pending` and the verdict asks for Korg's file. */
  async function restoreFromKorg(patched) {
    if (!licence.checked || !native()) { pending = { bytes: patched, usb }; return null; }
    const close = toast(t("patcher.korg.loading"), "info", { stay: true });
    try {
      const zip = new Uint8Array(await native()("korg_firmware", { device: hardwareOf(patched) }));
      const entry = isZip(zip) ? await unzipEntry(zip) : null;
      close();
      return entry ? await restoreWith(patched, entry.bytes) : null;
    } catch (e) {
      close();
      toast(t("patcher.korg.failed", { error: e?.message ?? e }), "error");
      pending = { bytes: patched, usb };
      return null;
    }
  }

  /**
   * A file of Korg's 2.02 that is not byte-identical to the one in Korg's zip (`kind.changed`, "stock" or "synth"): the app
   * loads Korg's own file for that Electribe and goes on with it. Hacktribe is never loaded. null without the app or the
   * licence (the file then waits in `pending` for the licence), or when what came is not Korg's original.
   */
  async function fetchOriginal(changed, dropped) {
    if (!native()) return null;
    if (!licence.checked) { pending = { bytes: dropped, usb }; return null; }
    const device = changed === "synth" ? "blue" : "red";
    const close = toast(t("patcher.korg.loading"), "info", { stay: true });
    try {
      const zip = new Uint8Array(await native()("korg_firmware", { device }));
      const entry = isZip(zip) ? await unzipEntry(zip) : null;
      close();
      const kind = entry ? await classifyFile(entry.bytes) : null;
      if (kind?.kind === changed) return { bytes: entry.bytes, kind };
      toast(t("patcher.korg.failed", { error: t("patcher.korg.notOriginal") }), "error");
    } catch (e) {
      close();
      toast(t("patcher.korg.failed", { error: e?.message ?? e }), "error");
    }
    return null;
  }

  async function loadKnown() {
    if (knownReleases === undefined) {
      try {
        const res = await fetch("data/known-releases.json");
        knownReleases = res.ok ? await res.json() : null;
      } catch { knownReleases = null; }
    }
    return knownReleases;
  }

  async function take(bytes) {
    const waiting = pending;
    pending = null;
    updating = null;
    let kind = await classifyFile(bytes);
    let restored = null;
    if (waiting && (kind.kind === "stock" || kind.kind === "synth")) {
      restored = await restoreWith(waiting.bytes, bytes);
      if (restored) usb = waiting.usb;
    } else if (kind.kind === "blech" || kind.kind === "partial") {
      const known = await recogniseBlech(bytes, await loadKnown());
      if (known.ok) {
        updating = known;
        bytes = known.bytes;
        kind = { kind: buildOf(bytes), size: bytes.length, sha256: kind.sha256, reasons: [], present: [], hardware: hardwareOf(bytes) };
        if (usb) usb = { fromOriginal: true };
        usbName.checked = usbName.checked || known.present.includes("usb-name");
        toast(t("patcher.update.found"), "info");
      } else if (canRestore(bytes)) {
        restored = await restoreFromKorg(bytes);
      } else if (kind.kind === "partial") {
        // Hacktribe's original is in no file the app can load: the user's backup, or Korg's 2.02 with hacktribe-2.patch
        kind = { ...kind, oldOnHacktribe: true };
      }
    }
    if (kind.changed && !waiting) {
      const fetched = await fetchOriginal(kind.changed, bytes);
      if (fetched) {
        bytes = fetched.bytes;
        kind = fetched.kind;
        toast(t("patcher.korg.fetched"), "ok");
      } else if (!native() || !licence.checked) {
        kind = { ...kind, reasons: [t("patcher.reason.withFetch", { reason: kind.reasons[0] })] };
      }
    }
    if (restored) {
      bytes = restored;
      kind = await classifyFile(bytes);
      toast(t("patcher.restore.done"), "ok");
    }
    input = bytes;
    original = bytes;
    stockFile = kind.kind === "stock" && !updating ? { bytes, kind } : null;
    passed = null;
    taken = kind;
    wiz.step = WAY;
    dispatch({ type: "input", input: kind });
    // a file the goal ruled out stays in the field, Weiter waits and the toast says which file the goal needs
    const wrong = mismatch();
    if (wrong) toast(t(wrong, { device: t(`patcher.device.${korgDevice()}`) }), "error");
    fitFlow();
    await askCable();
  }

  /** What the Electribe on the cable is, red or blue; it picks the device for a copy with Hacktribe. */
  async function askCable() {
    const s = session();
    try { cable = s?.hardware ? await s.hardware() : null; } catch { cable = null; }
    // the cable knows best; without one the Electribe named on the wizard's first page
    const want = cable ?? (patching() ? hwOf() : null);
    if (want && choosesDevice(flow) && want !== flow.device) dispatch({ type: "device", device: want });
    else render();
  }

  function chooseDevice(device) {
    if (allowed(flow).busy) return;
    passed = null;
    dispatch({ type: "device", device });
  }

  /** The bytes the patches go on: the input with the head the device takes (headFor), by what runs on it now. */
  const base = () => (headFor(flow, wiz.firmware) ? withHead(input, headFor(flow, wiz.firmware)) : input);

  /** Where the file goes on the card: the folder of the firmware that runs, as the wizard was told, else the file's own. */
  const targetFolder = () => (wiz.firmware ? runningFolder(wiz.firmware, hwOf()) : folderOf(flow));

  const rehearsable = () => !!original && (flow.device !== "blue" || flow.origin === "synth" || hardwareOf(original) === "blue");

  function chooseRoute(route) {
    if (!stockFile || route === flow.route || allowed(flow).busy) return;
    input = stockFile.bytes;
    passed = null;
    dispatch({ type: "route", route, input: stockFile.kind });
    htAck.checked = false;
    if (route === "hacktribe" && fetchHt.checked) fetchHacktribe();
  }

  /** hacktribe-2.patch straight from Hacktribe's repository onto this computer; without network the field in step 2 stays. */
  let fetchingHt = false;
  async function fetchHacktribe() {
    if (fetchingHt || flow.phase !== "needs-patch") return;
    fetchingHt = true;
    const close = toast(t("patcher.hacktribe.loading"), "info", { stay: true });
    try {
      const res = await fetch(HACKTRIBE_PATCH_RAW);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const bytes = new Uint8Array(await res.arrayBuffer());
      close();
      if (flow.route === "hacktribe" && !allowed(flow).busy) await convertWith("hacktribe-2.patch", bytes);
    } catch (e) {
      close();
      toast(t("patcher.hacktribe.failed", { error: e?.message ?? e }), "error");
    } finally {
      fetchingHt = false;
    }
  }
  fetchHt.addEventListener("change", () => { if (fetchHt.checked) fetchHacktribe(); });

  async function pickPatch(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    patchInput.value = "";
    await convertWith(file.name, bytes);
  }

  /** Korg's original and a hacktribe-2.patch (dropped or loaded) to Hacktribe, checked against Hacktribe's hash. */
  async function convertWith(name, bytes) {
    await tick();
    // another patch file after a conversion starts the route anew
    if (flow.phase !== "needs-patch") dispatch({ type: "route", route: "hacktribe", input: stockFile.kind });
    const res = await convertStock(stockFile.bytes, bytes);
    if (!res.ok) { dispatch({ type: "convert-failed", message: res.reason }); return; }
    patchName = name;
    input = res.bytes;
    passed = null;
    dispatch({ type: "converted", input: { kind: "hacktribe", size: res.bytes.length, reasons: [], present: [] }, detail: `SHA-256 ${res.sha256.slice(0, 12)}…` });
  }

  patchInput.addEventListener("change", () => {
    const file = patchInput.files?.[0];
    if (file && flow.route === "hacktribe" && !allowed(flow).busy) pickPatch(file);
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) pick(file);
  });

  run.addEventListener("click", () => patchAndCheck());

  /** Applies the set to the input and checks the copy in the emulator; afterwards `passed` holds it when it passed. */
  async function patchAndCheck() {
    if (!allowed(flow).patch) return;
    dispatch({ type: "patching", patches: planItems(), runs: wiz.firmware });
    passed = null;
    failure = null;
    try {
      const items = planItems();
      await tick();
      const from = base();
      const extra = await options();
      let res = ownPatch ? await applyPatchFile(from, ownPatch.bytes) : await applyPatches(from, [...(await loadPatches()).patches, ...extra], updating?.options);
      // a BLECH.patch is checked against its own hashes first; the optional patches go on top of its result
      if (ownPatch && res.ok && extra.length) {
        const more = await applyPatches(res.bytes, extra);
        res = more.ok ? { ...more, spans: [...res.spans, ...more.spans], allow: [...res.allow, ...more.allow], allowCode: [...res.allowCode, ...more.allowCode] } : more;
      }
      res = await withLoadingAnim(res, items.some(p => p.id === LOADING_ANIM_ID) ? storedAnimation() : null);
      if (!res.ok) {
        for (const p of items) {
          const own = res.reasons.filter(r => r.startsWith(`${p.id}:`)).map(r => r.slice(p.id.length + 2));
          dispatch({ type: "patch", id: p.id, ok: false, detail: own.length ? own.join(" ") : t("patcher.patch.waiting") });
        }
        failure = { group: "patch" };
        throw new Error(t("patcher.patch.failed", { reasons: res.reasons.join(" ") }));
      }
      for (const p of items) {
        const n = res.spans.filter(s => s.patch === p.id).length;
        dispatch({ type: "patch", id: p.id, ok: true, detail: n === 1 ? t("patcher.patch.spots.one", { count: n }) : t("patcher.patch.spots.many", { count: n }) });
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
      const hardware = hardwareOfFlow(flow);
      const report = (testChoice === "quick" ? await verifiedReport(from, res.bytes, await loadVerified(), hardware) : null)
        ?? await emulator.check(from, res.bytes, res.allow, res.allowCode, snapshot => { latest = snapshot; showProgress(); }, { quick: testChoice === "quick", hardware });
      if (report.ok) passed = res.bytes;
      // a red check no group knows still is a red test: Blechy then asks which kind it was
      failure = report.ok ? null : testFailure(report) ?? { group: null };
      onTest(failure);
      dispatch({ type: "checked", report });
    } catch (e) {
      // the patching stopped, or the emulator did not run the test
      failure ??= { group: "run" };
      onTest(failure);
      dispatch({ type: "error", message: e.message });
    }
  }

  /** The guide after the file is out: `usb` when the app wrote it to the card, else downloaded for the card. */
  function buildDone(way = "card") {
    const folder = targetFolder();
    onTarget(folder);
    const backup = el("li", { id: "cee-patch-guide-backup" }, tNodes("patcher.done.backup", { patterns: el("a", { className: "cee-text-link", href: "#patterns", textContent: t("rescue.link.patterns") }) }));
    if (flow.original) {
      // back to Korg's: the file alone in the running firmware's folder, afterwards Korg's firmware reads its own folder again
      const reads = sampleFolder(hwOf() === "blue" ? "synth" : "stock");
      const from = wiz.firmware === "ht" ? sampleFolder("hacktribe") : `KORG/${BLECH_FOLDER}/`;
      done.replaceChildren(
        el("h2", { textContent: t("patcher.done.original.title") }),
        el("ol", { className: "cee-patch-guide" }, [
          backup,
          el("li", { id: "cee-patch-guide-vsb" }, tNodes("patcher.done.original.vsb", { file: el("code", { textContent: "SYSTEM.VSB" }), folder: el("code", { textContent: folder }) })),
          el("li", { textContent: t("patcher.done.insert") }),
          el("li", { textContent: t("patcher.done.update") }),
          el("li", { textContent: t("patcher.done.power") }),
          el("li", { id: "cee-patch-guide-after" }, tNodes("patcher.done.original.after", { reads: el("code", { textContent: reads }), from: el("code", { textContent: from }) })),
        ]),
      );
      return;
    }
    // the samples lie where the running firmware keeps them: under Hacktribe in its folder, even when the new file is made from Korg's
    const old = sampleFolder(hasHt() ? "hacktribe" : flow.origin);
    // Korg's firmware of the blue keeps the synth's files, which the Sampler code cannot read: nothing to copy then;
    // a BLECH that runs already reads KORG/blechtribe/, nothing to copy either
    const moves = blech?.items.some(p => p.id === "blechtribe") && !(flow.origin === "stock" && flow.device === "blue") && !(wiz.firmware === "blech" || wiz.firmware === "blechHt");
    // with the runtime the device asks at the first start and copies the folder itself (script_migrate.s)
    const asks = moves && blech.items.some(p => p.id === "script-runtime");
    const copy = (key) => el("li", { id: "cee-patch-guide-copy" }, tNodes(key, {
      from: el("code", { textContent: old }), to: el("code", { textContent: `KORG/${BLECH_FOLDER}/` }), reads: el("code", { textContent: `KORG/${BLECH_FOLDER}/` }),
    }));
    done.replaceChildren(
      el("h2", { textContent: t("patcher.done.title") }),
      el("ol", { className: "cee-patch-guide" }, [
        backup,
        moves && !asks ? copy("patcher.done.copy") : null,
        blech && hasDoom(blech) ? el("li", { id: "cee-patch-guide-doom" }, tNodes("patcher.done.doom", {
          files: DOOM_FILES.flatMap((file, i) => [i ? t("patcher.done.doom.and") : "", el("a", { className: "cee-text-link", href: file, download: file.split("/").pop(), textContent: file.split("/").pop() })]),
          folder: el("code", { textContent: DOOM_FOLDER }),
          licences: el("a", { className: "cee-text-link", id: "cee-patch-doom-licences", href: "third_party/doom/README.md", target: "_blank", rel: "noopener noreferrer", textContent: t("patcher.done.doom.licences") }),
        })) : null,
        el("li", { id: "cee-patch-guide-vsb" }, tNodes(way === "usb" ? "patcher.done.usb.vsb" : moves ? "patcher.done.vsb.moved" : "patcher.done.vsb", { file: el("code", { textContent: "SYSTEM.VSB" }), folder: el("code", { textContent: folder }) })),
        way === "usb" ? null : el("li", { textContent: t("patcher.done.insert") }),
        way !== "usb" && folder === "KORG/electribe/System/" ? el("li", { textContent: t("patcher.done.only") }) : null,
        el("li", { textContent: t("patcher.done.update") }),
        el("li", { textContent: t("patcher.done.power") }),
        asks ? copy("patcher.done.copy.asks") : null,
      ].filter(Boolean)),
      el("p", { className: "cee-patch-exit" }, [el("strong", { textContent: t("patcher.done.exit.title") }), ...tNodes("patcher.done.exit", { rescue: el("a", { href: "#rescue", textContent: t("nav.rescue") }) })]),
    );
  }

  const percent = (done, total) => Math.round(done * 100 / total);

  /** The update file from the card into the page. False when it cannot go on by itself (no ORIGINAL.BIN beside a patched file). */
  async function fetchFromDevice(s) {
    const got = await fetchUpdateFile(s, (done, total) => { usbNote.textContent = t("patcher.usb.reading", { percent: percent(done, total) }); });
    usb = { fromOriginal: got.fromOriginal };
    fileName = t("patcher.usb.file");
    await take(got.bytes);
    if (flow.input?.kind === "blech") {
      usbNote.hidden = true;
      if (!pending) toast(t("patcher.usb.blech"), "info", { stay: true });
      return false;
    }
    return true;
  }

  /** The checked copy onto the card; the first time the unpatched file goes beside it as ORIGINAL.BIN. */
  async function storeToDevice(s) {
    await storeUpdateFile(s, passed, usb?.fromOriginal ? null : original, (done, total) => { usbNote.textContent = t("patcher.usb.writing", { percent: percent(done, total) }); });
    usbNote.hidden = true;
    usb = { fromOriginal: true };
    toast(t("patcher.usb.done"), "ok", { stay: true });
    dispatch({ type: "downloaded" });
    buildDone("usb");
  }

  usbGet.addEventListener("click", async () => {
    const s = session();
    if (!s) { toast(t("patcher.usb.notConnected"), "error", { help: "notfound" }); return; }
    usbGet.disabled = true;
    usbNote.hidden = false;
    try {
      if (!await fetchFromDevice(s)) return;
      if (flow.phase !== "ready") { usbNote.hidden = true; toast(t("patcher.usb.decide"), "info", { stay: true }); return; }
      usbNote.textContent = t("patcher.usb.checking");
      await patchAndCheck();
      if (!passed) { usbNote.hidden = true; toast(t("patcher.usb.failed"), "error", toRescue(testHelp())); return; }
      await storeToDevice(s);
      go(3);
    } catch (e) {
      usbNote.hidden = true;
      toast(e.message, "error", toRescue("start"));
    } finally {
      usbGet.disabled = allowed(flow).busy;
    }
  });

  usbPut.addEventListener("click", async () => {
    const s = session();
    if (!passed || !allowed(flow).download || !htReady()) return;
    if (!s) { toast(t("patcher.usb.notConnected"), "error", { help: "notfound" }); return; }
    usbPut.disabled = true;
    usbNote.hidden = false;
    try {
      await storeToDevice(s);
    } catch (e) {
      usbNote.hidden = true;
      toast(e.message, "error", toRescue("start"));
    } finally {
      usbPut.disabled = !allowed(flow).download || !htReady();
    }
  });

  download.addEventListener("click", () => {
    if (!passed || !allowed(flow).download || !htReady()) return;
    saveFile(passed, "SYSTEM.VSB");
    dispatch({ type: "downloaded" });
    buildDone();
  });

  function showHint(folder) {
    hint?.remove();
    const close = el("button", { type: "button", className: "btn icon", id: "cee-patch-hint-close", ariaLabel: t("patcher.hint.close"), title: t("patcher.hint.close") }, [icon("x")]);
    hint = el("div", { className: "cee-patch-hint", id: "cee-patch-hint", role: "note" }, [el("p", { textContent: hintFor(folder) }), close]);
    close.addEventListener("click", () => { hint.remove(); hint = null; });
    document.getElementById("cee-area-emu").prepend(hint);
  }

  afraid.addEventListener("click", async () => {
    if (!passed || !allowed(flow).test || !rehearsable()) return;
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
