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
  red: { title: "Rot: Electribe Sampler", body: "red", link: "korgRed", name: "Electribe Sampler", path: "KORG/electribe sampler/System/SYSTEM.VSB" },
  blue: { title: "Blau: Electribe", body: "blue", link: "korgBlue", name: "Electribe", path: "KORG/electribe/System/SYSTEM.VSB" },
};

/** The folder the running firmware reads its update from. Every folder is checked on devices with version 1.2. */
export const FOLDERS = [
  { title: "Korg Electribe 2 Sampler", body: "red", path: "KORG/electribe sampler/System/SYSTEM.VSB" },
  { title: "Korg Electribe 2", body: "blue", path: "KORG/electribe/System/SYSTEM.VSB" },
  { title: "Electribe 2 / 2s + Hacktribe", body: "grey", path: "KORG/hacktribe/System/SYSTEM.VSB" },
  { title: "Electribe 2 / 2s + BLECHTRIBE (+ Hacktribe optional)", body: "grey", path: "KORG/blechtribe/System/SYSTEM.VSB" },
];

/** Where to ask; a line of parts where { link } is a key of LINKS. */
const ASK = [
  "Dann melde dich direkt bei Kuhler Buhler, der hat das gebaut: Schick ein Foto vom Display und schreib kurz, was du zuletzt gemacht hast, ",
  { link: "issueNew", text: "als GitHub Issue" }, " (deine Antworten hier stehen dann schon drin) oder auf Instagram an ", { link: "instagram", text: "@kuhler_buhler" }, ".",
];
/** The guide the Hacktribe project keeps for a device that no longer starts. */
const DEBRICK = [{ link: "debrick", text: "Debrick-Anleitung von Hacktribe" }];
const LATER = "Kriegen wir es zusammen hin, kommt der Weg hier mit rein, damit er dem Nächsten gleich hilft.";

export const BUTTONS = { again: "Von vorn", back: "Zurück" };

/** The four answers to the first question. */
export const CASES = [
  { id: "starts", label: "Sie startet, aber etwas spinnt", hint: "Das Menü hängt, zeigt Unsinn, oder ein Patch oder Plugin macht Ärger." },
  { id: "prompt", label: "Da steht SOFTWARE UPDATE und press ENTER", hint: "Sie fragt nach einem Update, statt normal zu starten." },
  { id: "zero", label: "Das Display zeigt nur 00", hint: "Sonst passiert nichts." },
  { id: "silent", label: "Gar nichts, das Display bleibt dunkel oder hängt", hint: "Auch nach einer Weile kommt keine Frage." },
];

/**
 * The conversation. Each node: Blechy's mood, what he says (`say`, lines; `path` a file path on the card), an official
 * guide for the step if there is one (`source`), and either the answers (`choices`) or the node that follows by itself (`next`).
 */
export const FLOW = {
  start: {
    mood: "wave",
    say: ["Moin, ich bin Blechy. Keine Sorge, meistens kriegen wir das wieder hin.", "Was siehst du, wenn du deine Electribe einschaltest?"],
    choices: CASES.map(c => ({ label: c.label, hint: c.hint, to: c.id, id: c.id })),
  },

  // It starts, but something is off.
  starts: {
    mood: "idle",
    say: ["Dann probieren wir erst das Einfachste.", "Drück einmal EXIT. Hängt es weiter: ausschalten, EXIT gedrückt halten und dabei wieder einschalten. Dann startet sie dieses eine Mal ganz normal, ohne die BLECHTRIBE-Funktionen."],
    choices: [{ label: "Hat geholfen", to: "fixed" }, { label: "Hilft nicht", to: "backup" }],
  },
  fixed: {
    mood: "happy",
    say: ["Jut! Mit gehaltenem EXIT lief sie aber nur dieses eine Mal ohne BLECHTRIBE. Spinnt sie beim nächsten normalen Start wieder, komm zurück, dann spielen wir die alte Firmware zurück."],
  },
  backup: {
    mood: "idle",
    say: ["Dann spielen wir die alte Firmware zurück, das ist Korgs normaler Update-Weg.", "Hast du die Original-SYSTEM.VSB, die du vor dem Patchen gesichert hast?"],
    choices: [{ label: "Ja, hab ich", to: "which" }, { label: "Nein, oder weiß nicht", to: "nobackup" }],
  },
  nobackup: {
    mood: "idle",
    say: ["Macht nichts, Korgs Original-Firmware tut es genauso. Die holen wir uns direkt bei Korg."],
    next: "color:starts",
  },
  "color:starts": {
    mood: "idle",
    say: ["Welche Farbe hat deine Electribe?"],
    choices: Object.entries(DEVICES).map(([key, d]) => ({ label: d.title, to: `download:starts:${key}`, art: d.body })),
  },

  which: {
    mood: "idle",
    say: ["Welche Firmware läuft gerade auf deiner Electribe? Hast du sie mit unserem Patcher gepatcht, ist es die unterste."],
    choices: FOLDERS.map((f, i) => ({ label: f.title, to: `folder:${i}`, art: f.body })),
  },

  "update:menu": {
    mood: "idle",
    say: [
      "Karte zurück in die Electribe, Netzteil anschließen, einschalten.",
      "Dann: Menü -> DATA UTILITY -> SOFTWARE UPDATE. Pass auf, direkt davor steht FACTORY RESET, das nicht nehmen.",
      "Bestätige das Update und warte, bis es fertig ist. In der Zeit nicht ausschalten. Danach einmal aus- und wieder einschalten.",
    ],
    choices: [{ label: "Läuft wieder", to: "works" }, { label: "Klappt nicht", to: "stuck" }],
  },

  // The device asks for an update or shows 00: both go through the update prompt with Korg's own firmware.
  prompt: {
    mood: "happy",
    say: ["Das sieht schlimmer aus, als es ist. Die Electribe passt beim Start nicht zu der Firmware, die drauf ist, und fragt deshalb nach einem Update. Das geben wir ihr: Korgs Original-Firmware für ihre Farbe."],
    next: "color:update",
  },
  zero: {
    mood: "happy",
    say: ["Das kenn ich. Bei 00 richtet die Electribe gerade ihr Bedienfeld neu ein. Lass sie eingeschaltet und warte ein, zwei Minuten."],
    choices: [{ label: "Jetzt steht da Please Reboot", to: "reboot" }, { label: "Es bleibt bei 00", to: "zero:card" }],
  },
  reboot: {
    mood: "happy",
    say: ["Gut so. Schalte sie einmal aus und wieder ein."],
    choices: [{ label: "Läuft wieder", to: "works" }, { label: "Jetzt fragt sie nach einem Update", to: "prompt" }, { label: "Wieder 00", to: "zero:card" }],
  },
  "zero:card": {
    mood: "idle",
    say: ["Dann versuchen wir es mit Korgs Original-Firmware auf der SD-Karte. So hat es bei uns an einem Gerät schon geholfen."],
    next: "color:update",
  },
  "color:update": {
    mood: "idle",
    say: ["Welche Farbe hat deine Electribe?"],
    choices: Object.entries(DEVICES).map(([key, d]) => ({ label: d.title, to: `download:update:${key}`, art: d.body })),
  },


  "update:prompt": {
    mood: "idle",
    say: [
      "Karte zurück in die Electribe, Netzteil anschließen, einschalten.",
      "Sie fragt jetzt nach dem Update: ENTER drücken, das ist die Taste MENU. Warte, bis \"Please Reboot\" kommt, und schalte sie in der Zeit nicht aus. Dann einmal aus- und wieder einschalten.",
      "Mit Batterien meldet sie \"Battery Low\" und macht nichts, deshalb das Netzteil.",
    ],
    choices: [{ label: "Läuft wieder", to: "works" }, { label: "Klappt nicht", to: "stuck" }],
  },

  // Nothing at all.
  silent: {
    mood: "idle",
    say: ["Erst mal das Naheliegende: Steckt das Netzteil richtig, oder sind die Batterien voll? Schalte sie danach noch einmal ein und warte kurz."],
    choices: [{ label: "Jetzt geht sie", to: "works" }, { label: "Jetzt steht da 00", to: "zero" }, { label: "Jetzt fragt sie nach einem Update", to: "prompt" }, { label: "Immer noch nichts", to: "dark" }],
  },
  dark: {
    mood: "sad",
    say: ["Das ist leider der schwierigste Fall. Kommt beim Einschalten gar keine Frage, gibt es keinen Weg über die SD-Karte. Probier bitte nichts auf eigene Faust, damit wird es eher schlimmer."],
    source: DEBRICK,
    next: "ask",
  },

  // How it ends.
  works: {
    mood: "happy",
    say: ["Super, sie läuft wieder! Jetzt ist Korgs Original-Firmware drauf. BLECHTRIBE kannst du jederzeit wieder mit dem Firmware Patcher aufspielen."],
  },
  stuck: {
    mood: "sad",
    say: ["Mist. Dann komm ich hier allein nicht weiter. Probier bitte nichts auf eigene Faust."],
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
  say: [["Lade bei Korg das Firmware-Update für die ", d.name, " herunter: ", { link: d.link, text: "Korgs Download-Seite" }, ". Pack die ZIP-Datei aus, du brauchst daraus die Datei SYSTEM.VSB."]],
  choices: [{ label: "Hab ich", to }],
});
const card = path => ["Schalte die Electribe aus, nimm die SD-Karte raus und steck sie in deinen Rechner. Leg die SYSTEM.VSB genau hierhin, fehlende Ordner legst du einfach an:", { path }];

for (const [key, d] of Object.entries(DEVICES)) {
  FLOW[`download:starts:${key}`] = download(d, "which");
  FLOW[`download:update:${key}`] = download(d, `card:${key}`);
  FLOW[`card:${key}`] = { mood: "idle", say: card(d.path), choices: [{ label: "Liegt drauf", to: "update:prompt" }] };
}
FOLDERS.forEach((f, i) => {
  FLOW[`folder:${i}`] = {
    mood: "idle",
    say: card(f.path),
    choices: [{ label: "Liegt drauf", to: "update:menu" }],
  };
});
