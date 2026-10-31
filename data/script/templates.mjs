/**
 * The starting text of "Neues Plugin": one short, runnable plugin for each kind. The name the
 * user chose becomes the name of the app, so the menu on the device shows what the list shows.
 * test/script-templates.test.mjs compiles and probes every kind.
 */
import { text, TextError } from "../../src/text.mjs";
import { SCRIPT_APPS } from "./contract.mjs";

const games = name => `// App in GAMES: steht im Menü BLECH unter GAMES, ENTER öffnet sie, EXIT schließt sie.
// Ein Block läuft über den Platz, TAP in der Mitte gibt einen Punkt.
korg.app("${name}", "GAMES");
let x = 0;
let dir = 4;
let score = 0;

function draw() {
  korg.display.clear();
  korg.display.number(score, 0, 0);
  korg.display.rect(x, 40, 8, 8);
}

// open: die App wurde geöffnet, ab jetzt gehört ihr das Display.
korg.onEvent("open", () => {
  x = 0;
  score = 0;
  draw();
});

// buttonPress: key vergleicht man mit einem Namen aus korg.key, die Liste steht unter dem Editor.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP && x > 52 && x < 68) {
    score += 1;
    korg.led.TAP = 255;
  }
});

// frame: 25 Mal je Sekunde, solange die App offen ist.
korg.onEvent("frame", () => {
  x += dir;
  if (x <= 0 || x >= 120) dir = -dir;
  draw();
});
`;

const tools = name => `// App in TOOLS: steht im Menü BLECH unter TOOLS, ENTER öffnet sie, EXIT schließt sie.
// Zählt die Sekunden seit dem Öffnen und wie oft TAP gedrückt wurde.
korg.app("${name}", "TOOLS");
let opened = 0;
let seconds = 0;
let taps = 0;

function show() {
  korg.display.clear();
  korg.display.text("Seconds", 0, 0);
  korg.display.number(seconds, 0, 12);
  korg.display.text("TAP", 0, 28);
  korg.display.number(taps, 0, 40);
}

// open: die App wurde geöffnet, ab jetzt gehört ihr das Display.
korg.onEvent("open", () => {
  opened = korg.millis();
  seconds = 0;
  show();
});

// buttonPress: key vergleicht man mit einem Namen aus korg.key, die Liste steht unter dem Editor.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) {
    taps += 1;
    korg.led.TAP = taps & 1 ? 255 : 0;
    show();
  }
});

// frame: 25 Mal je Sekunde, solange die App offen ist. Neu zeichnen nur, wenn eine Sekunde dazukam.
korg.onEvent("frame", () => {
  const now = (korg.millis() - opened) / 1000;
  if (now != seconds) {
    seconds = now;
    show();
  }
});
`;

const background = () => `// Hintergrund: läuft ab dem Start, hat kein Display und steht nicht im Menü BLECH.
// Nach dem ersten TAP blinkt die TAP-LED einmal je Sekunde.
let pressed = 0;
let phase = 0;

// ready: kommt einmal, im ersten Rahmen nach dem Start.
korg.onEvent("ready", () => {
  korg.led.TAP = 0;
});

// buttonPress: key vergleicht man mit einem Namen aus korg.key, die Liste steht unter dem Editor.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) pressed = 1;
});

// frame: 25 Mal je Sekunde.
korg.onEvent("frame", () => {
  phase = (phase + 1) % 25;
  korg.led.TAP = pressed && phase < 12 ? 255 : 0;
});
`;

export const TEMPLATES = Object.freeze([
  Object.freeze({ id: "games", label: text("templates.games.label"), description: text("templates.games.description"), app: true, group: SCRIPT_APPS.groups[0], source: games }),
  Object.freeze({ id: "tools", label: text("templates.tools.label"), description: text("templates.tools.description"), app: true, group: SCRIPT_APPS.groups[1], source: tools }),
  Object.freeze({ id: "background", label: text("templates.background.label"), description: text("templates.background.description"), app: false, group: null, source: background }),
]);

/** The starting text for kind `id` and a plugin called `name` (the name only matters for apps). */
export function templateSource(id, name) {
  const kind = TEMPLATES.find(t => t.id === id);
  if (!kind) throw new TextError("templates.unknown", { id });
  return kind.source(name);
}
