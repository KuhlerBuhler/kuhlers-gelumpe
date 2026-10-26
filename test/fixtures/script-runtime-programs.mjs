import { readFileSync } from "node:fs";
import { compile, formatError } from "../../src/script/compiler.mjs";
import { markProbed } from "../../src/script/blob.mjs";

const build = (name, source) => {
  const result = compile(source, { name });
  if (!result.ok) throw new Error(result.errors.map(formatError).join("\n"));
  return { blob: Buffer.from(markProbed(result.blob)).toString("hex"), symbols: result.info.symbols };
};

/** korg.seq: ready writes part 1, TAP changes two steps, and while it plays step 9 of the first pass after TAP writes step 2. */
export const SEQ_WRITE = `
  let written = 0;
  korg.onEvent("ready", () => {
    korg.seq.clearPart(0);
    for (let s = 0; s < 16; s += 2) { korg.seq.setStep(0, s, 60 + s, 100); korg.seq.setGate(0, s, 48); }
    korg.seq.setStep(0, 1, 40, 100);
    korg.seq.setStep(0, 1, -1, 100);
    written = 1;
  });
  korg.onEvent("buttonPress", (key) => {
    if (key == korg.key.TAP) { korg.seq.setStep(0, 5, 65, 90); korg.seq.setGate(0, 5, 48); korg.seq.setStep(0, 0, 60, 0); written = 2; }
  });
  korg.onEvent("step", (s) => {
    if (s == 8 && written == 2) { korg.seq.setStep(0, 1, 50, 90); korg.seq.setGate(0, 1, 48); written = 3; }
  });
`;

export function runtimePrograms() {
  return {
    input: build("input", `
      let readyCount = 0; let frameCount = 0;
      let pressCount = 0; let releaseCount = 0; let lastKey = 0;
      let encoderIndex = 0; let encoderDelta = 0;
      let knobIndex = 0; let knobValue = 0;
      let padIndex = 0; let padVelocity = 0; let padReleaseCount = 0;
      let touchX = 0; let touchY = 0; let touchFirst = 0; let touches = 0; let firsts = 0;
      korg.onEvent("ready", () => { readyCount += 1; });
      korg.onEvent("frame", () => { frameCount += 1; });
      korg.onEvent("buttonPress", (key) => { pressCount += 1; lastKey = key; });
      korg.onEvent("buttonRelease", (key) => { releaseCount += 1; lastKey = key; });
      korg.onEvent("encoder", (index, delta) => { encoderIndex = index; encoderDelta = delta; });
      korg.onEvent("knob", (index, value) => { knobIndex = index; knobValue = value; });
      korg.onEvent("pad", (index, down, velocity) => {
        padIndex = index;
        if (down) { padVelocity = velocity; } else { padReleaseCount += 1; }
      });
      korg.onEvent("touch", (x, y, first) => { touchX = x; touchY = y; touchFirst = first; touches += 1; firsts += first; });
    `),
    bitmaps: build("bitmaps", `
      const face = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C];
      const tall = [255, 1, 1, 1, 255, 128, 128, 128, 255, 15, 15, 15];
      let granted = 0;
      korg.onEvent("buttonPress", (key) => {
        if (key == korg.key.TAP) {
          granted = korg.display.take();
          korg.display.clear();
          korg.display.bitmap(face, 3, 3, 8);
          korg.display.bitmap(face, 20, 60, 8);
          korg.display.bitmap(face, 124, 10, 8);
          korg.display.bitmap(face, -4, 1, 8);
          korg.display.bitmap(tall, 40, -5, 4);
          korg.display.bitmap(tall, 60, 21, 4);
          korg.display.textNumber("BPM ", 120, 70, 40);
          korg.display.textNumber("n", -5, 100, 56);
        }
      });
    `),
    fault: build("fault", `
      let zero = 0; let value = 0;
      korg.onEvent("buttonPress", (key) => { value = key / zero; });
    `),
    healthy: build("healthy", `
      let count = 0; let frames = 0;
      korg.onEvent("buttonPress", (key) => { count += 1; });
      korg.onEvent("frame", () => { frames += 1; });
    `),
    loop: build("loop", `
      let count = 0;
      korg.onEvent("buttonPress", (key) => { while (1) { count += 1; } });
    `),
    startfault: build("startfault", `
      let zero = 0; let value = 1 / zero;
      korg.onEvent("frame", () => { value += 1; });
    `),
    klicker: build("klicker", readFileSync(new URL("./scripts/klicker.js", import.meta.url), "utf8")),
    menuadd: build("menuadd", `
      let speed = 0; let offset = 0; let after = 0; let again = -5;
      let id = korg.menu.add("Speed", 1, 10, 5);
      let id2 = korg.menu.add("Offset", -50, 50, -7);
      korg.onEvent("ready", () => { again = korg.menu.add("Speed", 1, 10, 3); });
      korg.onEvent("menu", (which, value) => { if (which == id) { speed = value; } else { offset = value; } after += 1; });
    `),
    menumany: build("menumany", Array.from({ length: 14 }, (_, i) => `let p${i} = korg.menu.add("page${i}", 0, 9, 0);`).join("\n")),
    menuback: build("menuback", `let id = korg.menu.add("x", 5, 1, 2);`),
    readhw: build("readhw", `
      let transport = 0; let tempo = 0; let pattern = 0; let part = 0; let step = 0; let mute = 9; let knob = 0; let ms = 0;
      korg.onEvent("frame", () => {
        transport = korg.read.transport(); tempo = korg.read.tempo(); pattern = korg.read.pattern(); part = korg.read.part();
        step = korg.read.step(0); mute = korg.read.mute(0); knob = korg.read.knob(3); ms = korg.millis();
      });
    `),
    actions: build("actions", `
      korg.onEvent("pad", (index, down, velocity) => {
        if (down == 1) {
          if (index == 0) korg.tempo(1200);
          if (index == 1) korg.pattern(5);
          if (index == 2) korg.part(3);
          if (index == 3) korg.mute(2, 0);
          if (index == 4) korg.play();
          if (index == 5) korg.stop();
        }
      });
    `),
    seqevents: build("seqevents", `
      let plays = 0; let stops = 0; let recs = 0; let steps = 0; let beats = 0; let lastStep = 0;
      let tempoSeen = 0; let patternSeen = -1; let partSeen = -1; let muteSeen = -1; let saves = 0;
      korg.onEvent("play", () => { plays += 1; });
      korg.onEvent("stop", () => { stops += 1; });
      korg.onEvent("rec", () => { recs += 1; });
      korg.onEvent("step", (s) => { steps += 1; lastStep = s; });
      korg.onEvent("beat", () => { beats += 1; });
      korg.onEvent("tempo", (t) => { tempoSeen = t; });
      korg.onEvent("patternChange", (i) => { patternSeen = i; });
      korg.onEvent("partChange", (p) => { partSeen = p; });
      korg.onEvent("mute", (p, m) => { muteSeen = p * 10 + m; });
      korg.onEvent("save", () => { saves += 1; });
    `),
    seqwrite: build("seqwrite", SEQ_WRITE),
    lights: build("lights", `
      korg.onEvent("pad", (index, down, velocity) => {
        if (down == 1) {
          if (index == 6) korg.backlight(1, 0, 0);
          if (index == 7) korg.ledHold(1);
          if (index == 8) korg.ledHold(0);
        }
      });
    `),
    drawer: build("drawer", `
      korg.onEvent("frame", () => { korg.display.clear(); korg.display.rect(0, 0, 128, 64); });
    `),
    transport: build("transport", `
      korg.app("Transport", "TOOLS");
      let plays = 0; let stops = 0; let recs = 0; let others = 0;
      korg.onEvent("open", () => { korg.display.rect(0, 0, 128, 64); });
      korg.onEvent("buttonPress", (key) => {
        if (key == korg.key.PLAY) plays += 1;
        else if (key == korg.key.STOP) stops += 1;
        else if (key == korg.key.REC) recs += 1;
        else others += 1;
      });
      korg.onEvent("frame", () => { korg.display.rect(0, 0, 128, 64); });
    `),
    appfault: build("appfault", `
      korg.app("Defekt", "GAMES");
      let z = 0;
      korg.onEvent("open", () => { korg.display.text("x", 0, 0); z = 1 / z; });
    `),
    trap: build("trap", `
      korg.app("Falle", "GAMES");
      let exits = 0; let closes = 0;
      korg.onEvent("open", () => { korg.display.rect(0, 0, 128, 64); });
      korg.onEvent("close", () => { closes += 1; });
      korg.onEvent("buttonPress", (key) => { if (key == korg.key.EXIT) exits += 1; });
      korg.onEvent("frame", () => { korg.display.rect(0, 0, 128, 64); });
    `),
    taker: build("taker", `
      let granted = 0; let closes = 0; let exits = 0;
      korg.onEvent("close", () => { closes += 1; });
      korg.onEvent("buttonPress", (key) => {
        if (key == korg.key.TAP) { granted = korg.display.take(); korg.display.text("mine", 0, 0); }
        if (key == korg.key.EXIT) exits += 1;
      });
    `),
    snake: build("snake", readFileSync(new URL("./scripts/snake.js", import.meta.url), "utf8")),
    klickerstore: build("klickerstore", readFileSync(new URL("./scripts/klicker-store.js", import.meta.url), "utf8")),
    led: build("led", `
      let value = 0; let frames = 0;
      korg.onEvent("ready", () => { korg.led(0, 0); });
      korg.onEvent("frame", () => { frames += 1; });
      korg.onEvent("buttonPress", (key) => {
        if (key == 24) {
          value = 255 - value;
          korg.led(0, value);
          korg.led(0, value);
        }
        if (key == 9) {
          let index = 0;
          while (index < 88) { korg.led(index, 17); index += 1; }
        }
      });
    `),
  };
}
