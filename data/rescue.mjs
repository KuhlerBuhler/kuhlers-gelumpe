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
  // the pages of the 2.02 system updates (the same ones src-tauri/src/korg.rs fetches), not the product page
  korgRed: "https://www.korg.com/us/support/download/software/0/368/2579/",
  korgBlue: "https://www.korg.com/us/support/download/software/0/367/2578/",
  // pages of the app itself; they open in place, not in a new tab
  patterns: "#patterns",
  settings: "#settings",
  patcher: "#patcher",
  discord: "#discord",
  plugins: "#scripts",
  baukasten: "#baukasten",
  emulator: "#emu",
  samples: "#sampleset",
  splash: "#splash",
};

/**
 * The two Electribes and where Korg's own firmware for each lives: on Korg's page and on the card. `heads`: the files
 * the update there takes, by their head (src/card-check.mjs), for Blechy's look at the card.
 */
export const DEVICES = {
  red: { title: "rescue.device.red", hint: "rescue.device.red.hint", body: "red", link: "korgRed", name: "Electribe Sampler", zip: "electribe_sampler_system_v202.zip", shot: "img/rescue/korg-download-red.webp", path: "KORG/electribe sampler/System/SYSTEM.VSB", heads: ["sampler"] },
  blue: { title: "rescue.device.blue", hint: "rescue.device.blue.hint", body: "blue", link: "korgBlue", name: "Electribe", zip: "electribe_system_v202.zip", shot: "img/rescue/korg-download-blue.webp", path: "KORG/electribe/System/SYSTEM.VSB", heads: ["synth"] },
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

/**
 * Facts the page carries (rescue.mjs): `set` on an answer adds one, `ask` on a node skips it when a fact is known;
 * `toIf` { fact: { value: node } } redirects an answer by what is known before the answer's own `set`.
 * Facts: case (the first answer), color, firmware (korg, hacktribe, blech, unknown), last (the file put on last, same
 * values), ht, again, goal. `passIf` and `passTo` on a node: when the fact `passIf` is known, it goes on to `passTo`.
 */
const colorChoices = (red, blue, toIf) => Object.entries(DEVICES).map(([key, d]) => ({
  label: d.title, hint: d.hint, to: key === "red" ? red : blue, ...(toIf ? { toIf } : {}), art: d.body, value: key, set: { color: key },
}));

/** What runs now: Korg's own, Hacktribe, BLECHTRIBE, or not known. `to` per answer, `{ to, toIf }` or a node. */
const FIRMWARE = [
  ["korg", "rescue.fw.korg", "rescue.fw.korg.hint"],
  ["hacktribe", "rescue.fw.hacktribe", "rescue.fw.hacktribe.hint"],
  ["blech", "rescue.fw.blech", "rescue.fw.blech.hint"],
  ["unknown", "rescue.answer.dontKnow", "rescue.answer.dontKnow.hint"],
];
const firmwareChoices = to => FIRMWARE.map(([key, label, hint]) => {
  const t = typeof to[key] === "string" ? { to: to[key] } : to[key];
  return { label, hint, ...t, value: key, set: { firmware: key } };
});
/** The folder nodes of the card step by what runs, and the colour for Korg's own. */
const byColor = (red, blue) => ({ to: red, toIf: { color: { red, blue } } });
const FOLDER_NODE = { korg: byColor("folder:korg:red", "folder:korg:blue"), hacktribe: "folder:hacktribe", blech: "folder:blech", unknown: byColor("folder:all:red", "folder:all:blue") };
/**
 * The file put on last, asked before what runs: it marks the answer that fits there (the person still picks), "not known"
 * goes straight to every folder.
 */
const LAST = [
  ["korg", "rescue.last.korg", "rescue.last.korg.hint"],
  ["hacktribe", "rescue.last.hacktribe", "rescue.last.hacktribe.hint"],
  ["blech", "rescue.last.blech", "rescue.last.blech.hint"],
];
const lastFile = to => ({
  mood: "idle",
  say: ["rescue.say.last.1"],
  known: "firmware",
  ask: "last",
  passIf: "firmware",
  passTo: to,
  choices: [
    ...LAST.map(([key, label, hint]) => ({ label, hint, to, value: key, set: { last: key } })),
    { label: "rescue.answer.dontKnow", hint: "rescue.last.dontKnow.hint", ...FOLDER_NODE.unknown, value: "unknown", set: { last: "unknown", firmware: "unknown" } },
  ],
});
const SCAN_NODE = { korg: byColor("sd:folder:korg:red", "sd:folder:korg:blue"), hacktribe: "sd:folder:hacktribe", blech: "sd:folder:blech", unknown: "ask" };

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
  "sample-errors": "rescue.area.samples", "stereo-pad": "rescue.area.samples", "ht-osc": "rescue.area.samples", usersamples: "rescue.area.samples",
  splash: "rescue.area.start", loadbar: "rescue.area.start", migrate: "rescue.area.start",
  fxcard: "rescue.area.card", cardfault: "rescue.area.card", presets: "rescue.area.card", power_off: "rescue.area.card",
  mfx: "rescue.area.sound", ifxidle: "rescue.area.sound", synthfilter: "rescue.area.sound",
  tapmotion: "rescue.area.play", noteassist: "rescue.area.play", dice: "rescue.area.play", beateighth: "rescue.area.play", touchscalezero: "rescue.area.play",
  remote: "rescue.area.midi", sysex: "rescue.area.midi", devmode: "rescue.area.midi", hotpatch: "rescue.area.midi",
  plugin_edit: "rescue.area.plugin", plugin_api15: "rescue.area.plugin", plugin_api18: "rescue.area.plugin", plugin_api19: "rescue.area.plugin", plugin_api22: "rescue.area.plugin", plugin_api23: "rescue.area.plugin", plugin_api24: "rescue.area.plugin", plugin_api25: "rescue.area.plugin", plugin_api35: "rescue.area.plugin", plugin_api36: "rescue.area.plugin", plugin_api26: "rescue.area.plugin", plugin_api27: "rescue.area.plugin", plugin_api28: "rescue.area.plugin", plugin_api29: "rescue.area.plugin", plugin_api30: "rescue.area.plugin", plugin_api31: "rescue.area.plugin", plugin_api31_spectrum: "rescue.area.plugin", plugin_api32: "rescue.area.plugin", plugin_api33: "rescue.area.plugin", plugin_api34: "rescue.area.plugin", plugin_catalog_api: "rescue.area.plugin", plugin_catalog15: "rescue.area.plugin", timers: "rescue.area.plugin", objects: "rescue.area.plugin", live_write: "rescue.area.plugin", global: "rescue.area.plugin", pattern_parts: "rescue.area.plugin", testmode: "rescue.area.plugin",
  dsp: "rescue.area.play",
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

/**
 * The answers to the first question: what the device shows, a problem in the app, or a question about using the app.
 * Ordered by what people ask most on the Discord server (the first ones are FIRST_CASES). A case with `to` goes straight
 * to that node; the others ask the colour first. Every id needs its texts in all languages (`rescue.case.<id>`), its
 * words (data/blechy-words.mjs) and test queries (test/fixtures/blechy-queries.mjs).
 */
export const CASES = [
  { id: "hacktribe", label: "rescue.case.hacktribe", hint: "rescue.case.hacktribe.hint", to: "h:hacktribe" },
  { id: "nofile", label: "rescue.case.nofile", hint: "rescue.case.nofile.hint" },
  { id: "invalid", label: "rescue.case.invalid", hint: "rescue.case.invalid.hint" },
  { id: "install", label: "rescue.case.install", hint: "rescue.case.install.hint", to: "h:install" },
  { id: "check", label: "rescue.case.check", hint: "rescue.case.check.hint", to: "test" },
  { id: "plugins", label: "rescue.case.plugins", hint: "rescue.case.plugins.hint", to: "h:plugins" },
  { id: "notfound", label: "rescue.case.notfound", hint: "rescue.case.notfound.hint", to: "notfound" },
  { id: "silent", label: "rescue.case.silent", hint: "rescue.case.silent.hint" },
  { id: "samples", label: "rescue.case.samples", hint: "rescue.case.samples.hint" },
  { id: "zero", label: "rescue.case.zero", hint: "rescue.case.zero.hint" },
  { id: "prompt", label: "rescue.case.prompt", hint: "rescue.case.prompt.hint" },
  { id: "starts", label: "rescue.case.starts", hint: "rescue.case.starts.hint" },
  { id: "back", label: "rescue.case.back", hint: "rescue.case.back.hint" },
  { id: "app", label: "rescue.case.app", hint: "rescue.case.app.hint", to: "app" },
  { id: "games", label: "rescue.case.games", hint: "rescue.case.games.hint", to: "h:games" },
  { id: "effects", label: "rescue.case.effects", hint: "rescue.case.effects.hint", to: "h:effects" },
  { id: "emulator", label: "rescue.case.emulator", hint: "rescue.case.emulator.hint", to: "h:emulator" },
  { id: "wavs", label: "rescue.case.wavs", hint: "rescue.case.wavs.hint", to: "h:wavs" },
  { id: "updates", label: "rescue.case.updates", hint: "rescue.case.updates.hint", to: "h:updates" },
  { id: "write", label: "rescue.case.write", hint: "rescue.case.write.hint", to: "h:write" },
  { id: "splash", label: "rescue.case.splash", hint: "rescue.case.splash.hint", to: "h:splash" },
];

/**
 * The cases Blechy's field offers before anything is typed; the others come up while typing or under "show all". The
 * order follows what people asked for on the Discord server (docs/rettung.md).
 */
export const FIRST_CASES = ["hacktribe", "nofile", "invalid", "install", "check"];

/** At most this many cases stand in the list at once, typed or not; "show all" lists every one. */
export const MAX_SHOWN = 5;

/** Where the colour question leads, by the case that was picked: every case about the device asks the colour first, once. */
const AFTER_COLOR = { silent: "silent", zero: "zero", prompt: "prompt", invalid: "invalid", nofile: "nofile", starts: "starts", samples: "samples", back: "back", install: "firmware:last" };

/**
 * The conversation. Each node: Blechy's mood, what he says (`say`, lines; `path` a file path on the card, `tree` the same as
 * folders), an official guide for the step if there is one (`source`), and either the answers (`choices`) or the node that
 * follows by itself (`next`). `known` names what the app already knows about the device (KNOWN in site/app/rescue.mjs):
 * Blechy says it and marks the answer whose `value` fits, the person still picks (an `auto` fact is taken without asking).
 * `read` follows by itself like `next`, to `to[result]` of what the app reads, or to `otherwise` when it reads nothing.
 */
export const FLOW = {
  start: {
    mood: "wave",
    say: ["rescue.say.start.1", "rescue.say.start.2", "rescue.say.start.3"],
    // the answers come up under a text field as the person types (site/app/rescue.mjs), not as a wall of buttons
    search: true,
    choices: CASES.map(c => ({ label: c.label, hint: c.hint, to: c.to ?? "color", id: c.id, ...(c.to ? {} : { set: { case: c.id } }) })),
  },
  color: {
    mood: "idle",
    say: ["rescue.say.color.1"],
    known: "hardware",
    ask: "color",
    choices: [...colorChoices("starts", "starts", { case: AFTER_COLOR }), { label: "rescue.answer.dontKnow", to: "color:help" }],
  },
  "color:help": {
    mood: "idle",
    say: ["rescue.say.colorHelp.1"],
    choices: colorChoices("starts", "starts", { case: AFTER_COLOR }),
  },

  // Nothing at all: the power, then the emergency exit, then the way to Kuhler Buhler.
  silent: {
    mood: "idle",
    say: ["rescue.say.silent.1", "rescue.say.silent.2"],
    choices: [
      { label: "rescue.answer.worksNow", to: "ok" },
      { label: "rescue.answer.exitWorks", to: "fixed" },
      { label: "rescue.answer.shows00", to: "zero" },
      { label: "rescue.answer.asksUpdate", to: "prompt" },
      { label: "rescue.answer.stillNothing", to: "dark" },
    ],
  },
  dark: {
    mood: "sad",
    say: ["rescue.say.darkEnd.1"],
    source: DEBRICK,
    next: "ask",
  },

  // It starts, but something is off.
  starts: {
    mood: "idle",
    say: ["rescue.say.starts.1", "rescue.say.starts.2"],
    choices: [
      { label: "rescue.answer.helped", to: "fixed" },
      { label: "rescue.answer.notHelped", to: "backup" },
      { label: "rescue.answer.samplesWrong", to: "samples" },
    ],
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
    say: ["rescue.say.backup.1", { key: "rescue.say.keeps", links: { patterns: { link: "patterns", text: "rescue.link.patterns" } } }, "rescue.say.backup.2"],
    choices: [{ label: "rescue.answer.haveIt", to: "firmware:last" }, { label: "rescue.answer.dontHave", to: "nobackup" }],
  },
  nobackup: {
    mood: "idle",
    say: ["rescue.say.nobackup.1"],
    next: "back:firmware",
  },

  // What runs now decides the folder on the card; asked once, "not known" puts the file in every folder.
  "firmware:last": lastFile("firmware:file"),
  "firmware:file": {
    mood: "idle",
    say: ["rescue.say.firmware.1"],
    known: "firmware",
    ask: "firmware",
    choices: firmwareChoices(FOLDER_NODE),
  },

  "update:menu": {
    mood: "idle",
    say: [
      "rescue.say.updateMenu.1",
      "rescue.say.updateMenu.2",
      { keys: "menu" },
      "rescue.say.updateMenu.3",
    ],
    choices: [
      { label: "rescue.answer.runsAgain", to: "works", toIf: { goal: { blech: "updated" } } },
      { label: "rescue.answer.fails", to: "recheck", toIf: { again: { yes: "stuck" } }, set: { again: "yes" } },
      { label: "rescue.answer.noFile", to: "nofile:menu" },
      { label: "rescue.answer.invalidFile", to: "invalid:menu" },
    ],
  },
  // The update did not work: once more the card, then what the device shows now.
  recheck: {
    mood: "idle",
    say: ["rescue.say.recheck.1"],
    ask: "firmware",
    choices: firmwareChoices(SCAN_NODE),
  },
  "recheck:prompt": {
    mood: "idle",
    say: ["rescue.say.recheck.1"],
    ask: "color",
    choices: colorChoices("sd:card:red", "sd:card:blue"),
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
    choices: [{ label: "rescue.answer.runsAgain", to: "ok" }, { label: "rescue.answer.asksUpdate", to: "prompt" }, { label: "rescue.answer.again00", to: "zero:card" }],
  },
  "zero:card": {
    mood: "idle",
    say: ["rescue.say.zeroCard.1"],
    next: "color:update",
  },
  // The card did not bring a way out of 00: the panel does not talk to the board (docs/rettung.md, case 3).
  "zero:cable": {
    mood: "sad",
    say: ["rescue.say.zeroCable.1"],
    source: DEBRICK,
    next: "ask",
  },
  "color:update": {
    mood: "idle",
    say: ["rescue.say.color.1"],
    known: "hardware",
    ask: "color",
    choices: colorChoices("download:update:red", "hacktribe:blue"),
  },
  // A blue that once had Hacktribe can still take itself for a Sampler when it starts (docs/rettung.md, "Invalid File").
  "hacktribe:blue": {
    mood: "idle",
    say: ["rescue.say.hacktribeBlue.1"],
    ask: "ht",
    choices: [
      { label: "rescue.answer.neverHacktribe", to: "download:update:blue", set: { ht: "no" } },
      { label: "rescue.answer.hadHacktribe", to: "sampler:blue", set: { ht: "yes" } },
      { label: "rescue.answer.dontKnow", to: "download:update:blue", set: { ht: "no" } },
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
      { keys: "enter" },
      "rescue.say.updatePrompt.3",
    ],
    choices: [
      { label: "rescue.answer.runsAgain", to: "works" },
      { label: "rescue.answer.noPrompt", to: "noprompt" },
      { label: "rescue.answer.fails", to: "recheck:prompt", toIf: { again: { yes: "stuck" } }, set: { again: "yes" } },
      { label: "rescue.answer.noFile", to: "nofile:prompt" },
      { label: "rescue.answer.invalidFile", to: "invalid:prompt" },
    ],
  },
  // No prompt: Hacktribe and BLECHTRIBE take both machine IDs, so the card is not their way in; the menu is, or the emergency exit.
  noprompt: {
    mood: "idle",
    say: ["rescue.say.noPrompt.1", "rescue.say.noPrompt.2"],
    choices: [{ label: "rescue.answer.reachesMenu", to: "firmware:last" }, { label: "rescue.answer.noMenu", to: "silent" }],
  },

  // "Error, Invalid File": the device found a file that does not fit it and wrote nothing.
  invalid: {
    mood: "happy",
    say: ["rescue.say.invalid.1", "rescue.say.invalid.2", "rescue.say.when.1"],
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
    choices: [{ label: "rescue.answer.fromPatcher", to: "invalid:patcher" }, { label: "rescue.answer.korgBack", to: "back:firmware", set: { ht: "yes" } }],
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

  // Back to Korg's original while BLECH or Hacktribe runs: what runs decides whether the file is Korg's own or the one with
  // the Sampler head (`file` is the file step the page adds, `done` where it goes on), then the folder.
  back: {
    mood: "happy",
    say: ["rescue.say.back.1", "rescue.say.back.2", { key: "rescue.say.keeps", links: { patterns: { link: "patterns", text: "rescue.link.patterns" } } }],
    next: "back:firmware",
  },
  "back:firmware": {
    mood: "idle",
    say: ["rescue.say.firmware.1"],
    known: "firmware",
    ask: "firmware",
    choices: firmwareChoices({
      korg: "back:already",
      hacktribe: { to: "download:red:go", toIf: { color: { red: "download:red:go", blue: "back:head" } } },
      blech: { to: "download:red:go", toIf: { color: { red: "download:red:go", blue: "back:blueHt" } } },
      unknown: { to: "download:red:go", toIf: { color: { red: "download:red:go", blue: "back:blueHt" } } },
    }),
  },
  "back:already": {
    mood: "happy",
    say: ["rescue.say.backAlready.1"],
    choices: [{ label: "rescue.answer.worksNow", to: "ok" }, { label: "rescue.answer.stillOdd", to: "starts" }],
  },
  "back:blueHt": {
    mood: "idle",
    say: ["rescue.say.backBlueHt.1"],
    ask: "ht",
    choices: [
      { label: "rescue.answer.blueNoHt", to: "download:blue:go", set: { ht: "no" } },
      { label: "rescue.answer.blueHt", to: "back:head", set: { ht: "yes" } },
      { label: "rescue.answer.dontKnow", to: "download:blue:go", set: { ht: "no" } },
    ],
  },
  "back:head": {
    mood: "idle",
    say: ["rescue.say.backHeadWhy.1", { key: "rescue.say.download", vars: { name: DEVICES.blue.name }, links: { link: { link: DEVICES.blue.link, text: "rescue.link.korg" } } }, { key: "rescue.say.downloadFile", vars: { file: DEVICES.blue.zip } }, { shot: DEVICES.blue.shot }, "rescue.say.backHeadFile.1"],
    file: "korgBlueHead",
    done: "firmware:last",
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
      "rescue.say.nofileMenu.renamed",
      "rescue.say.nofileMenu.patcher",
    ],
    next: "nofile:last",
  },
  "nofile:last": lastFile("nofile:which"),
  "nofile:which": {
    mood: "idle",
    say: ["rescue.say.nofileWhich.1"],
    known: "firmware",
    ask: "firmware",
    choices: firmwareChoices(FOLDER_NODE),
  },
  "nofile:update": {
    mood: "idle",
    say: ["rescue.say.updateMenu.1", "rescue.say.updateMenu.2", { keys: "menu" }, "rescue.say.updateMenu.3"],
    choices: [
      { label: "rescue.answer.updateRan", to: "updated" },
      { label: "rescue.answer.againNoFile", to: "recheck", toIf: { again: { yes: "ask" } }, set: { again: "yes" } },
      { label: "rescue.answer.invalidFile", to: "invalid:menu" },
    ],
  },

  // Hacktribe, or Hacktribe and BLECHTRIBE, on the device and the samples are not as they were
  // (docs/messungen/2026-11-06-hacktribe-samples.md). The way back is BLECHTRIBE without Hacktribe.
  samples: {
    mood: "sad",
    say: ["rescue.say.samplesWhy.1", "rescue.say.samplesHt.1"],
    choices: [
      { label: "rescue.answer.samplesHt", to: "samples:flash" },
      { label: "rescue.answer.samplesNoHt", to: "samples:other" },
      { label: "rescue.answer.dontKnow", to: "samples:other" },
    ],
  },
  "samples:other": {
    mood: "idle",
    say: ["rescue.say.samplesOther.1"],
    next: "starts",
  },
  // The sounds stay in the device flash; Hacktribe only does not read them, a firmware without it does again.
  "samples:flash": {
    mood: "happy",
    say: ["rescue.say.samplesFlash.1"],
    next: "samples:firmware",
  },
  "samples:firmware": {
    mood: "idle",
    say: ["rescue.say.firmware.1"],
    known: "firmware",
    ask: "firmware",
    choices: firmwareChoices({
      korg: "samples:way",
      hacktribe: { to: "samples:way", toIf: { color: { red: "samples:way", blue: "samples:head" } } },
      blech: { to: "samples:way", toIf: { color: { red: "samples:way", blue: "samples:blueHt" } } },
      unknown: { to: "samples:way", toIf: { color: { red: "samples:way", blue: "samples:head" } } },
    }),
  },
  // On the blue the patcher's file from Korg's original has the blue head, which only a firmware without Hacktribe takes;
  // BLECHTRIBE with Hacktribe says "Invalid File" to it (docs/messungen/2026-11-08-rettung-alle-ordner.md). The app cannot
  // tell which BLECHTRIBE runs, so it asks; not known takes the way for Hacktribe, which samples missing point to.
  "samples:blueHt": {
    mood: "idle",
    say: ["rescue.say.samplesBlueHt.1"],
    ask: "ht",
    choices: [
      { label: "rescue.answer.blueNoHt", to: "samples:way", set: { ht: "no" } },
      { label: "rescue.answer.blueHt", to: "samples:head", set: { ht: "yes" } },
      { label: "rescue.answer.dontKnow", to: "samples:head", set: { ht: "yes" } },
    ],
  },
  // The patcher builds BLECHTRIBE from Korg's original; its file goes to the folder of what runs now. On the red every
  // firmware takes it (Sampler head), on the blue only Korg's own and BLECHTRIBE without Hacktribe (blue head).
  "samples:way": {
    mood: "idle",
    say: [{ key: "rescue.say.samplesWay.1", links: { patcher: { link: "patcher", text: "nav.patcher" } } }, "rescue.say.samplesFile.1"],
    choices: [{ label: "rescue.answer.fileReady", to: "firmware:last", set: { goal: "blech" } }],
  },
  // Hacktribe on a blue, alone or in BLECHTRIBE, takes only a file with the Sampler head: first back to Korg's original,
  // BLECHTRIBE after that.
  "samples:head": {
    mood: "idle",
    say: ["rescue.say.samplesHead.1"],
    next: "back:head",
  },

  // The device runs; the app, the patcher or the patterns are where it sticks.
  app: {
    mood: "idle",
    say: ["rescue.say.app.1"],
    choices: [
      { label: "rescue.answer.notFound", to: "notfound" },
      { label: "rescue.answer.emuNotRunning", to: "h:emulator:fix" },
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

  // How it ends. `works` only after a file went onto the card, `ok` when the device came back without one.
  works: {
    mood: "happy",
    say: ["rescue.say.works.1", { key: "rescue.say.worksAgain.1", links: { patcher: { link: "patcher", text: "nav.patcher" } } }],
  },
  ok: {
    mood: "happy",
    say: ["rescue.say.ok.1"],
  },
  updated: {
    mood: "happy",
    say: ["rescue.say.updated.1"],
  },
  "app:fixed": {
    mood: "happy",
    say: ["rescue.say.appFixed.1"],
  },
  // A way did not help: what the device shows now sends it to the matching way, the last stop is Kuhler Buhler.
  stuck: {
    mood: "sad",
    say: ["rescue.say.stuckAsk.1"],
    choices: [
      { label: "rescue.answer.stays00", to: "zero:cable" },
      { label: "rescue.case.prompt", to: "prompt" },
      { label: "rescue.answer.noFile", to: "nofile" },
      { label: "rescue.answer.invalidFile", to: "invalid" },
      { label: "rescue.answer.stillNothing", to: "dark" },
      { label: "rescue.answer.somethingElse", to: "ask" },
    ],
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

/**
 * Questions about using the app, not about a device that went wrong (the cases with a `to` that starts with "h:"). Each
 * node says what to do in a few lines and ends with "helped" or the way to the contact. An error of a page of the app
 * opens the node of that page (`help` of the toast, site/app/toast.mjs).
 */
const HELP_END = [{ label: "rescue.answer.helped", to: "helpdone" }, { label: "rescue.answer.somethingElse", to: "ask" }];
/** An answer that goes on with a device case: the colour first, then that case's way. */
const viaColor = (label, id) => ({ label, to: "color", set: { case: id } });
const pageLink = (name, text) => ({ [name]: { link: name, text } });
const help = (id, mood, say, choices = []) => { FLOW[`h:${id}`] = { mood, say, choices: [...choices, ...HELP_END] }; };
help("install", "happy", [
  { key: "rescue.help.install.1", links: pageLink("patcher", "nav.patcher") },
  "rescue.help.install.2",
  "rescue.help.install.3",
], [viaColor("rescue.answer.whichFolder", "install"), viaColor("rescue.answer.noFile", "nofile"), viaColor("rescue.answer.invalidFile", "invalid")]);
help("hacktribe", "idle", ["rescue.help.hacktribe.1", "rescue.help.hacktribe.2", "rescue.help.hacktribe.3"], [viaColor("rescue.case.samples", "samples"), viaColor("rescue.case.back", "back")]);
help("plugins", "happy", [
  { key: "rescue.help.plugins.1", links: pageLink("plugins", "nav.scripts") },
  "rescue.help.plugins.2",
  { path: "KORG/blechtribe/Plugin/" },
  "rescue.help.plugins.3",
], [{ label: "rescue.answer.howGames", to: "h:games" }, { label: "rescue.case.effects", to: "h:effects" }]);
help("games", "happy", [{ key: "rescue.help.games.1", links: pageLink("plugins", "nav.scripts") }, "rescue.help.games.2"], [{ label: "rescue.answer.gameMissing", to: "h:plugins" }]);
help("effects", "idle", [
  { key: "rescue.help.effects.1", links: pageLink("baukasten", "nav.baukasten") },
  "rescue.help.effects.2",
  { path: "KORG/blechtribe/Presets/" },
  "rescue.help.effects.3",
]);
help("emulator", "idle", [{ key: "rescue.help.emulator.1", links: pageLink("emulator", "nav.emu") }, "rescue.help.emulator.2"], [{ label: "rescue.answer.emuNotRunning", to: "h:emulator:fix" }]);
// The emulator of the app does not run: where an error of the Emulator page leads.
FLOW["h:emulator:fix"] = {
  mood: "idle",
  say: ["rescue.help.emulatorFix.1", "rescue.help.emulatorFix.2", { path: "~/.gelumpe/emu.log" }, "rescue.help.emulatorFix.3"],
  choices: [{ label: "rescue.answer.emuRuns", to: "app:fixed" }, { label: "rescue.answer.stillNotFound", to: "check:report" }],
};
help("wavs", "idle", [{ key: "rescue.help.wavs.1", links: pageLink("samples", "nav.sampleset") }, "rescue.help.wavs.2", "rescue.help.wavs.3"], [viaColor("rescue.case.samples", "samples")]);
help("updates", "idle", [
  { key: "rescue.help.updates.1", links: pageLink("patcher", "nav.patcher") },
  "rescue.help.updates.2",
  "rescue.help.updates.3",
], [viaColor("rescue.answer.noFile", "nofile"), viaColor("rescue.answer.invalidFile", "invalid")]);
help("write", "idle", ["rescue.help.write.1", "rescue.help.write.2"]);
help("splash", "idle", [
  { key: "rescue.help.splash.1", links: pageLink("splash", "nav.splash") },
  { path: "KORG/blechtribe/" },
  "rescue.help.splash.2",
]);
FLOW.helpdone = { mood: "happy", say: ["rescue.help.done.1"] };

/** Korg's file: the exact page of the 2.02 update and the version, only said once it is clear which one is needed. */
const download = (d, to) => ({
  mood: "idle",
  say: [
    { key: "rescue.say.download", vars: { name: d.name }, links: { link: { link: d.link, text: "rescue.link.korg" } } },
    { key: "rescue.say.downloadFile", vars: { file: d.zip } },
    { shot: d.shot },
  ],
  choices: [{ label: "rescue.answer.gotIt", to }],
});
const tree = path => ({ tree: path });
/**
 * Where the file has to be, and the offer to look at the card: Blechy finds every .VSB on it and puts the right one
 * there after one click (site/app/rescue.mjs, src/card-check.mjs). An answer with `pick` opens the card; its `to` is
 * where the talk goes on after the look. `note` explains why the folder has this name. The look comes first, "I checked
 * it myself" second.
 */
const place = (id, { path, heads }, to, { toIf, note } = {}) => {
  const go = toIf ? { to, toIf } : { to };
  FLOW[id] = {
    mood: "idle",
    say: ["rescue.say.card", tree(path), ...[note].flat()].filter(Boolean),
    choices: [{ label: "rescue.answer.showCard", hint: "rescue.answer.showCard.hint", to: `sd:${id}` }, { label: "rescue.answer.onCard", ...go }],
  };
  FLOW[`sd:${id}`] = {
    mood: "happy",
    say: ["rescue.say.sd.1", "rescue.say.sd.2"],
    card: { path, heads },
    choices: [{ label: "rescue.answer.pickCard", hint: "rescue.answer.pickCard.hint", ...go, pick: true, id: "card-pick" }, { label: "rescue.answer.onCard", ...go }],
  };
};

for (const [key, d] of Object.entries(DEVICES)) {
  FLOW[`download:update:${key}`] = download(d, `card:${key}`);
  FLOW[`download:${key}:go`] = download(d, "firmware:last");
  place(`card:${key}`, d, "update:prompt", { note: "rescue.say.cardBoot" });
}
// The folder of the running firmware; the menu update reads it, whatever the update is for.
// The second line of the note names the folder that is shown, so it never speaks of another one.
const MENU = { toIf: { case: { nofile: "nofile:update" } }, note: "rescue.say.cardFolder" };
const [KORG_RED, KORG_BLUE, HACKTRIBE, BLECH] = FOLDERS;
place("folder:korg:red", KORG_RED, "update:menu", MENU);
place("folder:korg:blue", KORG_BLUE, "update:menu", MENU);
place("folder:hacktribe", HACKTRIBE, "update:menu", { ...MENU, note: [MENU.note, "rescue.say.cardFolder.hacktribe"] });
place("folder:blech", BLECH, "update:menu", { ...MENU, note: [MENU.note, "rescue.say.cardFolder.blech"] });
// Not known what runs: Korg's folder of the colour, Hacktribe's and BLECHTRIBE's, the update reads only the one that fits.
for (const [key, d] of Object.entries(DEVICES)) {
  FLOW[`folder:all:${key}`] = {
    mood: "idle",
    say: ["rescue.say.cardAll", tree(d.path), tree(HACKTRIBE.path), tree(BLECH.path), "rescue.say.cardFolder"],
    choices: [{ label: "rescue.answer.onCard", to: "update:menu", toIf: { case: { nofile: "nofile:update" } } }],
  };
}


/** Where an answer leads: its `to`, or what `toIf` says for a fact known so far. */
export const destOf = (choice, facts) => {
  for (const [fact, map] of Object.entries(choice.toIf ?? {})) if (facts[fact] != null && map[facts[fact]]) return map[facts[fact]];
  return choice.to;
};

/** The step a talk is at after passing every step that asks for a fact already known: { id, facts } (nodes: FLOW and the page's own). */
export function passSteps(id, facts, nodes = FLOW) {
  for (let guard = 0; guard < 8; guard++) {
    const node = nodes[id];
    if (node.passIf && facts[node.passIf] != null) { id = node.passTo; continue; }
    const c = node.ask && facts[node.ask] != null ? node.choices?.find(c => c.set?.[node.ask] === facts[node.ask]) : null;
    if (!c) break;
    facts = { ...facts, ...c.set };
    id = destOf(c, facts);
  }
  return { id, facts };
}

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
