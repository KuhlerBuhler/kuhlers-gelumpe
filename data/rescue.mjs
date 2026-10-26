/**
 * What the Rettung page (site/app/rescue.mjs) says: a conversation with Blechy for someone who knows little about the
 * device and is worried. Only the answers, in plain words; where an official guide covers a step, `source` names it.
 * The evidence behind each step is in docs/rettung.md.
 */

export const LINKS = {
  debrick: "https://github.com/bangcorrupt/hacktribe/wiki/Debrick",
  issues: "https://github.com/KuhlerBuhler/kuhlers-gelumpe/issues",
  instagram: "https://www.instagram.com/kuhler_buhler/",
  korgRed: "https://www.korg.com/us/support/download/product/0/368/#software",
  korgBlue: "https://www.korg.com/us/support/download/product/0/367/#software",
};

/** The two Electribes and where Korg's own firmware for each lives: on Korg's page and on the card. */
export const DEVICES = {
  red: { title: "rescue.device.red", body: "red", link: "korgRed", name: "Electribe Sampler", path: "KORG/electribe sampler/System/SYSTEM.VSB" },
  blue: { title: "rescue.device.blue", body: "blue", link: "korgBlue", name: "Electribe", path: "KORG/electribe/System/SYSTEM.VSB" },
};

/** The folder the running firmware reads its update from. Every folder is checked on devices with version 1.2. */
export const FOLDERS = [
  { title: "rescue.folder.red", body: "red", path: "KORG/electribe sampler/System/SYSTEM.VSB" },
  { title: "rescue.folder.blue", body: "blue", path: "KORG/electribe/System/SYSTEM.VSB" },
  { title: "rescue.folder.hacktribe", body: "grey", path: "KORG/hacktribe/System/SYSTEM.VSB" },
  { title: "rescue.folder.blech", body: "grey", path: "KORG/blechtribe/System/SYSTEM.VSB" },
];

/** Where to ask: a line with links, `{name}` in its text is the link `links.name`, whose `link` is a key of LINKS. */
const ASK = { key: "rescue.say.ask", links: { issue: { link: "issueNew", text: "rescue.link.issue" }, instagram: { link: "instagram", text: "rescue.link.instagram" } } };
/** The guide the Hacktribe project keeps for a device that no longer starts. */
const DEBRICK = [{ link: "debrick", text: "rescue.link.debrick" }];
const LATER = "rescue.say.later";

export const BUTTONS = { again: "rescue.again", back: "rescue.back" };

/** The four answers to the first question. */
export const CASES = [
  { id: "starts", label: "rescue.case.starts", hint: "rescue.case.starts.hint" },
  { id: "prompt", label: "rescue.case.prompt", hint: "rescue.case.prompt.hint" },
  { id: "zero", label: "rescue.case.zero", hint: "rescue.case.zero.hint" },
  { id: "silent", label: "rescue.case.silent", hint: "rescue.case.silent.hint" },
];

/**
 * The conversation. Each node: Blechy's mood, what he says (`say`, lines; `path` a file path on the card), an official
 * guide for the step if there is one (`source`), and either the answers (`choices`) or the node that follows by itself (`next`).
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
    choices: Object.entries(DEVICES).map(([key, d]) => ({ label: d.title, to: `download:starts:${key}`, art: d.body })),
  },

  which: {
    mood: "idle",
    say: ["rescue.say.which.1"],
    choices: FOLDERS.map((f, i) => ({ label: f.title, to: `folder:${i}`, art: f.body })),
  },

  "update:menu": {
    mood: "idle",
    say: [
      "rescue.say.updateMenu.1",
      "rescue.say.updateMenu.2",
      "rescue.say.updateMenu.3",
    ],
    choices: [{ label: "rescue.answer.runsAgain", to: "works" }, { label: "rescue.answer.fails", to: "stuck" }],
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
    choices: Object.entries(DEVICES).map(([key, d]) => ({ label: d.title, to: `download:update:${key}`, art: d.body })),
  },


  "update:prompt": {
    mood: "idle",
    say: [
      "rescue.say.updatePrompt.1",
      "rescue.say.updatePrompt.2",
      "rescue.say.updatePrompt.3",
    ],
    choices: [{ label: "rescue.answer.runsAgain", to: "works" }, { label: "rescue.answer.fails", to: "stuck" }],
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

const download = (d, to) => ({
  mood: "idle",
  say: [{ key: "rescue.say.download", vars: { name: d.name }, links: { link: { link: d.link, text: "rescue.link.korg" } } }],
  choices: [{ label: "rescue.answer.gotIt", to }],
});
const card = path => ["rescue.say.card", { path }];

for (const [key, d] of Object.entries(DEVICES)) {
  FLOW[`download:starts:${key}`] = download(d, "which");
  FLOW[`download:update:${key}`] = download(d, `card:${key}`);
  FLOW[`card:${key}`] = { mood: "idle", say: card(d.path), choices: [{ label: "rescue.answer.onCard", to: "update:prompt" }] };
}
FOLDERS.forEach((f, i) => {
  FLOW[`folder:${i}`] = {
    mood: "idle",
    say: card(f.path),
    choices: [{ label: "rescue.answer.onCard", to: "update:menu" }],
  };
});
