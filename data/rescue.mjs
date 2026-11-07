/**
 * What the Rettung page (site/app/rescue.mjs) says: a conversation with Blechy for someone who knows little about the
 * device and is worried. Only the answers, in plain words; where an official guide covers a step, `source` names it.
 * The evidence behind each step is in docs/rettung.md.
 */

export const LINKS = {
  debrick: "https://github.com/bangcorrupt/hacktribe/wiki/Debrick",
  hacktribe: "https://github.com/bangcorrupt/hacktribe",
  issues: "https://github.com/KuhlerBuhler/kuhlers-gelumpe/issues",
  instagram: "https://www.instagram.com/kuhler_buhler/",
  korgRed: "https://www.korg.com/us/support/download/product/0/368/#software",
  korgBlue: "https://www.korg.com/us/support/download/product/0/367/#software",
  // pages of the app itself; they open in place, not in a new tab
  settings: "#settings",
  patcher: "#patcher",
  discord: "#discord",
};

/**
 * The two Electribes and where Korg's own firmware for each lives: on Korg's page and on the card. `heads`: the files
 * the update there takes, by their head (src/card-check.mjs), for Blechy's look at the card.
 */
export const DEVICES = {
  red: { title: "rescue.device.red", body: "red", link: "korgRed", name: "Electribe Sampler", path: "KORG/electribe sampler/System/SYSTEM.VSB", heads: ["sampler"] },
  blue: { title: "rescue.device.blue", body: "blue", link: "korgBlue", name: "Electribe", path: "KORG/electribe/System/SYSTEM.VSB", heads: ["synth"] },
};

/**
 * The folder the running firmware reads its update from. Every folder is checked on devices with version 1.2. Hacktribe
 * takes only the Sampler head, on the blue too; BLECH takes the head of its build, so both (src/patcher.mjs, HEADS).
 */
export const FOLDERS = [
  { title: "rescue.folder.red", body: "red", path: "KORG/electribe sampler/System/SYSTEM.VSB", heads: ["sampler"] },
  { title: "rescue.folder.blue", body: "blue", path: "KORG/electribe/System/SYSTEM.VSB", heads: ["synth"] },
  { title: "rescue.folder.hacktribe", body: "grey", path: "KORG/hacktribe/System/SYSTEM.VSB", heads: ["sampler"] },
  { title: "rescue.folder.blech", body: "grey", path: "KORG/blechtribe/System/SYSTEM.VSB", heads: ["sampler", "synth"] },
];

/** Where to ask: a line with links, `{name}` in its text is the link `links.name`, whose `link` is a key of LINKS. */
const ASK = { key: "rescue.say.ask", links: { issue: { link: "issueNew", text: "rescue.link.issue" }, instagram: { link: "instagram", text: "rescue.link.instagram" } } };
/** The guide the Hacktribe project keeps for a device that no longer starts. */
const DEBRICK = [{ link: "debrick", text: "rescue.link.debrick" }];
const LATER = "rescue.say.later";

export const BUTTONS = { again: "rescue.again", back: "rescue.back" };

/**
 * What a red test of the patcher is about: `patch` the patching itself stopped (the bytes at a spot are not those of a
 * known 2.02), `start` a change in the head, the DSP program or the code of the start phase, `boot` a start or a rescue
 * path that no longer works in the emulator, `feature` the test of a function (the cases of the patches), `run` the test
 * did not run at all (no emulator).
 */
export const TEST_GROUPS = ["patch", "start", "boot", "feature", "run"];

/** The checks of tools/emu/check.py by their group; every id with a module prefix ("menu:...") is a function test. */
const START_CHECKS = ["header", "dsp_stream", "start_phase"];
const BOOT_CHECKS = ["boot:normal", "boot:normal_blank", "update_offer", "panel_update", "kill_switch", "dsp_boot_once"];

/**
 * The key of the area of a function test by the prefix of its id (the `id` the cases in tools/emu/*_cases.py report), so Blechy
 * can say what was tested in words.
 */
export const TEST_AREAS = {
  menu: "rescue.area.menu", shortcut: "rescue.area.menu",
  pswitch: "rescue.area.pattern", lastpattern: "rescue.area.pattern", initpattern: "rescue.area.pattern",
  "sample-errors": "rescue.area.samples", "stereo-pad": "rescue.area.samples",
  splash: "rescue.area.start", loadbar: "rescue.area.start", migrate: "rescue.area.start",
  fxcard: "rescue.area.card", presets: "rescue.area.card", power_off: "rescue.area.card",
  mfx: "rescue.area.sound", ifxidle: "rescue.area.sound", synthfilter: "rescue.area.sound",
  tapmotion: "rescue.area.play", noteassist: "rescue.area.play", dice: "rescue.area.play", beateighth: "rescue.area.play", touchscalezero: "rescue.area.play",
  remote: "rescue.area.midi", sysex: "rescue.area.midi",
  plugin_edit: "rescue.area.plugin", plugin_api15: "rescue.area.plugin", plugin_api18: "rescue.area.plugin", plugin_api19: "rescue.area.plugin", plugin_catalog15: "rescue.area.plugin", timers: "rescue.area.plugin", objects: "rescue.area.plugin", live_write: "rescue.area.plugin", global: "rescue.area.plugin", pattern_parts: "rescue.area.plugin", testmode: "rescue.area.plugin",
  doom: "rescue.area.doom",
};

/** The group of one check id (see TEST_GROUPS), null for an id no group knows. */
export function testGroup(id) {
  if (typeof id !== "string") return null;
  if (START_CHECKS.includes(id)) return "start";
  if (BOOT_CHECKS.includes(id) || id.startsWith("start_mode:")) return "boot";
  return TEST_AREAS[id.split(":")[0]] ? "feature" : null;
}

/**
 * The first red check of a test report as { group, id, area }: what the patcher tells Blechy. A report that passed, or
 * whose red checks no group knows, gives null.
 */
export function testFailure(report) {
  for (const c of report?.checks ?? []) {
    if (c.ok) continue;
    const group = testGroup(c.id);
    if (group) return { group, id: c.id, area: group === "feature" ? TEST_AREAS[c.id.split(":")[0]] : null };
  }
  return null;
}

/** Nodes the conversation can start at besides `start`: an app error opens `error`. */
export const ENTRIES = ["error"];

/** The answers to the first question: what the device shows, or that the app is where it sticks. */
export const CASES = [
  { id: "starts", label: "rescue.case.starts", hint: "rescue.case.starts.hint" },
  { id: "prompt", label: "rescue.case.prompt", hint: "rescue.case.prompt.hint" },
  { id: "invalid", label: "rescue.case.invalid", hint: "rescue.case.invalid.hint" },
  { id: "nofile", label: "rescue.case.nofile", hint: "rescue.case.nofile.hint" },
  { id: "zero", label: "rescue.case.zero", hint: "rescue.case.zero.hint" },
  { id: "silent", label: "rescue.case.silent", hint: "rescue.case.silent.hint" },
  { id: "samples", label: "rescue.case.samples", hint: "rescue.case.samples.hint" },
  { id: "app", label: "rescue.case.app", hint: "rescue.case.app.hint" },
  { id: "back", label: "rescue.case.back", hint: "rescue.case.back.hint" },
];

/**
 * The conversation. Each node: Blechy's mood, what he says (`say`, lines; `path` a file path on the card), an official
 * guide for the step if there is one (`source`), and either the answers (`choices`) or the node that follows by itself (`next`).
 * `known` names what the app already knows about the device (KNOWN in site/app/rescue.mjs): Blechy says it and marks the
 * answer whose `value` fits, the person still picks. `read` follows by itself like `next`, to `to[result]` of what the app
 * reads, or to `otherwise` when it reads nothing.
 */
export const FLOW = {
  start: {
    mood: "wave",
    say: ["rescue.say.start.1", "rescue.say.start.2"],
    choices: CASES.map(c => ({ label: c.label, hint: c.hint, to: c.id, id: c.id })),
  },

  // It starts, but something is off.
  starts: {
    mood: "idle",
    say: ["rescue.say.starts.1", "rescue.say.starts.2"],
    choices: [{ label: "rescue.answer.helped", to: "fixed" }, { label: "rescue.answer.notHelped", to: "backup" }],
  },
  fixed: {
    mood: "happy",
    say: ["rescue.say.fixed.1"],
    next: "nocard",
  },
  nocard: {
    mood: "idle",
    say: [
      "rescue.say.nocard.1",
      "rescue.say.nocard.2",
    ],
    choices: [{ label: "rescue.answer.runsWithoutCard", to: "cardfiles" }, { label: "rescue.answer.oddWithoutCard", to: "backup" }],
  },
  cardfiles: {
    mood: "idle",
    say: [
      "rescue.say.cardfiles.1",
      "rescue.say.cardfiles.2",
      { path: "KORG/blechtribe/Plugin/e2sPlugin.all" },
      { path: "KORG/blechtribe/settings.a.bin" },
      { path: "KORG/blechtribe/settings.b.bin" },
      "rescue.say.cardfiles.3",
    ],
    choices: [{ label: "rescue.answer.runsNow", to: "cardfixed" }, { label: "rescue.answer.stillOdd", to: "backup" }],
  },
  cardfixed: {
    mood: "happy",
    say: [
      "rescue.say.cardfixed.1",
      "rescue.say.cardfixed.2",
      { key: "rescue.say.cardfixed.3", links: { issue: { link: "issueNew", text: "rescue.link.issue" } } },
    ],
  },
  backup: {
    mood: "idle",
    say: ["rescue.say.backup.1", "rescue.say.backup.2"],
    choices: [{ label: "rescue.answer.haveIt", to: "which" }, { label: "rescue.answer.dontHave", to: "nobackup" }],
  },
  nobackup: {
    mood: "idle",
    say: ["rescue.say.nobackup.1"],
    next: "color:starts",
  },
  "color:starts": {
    mood: "idle",
    say: ["rescue.say.colorStarts.1"],
    known: "hardware",
    choices: Object.entries(DEVICES).map(([key, d]) => ({ label: d.title, to: `download:starts:${key}`, art: d.body, value: key })),
  },

  which: {
    mood: "idle",
    say: ["rescue.say.which.1"],
    known: "firmware",
    choices: FOLDERS.map((f, i) => ({ label: f.title, to: `folder:${i}`, art: f.body, value: f.path })),
  },

  "update:menu": {
    mood: "idle",
    say: [
      "rescue.say.updateMenu.1",
      "rescue.say.updateMenu.2",
      "rescue.say.updateMenu.3",
    ],
    choices: [
      { label: "rescue.answer.runsAgain", to: "works" },
      { label: "rescue.answer.fails", to: "stuck" },
      { label: "rescue.answer.noFile", to: "nofile:menu" },
      { label: "rescue.answer.invalidFile", to: "invalid:menu" },
    ],
  },

  // The device asks for an update or shows 00: both go through the update prompt with Korg's own firmware.
  prompt: {
    mood: "happy",
    say: ["rescue.say.prompt.1"],
    next: "color:update",
  },
  zero: {
    mood: "happy",
    say: ["rescue.say.zero.1"],
    choices: [{ label: "rescue.answer.pleaseReboot", to: "reboot" }, { label: "rescue.answer.stays00", to: "zero:card" }],
  },
  reboot: {
    mood: "happy",
    say: ["rescue.say.reboot.1"],
    choices: [{ label: "rescue.answer.runsAgain", to: "works" }, { label: "rescue.answer.asksUpdate", to: "prompt" }, { label: "rescue.answer.again00", to: "zero:card" }],
  },
  "zero:card": {
    mood: "idle",
    say: ["rescue.say.zeroCard.1"],
    next: "color:update",
  },
  "color:update": {
    mood: "idle",
    say: ["rescue.say.colorUpdate.1"],
    known: "hardware",
    choices: [
      { label: DEVICES.red.title, to: "download:update:red", art: DEVICES.red.body, value: "red" },
      { label: DEVICES.blue.title, to: "hacktribe:blue", art: DEVICES.blue.body, value: "blue" },
    ],
  },
  // A blue that once had Hacktribe can still take itself for a Sampler when it starts (docs/rettung.md, "Invalid File").
  "hacktribe:blue": {
    mood: "idle",
    say: ["rescue.say.hacktribeBlue.1"],
    choices: [
      { label: "rescue.answer.neverHacktribe", to: "download:update:blue" },
      { label: "rescue.answer.hadHacktribe", to: "sampler:blue" },
      { label: "rescue.answer.dontKnow", to: "download:update:blue" },
    ],
  },
  "sampler:blue": {
    mood: "idle",
    say: ["rescue.say.samplerBlue.1", "rescue.say.samplerBlue.2"],
    next: "download:update:red",
  },

  "update:prompt": {
    mood: "idle",
    say: [
      "rescue.say.updatePrompt.1",
      "rescue.say.updatePrompt.2",
      "rescue.say.updatePrompt.3",
    ],
    choices: [
      { label: "rescue.answer.runsAgain", to: "works" },
      { label: "rescue.answer.fails", to: "stuck" },
      { label: "rescue.answer.noFile", to: "nofile:prompt" },
      { label: "rescue.answer.invalidFile", to: "invalid:prompt" },
    ],
  },

  // "Error, Invalid File": the device found a file that does not fit it and wrote nothing.
  invalid: {
    mood: "happy",
    say: ["rescue.say.invalid.1", "rescue.say.when.1"],
    choices: [{ label: "rescue.answer.atStart", to: "invalid:prompt" }, { label: "rescue.answer.inMenu", to: "invalid:menu" }],
  },
  "invalid:prompt": {
    mood: "idle",
    say: ["rescue.say.invalidPrompt.1"],
    next: "color:update",
  },
  "invalid:menu": {
    mood: "idle",
    say: ["rescue.say.invalidMenu.1"],
    choices: [{ label: "rescue.answer.fromPatcher", to: "invalid:patcher" }, { label: "rescue.answer.korgBack", to: "invalid:korg" }],
  },
  "invalid:patcher": {
    mood: "idle",
    say: [
      "rescue.say.invalidPatcher.1",
      { key: "rescue.say.invalidPatcher.2", links: { patcher: { link: "patcher", text: "nav.patcher" } } },
      "rescue.say.invalidPatcher.3",
    ],
    choices: [{ label: "rescue.answer.blechRuns", to: "updated" }, { label: "rescue.answer.fails", to: "stuck" }],
  },
  "invalid:korg": {
    mood: "idle",
    say: ["rescue.say.invalidKorg.1"],
    choices: [
      { label: DEVICES.red.title, to: "download:starts:red", art: DEVICES.red.body },
      { label: "rescue.answer.blueNoHacktribe", to: "download:starts:blue", art: DEVICES.blue.body },
      { label: "rescue.answer.blueHacktribe", to: "back:head", art: DEVICES.blue.body },
    ],
  },

  // Back to Korg's original while BLECH or Hacktribe runs. `file` names the file step the page adds (site/app/rescue.mjs).
  back: {
    mood: "happy",
    say: ["rescue.say.back.1", "rescue.say.back.2"],
    next: "back:color",
  },
  "back:color": {
    mood: "idle",
    say: ["rescue.say.colorUpdate.1"],
    known: "hardware",
    choices: [
      { label: DEVICES.red.title, to: "download:starts:red", art: DEVICES.red.body, value: "red" },
      { label: DEVICES.blue.title, to: "back:blue", art: DEVICES.blue.body, value: "blue" },
    ],
  },
  "back:blue": {
    mood: "idle",
    say: ["rescue.say.backBlue.1"],
    choices: [
      { label: "rescue.answer.blueSynthSet", to: "download:starts:blue" },
      { label: "rescue.answer.runsHacktribe", to: "back:head" },
    ],
  },
  "back:head": {
    mood: "idle",
    say: ["rescue.say.backHead.1", { key: "rescue.say.download", vars: { name: DEVICES.blue.name }, links: { link: { link: DEVICES.blue.link, text: "rescue.link.korg" } } }, "rescue.say.backHead.2"],
    file: "korgBlueHead",
    choices: [{ label: "rescue.answer.fileSaved", to: "which" }],
  },

  // "Error, No File": nothing where the device looks. The name, the folder System, or the folder of another firmware.
  nofile: {
    mood: "happy",
    say: ["rescue.say.nofile.1", "rescue.say.when.1"],
    choices: [{ label: "rescue.answer.atStart", to: "nofile:prompt" }, { label: "rescue.answer.inMenu", to: "nofile:menu" }],
  },
  "nofile:prompt": {
    mood: "idle",
    say: ["rescue.say.nofilePrompt.1"],
    next: "color:update",
  },
  "nofile:menu": {
    mood: "idle",
    say: [
      "rescue.say.nofileMenu.1",
      "rescue.say.nofileMenu.name",
      "rescue.say.nofileMenu.folder",
      "rescue.say.nofileMenu.renamed",
      "rescue.say.nofileMenu.patcher",
    ],
    next: "nofile:which",
  },
  "nofile:which": {
    mood: "idle",
    say: ["rescue.say.nofileWhich.1"],
    known: "folder",
    choices: FOLDERS.map((f, i) => ({ label: f.title, to: `nofile:folder:${i}`, art: f.body, value: f.path })),
  },
  "nofile:update": {
    mood: "idle",
    say: ["rescue.say.updateMenu.1", "rescue.say.updateMenu.2", "rescue.say.updateMenu.3"],
    choices: [
      { label: "rescue.answer.updateRan", to: "updated" },
      { label: "rescue.answer.againNoFile", to: "ask" },
      { label: "rescue.answer.invalidFile", to: "invalid:menu" },
    ],
  },

  // Hacktribe installed by accident: the samples are gone, the way back is BLECHTRIBE without Hacktribe (docs/messungen/2026-11-06-hacktribe-samples.md).
  samples: {
    mood: "sad",
    say: ["rescue.say.samples.1", "rescue.say.samples.2"],
    choices: [{ label: "rescue.answer.samplesHave", to: "samples:restore" }, { label: "rescue.answer.samplesLost", to: "samples:lost" }],
  },
  "samples:restore": {
    mood: "happy",
    say: ["rescue.say.samplesRestore.1", { path: "KORG/blechtribe/Sample/e2sSample.all" }, "rescue.say.samplesRestore.2"],
    next: "samples:way",
  },
  "samples:lost": {
    mood: "sad",
    say: ["rescue.say.samplesLost.1", "rescue.say.samplesLost.2"],
    next: "samples:way",
  },
  "samples:way": {
    mood: "idle",
    say: [
      { key: "rescue.say.samplesWay.1", links: { patcher: { link: "patcher", text: "nav.patcher" } } },
      "rescue.say.samplesWay.2",
    ],
    known: "hardware",
    choices: Object.entries(DEVICES).map(([key, d]) => ({ label: d.title, to: key === "blue" ? "samples:blue" : "which", art: d.body, value: key })),
  },
  "samples:blue": {
    mood: "idle",
    say: ["rescue.say.samplesBlue.1"],
    choices: [{ label: "rescue.answer.samplesBlueBlech", to: "which" }, { label: "rescue.answer.samplesBlueHt", to: "back:head", art: DEVICES.blue.body }],
  },

  // The device runs; the app, the patcher or the patterns are where it sticks.
  app: {
    mood: "idle",
    say: ["rescue.say.app.1"],
    choices: [
      { label: "rescue.answer.notFound", to: "notfound" },
      { label: "rescue.answer.oldPatterns", to: "export" },
      { label: "rescue.answer.checkFails", to: "test" },
      { label: "rescue.answer.somethingElse", to: "ask" },
    ],
  },

  // An error of the app itself, opened from its toast (site/app/toast.mjs): Blechy quotes it and goes on with its topic.
  error: {
    mood: "idle",
    say: ["rescue.say.error.1", { quote: true }],
    next: "app",
  },

  // The patcher's test is red (tools/emu/check.py): what failed, what it means, and the input to take.
  test: {
    mood: "idle",
    say: ["rescue.say.test.1", "rescue.say.test.2"],
    known: "test",
    choices: [
      ["patch", "rescue.answer.test.patch", "rescue.answer.test.patch.hint"],
      ["start", "rescue.answer.test.start", "rescue.answer.test.start.hint"],
      ["boot", "rescue.answer.test.boot", "rescue.answer.test.boot.hint"],
      ["feature", "rescue.answer.test.feature", "rescue.answer.test.feature.hint"],
      ["run", "rescue.answer.test.run", "rescue.answer.test.run.hint"],
    ].map(([group, label, hint]) => ({ label, hint, to: `test:${group}`, value: group })),
  },
  "test:patch": {
    mood: "idle",
    say: ["rescue.say.testPatch.1", "rescue.say.testPatch.2"],
    next: "normal:patch",
  },
  "test:start": {
    mood: "idle",
    say: ["rescue.say.testStart.1", "rescue.say.testStart.2"],
    next: "normal:start",
  },
  "test:boot": {
    mood: "idle",
    say: ["rescue.say.testBoot.1", "rescue.say.testBoot.2"],
    next: "normal:boot",
  },
  "test:feature": {
    mood: "idle",
    say: ["rescue.say.testFeature.1", "rescue.say.testFeature.2"],
    next: "normal:feature",
  },
  "test:run": {
    mood: "idle",
    say: ["rescue.say.testRun.1", "rescue.say.testRun.2"],
    choices: [{ label: "rescue.answer.checkGreen", to: "app:fixed" }, { label: "rescue.answer.checkRed", to: "check:report" }],
  },
  "test:screenshot": {
    mood: "idle",
    say: ["rescue.say.testScreenshot.1"],
    next: "ask",
  },
  notfound: {
    mood: "idle",
    say: ["rescue.say.notfound.1"],
    read: {
      from: "midi",
      to: {
        korgWindows: "notfound:korgWindows", korgOther: "notfound:korgOther", emu: "notfound:emu", paired: "notfound:paired",
        unpaired: "notfound:report", none: "notfound:none", denied: "notfound:denied", unsupported: "notfound:unsupported",
      },
      otherwise: "notfound:mode",
    },
  },
  "notfound:mode": {
    mood: "idle",
    say: ["rescue.say.notfoundMode.1"],
    choices: [{ label: "mode.emu", to: "notfound:emu" }, { label: "mode.device", to: "notfound:ports" }],
  },
  "notfound:ports": {
    mood: "idle",
    say: [{ key: "rescue.say.notfoundPorts.1", links: { settings: { link: "settings", text: "nav.settings" } } }],
    choices: [
      { label: "rescue.answer.jackNames", to: "notfound:system" },
      { label: "rescue.answer.electribeListed", to: "notfound:report" },
      { label: "rescue.answer.noElectribe", to: "notfound:none" },
    ],
  },
  "notfound:system": {
    mood: "idle",
    say: ["rescue.say.notfoundSystem.1"],
    choices: [{ label: "rescue.answer.windows", to: "notfound:korgWindows" }, { label: "rescue.answer.otherSystem", to: "notfound:korgOther" }],
  },
  "notfound:korgWindows": {
    mood: "idle",
    say: ["rescue.say.korgWindows.1", "rescue.say.korgWindows.2"],
    choices: [{ label: "rescue.answer.foundNow", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "notfound:report" }],
  },
  "notfound:korgOther": {
    mood: "idle",
    say: ["rescue.say.korgOther.1"],
    next: "notfound:report",
  },
  "notfound:emu": {
    mood: "happy",
    say: ["rescue.say.notfoundEmu.1"],
    choices: [{ label: "rescue.answer.foundNow", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "notfound:ports" }],
  },
  "notfound:paired": {
    mood: "idle",
    say: ["rescue.say.notfoundPaired.1"],
    choices: [{ label: "rescue.answer.foundNow", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "notfound:report" }],
  },
  "notfound:none": {
    mood: "idle",
    say: ["rescue.say.notfoundNone.1"],
    choices: [{ label: "rescue.answer.foundNow", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "notfound:report" }],
  },
  "notfound:denied": {
    mood: "idle",
    say: ["rescue.say.notfoundDenied.1"],
    choices: [{ label: "rescue.answer.foundNow", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "notfound:report" }],
  },
  "notfound:unsupported": {
    mood: "idle",
    say: ["rescue.say.notfoundUnsupported.1"],
    choices: [{ label: "rescue.answer.foundNow", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "notfound:report" }],
  },
  "notfound:report": {
    mood: "idle",
    say: [{ key: "rescue.say.notfoundReport.1", links: { settings: { link: "settings", text: "nav.settings" }, discord: { link: "discord", text: "nav.discord" } } }],
    next: "ask",
  },
  export: {
    mood: "happy",
    say: [
      "rescue.say.export.1",
      "rescue.say.export.write",
      "rescue.say.export.folder",
      { path: "KORG/blechtribe/" },
      "rescue.say.export.blue",
      "rescue.say.export.date",
    ],
    choices: [{ label: "rescue.answer.newPatternsNow", to: "app:fixed" }, { label: "rescue.answer.stillOld", to: "ask" }],
  },
  check: {
    mood: "idle",
    say: ["rescue.say.check.1"],
    read: { from: "version", to: { fixed: "check:fixed", old: "check:old" }, otherwise: "check:unknown" },
  },
  "check:old": {
    mood: "idle",
    say: ["rescue.say.checkOld.1", { path: "~/.gelumpe/flash/flash.bin" }, "rescue.say.checkOld.2"],
    choices: [{ label: "rescue.answer.checkGreen", to: "app:fixed" }, { label: "rescue.answer.checkRed", to: "check:report" }],
  },
  "check:unknown": {
    mood: "idle",
    say: ["rescue.say.checkUnknown.1", { path: "~/.gelumpe/flash/flash.bin" }, "rescue.say.checkOld.2"],
    choices: [{ label: "rescue.answer.checkGreen", to: "app:fixed" }, { label: "rescue.answer.checkRed", to: "check:report" }],
  },
  "check:fixed": {
    mood: "idle",
    say: ["rescue.say.checkFixed.1"],
    next: "check:report",
  },
  "check:report": {
    mood: "idle",
    say: ["rescue.say.checkReport.1", { path: "~/.gelumpe/emu.log" }],
    next: "ask",
  },

  // Nothing at all.
  silent: {
    mood: "idle",
    say: ["rescue.say.silent.1"],
    choices: [{ label: "rescue.answer.worksNow", to: "works" }, { label: "rescue.answer.shows00", to: "zero" }, { label: "rescue.answer.asksUpdate", to: "prompt" }, { label: "rescue.answer.stillNothing", to: "dark" }],
  },
  dark: {
    mood: "sad",
    say: ["rescue.say.dark.1"],
    source: DEBRICK,
    next: "ask",
  },

  // How it ends.
  works: {
    mood: "happy",
    say: ["rescue.say.works.1"],
  },
  updated: {
    mood: "happy",
    say: ["rescue.say.updated.1"],
  },
  "app:fixed": {
    mood: "happy",
    say: ["rescue.say.appFixed.1"],
  },
  stuck: {
    mood: "sad",
    say: ["rescue.say.stuck.1"],
    source: DEBRICK,
    next: "ask",
  },
  ask: {
    mood: "wave",
    say: [ASK, LATER],
  },
};

/**
 * The main advice for a red test: a normal firmware as the input. Still red with one, a red function test may be the old
 * emulator flash (`check`), the rest goes to Kuhler Buhler with what the patcher or the emulator reported.
 */
const NORMAL_THEN = { patch: "test:screenshot", start: "check:report", boot: "check:report", feature: "check" };
for (const [group, then] of Object.entries(NORMAL_THEN)) {
  FLOW[`normal:${group}`] = {
    mood: "happy",
    say: [
      { key: "rescue.say.normal.1", links: { hacktribe: { link: "hacktribe", text: "rescue.link.hacktribe" } } },
      { key: "rescue.say.normal.2", links: { red: { link: "korgRed", text: DEVICES.red.title }, blue: { link: "korgBlue", text: DEVICES.blue.title }, patcher: { link: "patcher", text: "nav.patcher" } } },
    ],
    choices: [{ label: "rescue.answer.checkGreen", to: "app:fixed" }, { label: "rescue.answer.normalStillRed", to: then }],
  };
}

const download = (d, to) => ({
  mood: "idle",
  say: [{ key: "rescue.say.download", vars: { name: d.name }, links: { link: { link: d.link, text: "rescue.link.korg" } } }],
  choices: [{ label: "rescue.answer.gotIt", to }],
});
const card = path => ["rescue.say.card", { path }];
/**
 * Where the file has to be, and the offer to look at the card: Blechy finds every .VSB on it and puts the right one
 * there after one click (site/app/rescue.mjs, src/card-check.mjs). An answer with `pick` opens the card; its `to` is
 * where the talk goes on after the look.
 */
const place = (id, { path, heads }, to) => {
  FLOW[id] = { mood: "idle", say: card(path), choices: [{ label: "rescue.answer.onCard", to }, { label: "rescue.answer.showCard", hint: "rescue.answer.showCard.hint", to: `sd:${id}` }] };
  FLOW[`sd:${id}`] = {
    mood: "happy",
    say: ["rescue.say.sd.1", "rescue.say.sd.2"],
    card: { path, heads },
    choices: [{ label: "rescue.answer.pickCard", to, pick: true, id: "card-pick" }, { label: "rescue.answer.onCard", to }],
  };
};

for (const [key, d] of Object.entries(DEVICES)) {
  FLOW[`download:starts:${key}`] = download(d, "which");
  FLOW[`download:update:${key}`] = download(d, `card:${key}`);
  place(`card:${key}`, d, "update:prompt");
}
FOLDERS.forEach((f, i) => {
  FLOW[`folder:${i}`] = { mood: "idle", say: card(f.path), choices: [{ label: "rescue.answer.onCard", to: "update:menu" }] };
  place(`nofile:folder:${i}`, f, "nofile:update");
});

/** The app version whose full check runs the patches' cases on a blank flash, so saved emulator patterns no longer fail it. */
export const CHECK_FIXED = "1.3.7";

/** "fixed" or "old" for an app version like "1.3.6", null without one (the browser has none). */
export function checkVerdict(version) {
  const parts = String(version ?? "").match(/^(\d+)\.(\d+)\.(\d+)/)?.slice(1).map(Number);
  if (!parts) return null;
  const fixed = CHECK_FIXED.split(".").map(Number);
  const i = parts.findIndex((n, k) => n !== fixed[k]);
  return i < 0 || parts[i] > fixed[i] ? "fixed" : "old";
}
