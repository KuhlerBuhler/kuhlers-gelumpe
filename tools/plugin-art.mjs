#!/usr/bin/env node
// Draws the pictures of the plugin catalog for the plugins that leave the display alone (they light LEDs or work in
// the background). Same drawing as the Features pictures (tools/feature-art.mjs). Writes the SVGs and the list of
// ids the catalog looks up (data/script/plugin-pictures.mjs).
//   node tools/plugin-art.mjs
import { writeFileSync, mkdirSync } from "node:fs";
import { picture, svg, arrow } from "./feature-art.mjs";

const OUT = new URL("../site/img/plugins/", import.meta.url);
const LIST = new URL("../data/script/plugin-pictures.mjs", import.meta.url);
const RED = "#ff4b4b";

/** One pad of the 2 x 8 grid, as on the Features pictures. */
const padAt = i => [6 + (i % 8) * 15, i < 8 ? 26 : 42];
/** A pad that is half lit: every second pixel. */
const dim = (p, x, y, w, h, colour, every = 2) => {
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) if ((i + j) % every === 0) p.fill(x + i, y + j, 1, 1, colour);
};

const PLUGIN_ART = {
  // the tempo glides over the length of the pattern to the tempo of the next one in the chain
  bpmglide: p => {
    p.text("BPM GLIDE", 4, 3);
    p.text("CHAIN", 124, 3, { align: "right" });
    p.text("120", 4, 16, { s: 2 });
    arrow(p, 52, 22);
    p.text("140", 124, 16, { s: 2, align: "right" });
    for (let x = 0; x < 120; x++) p.fill(4 + x, 58 - Math.round((x / 119) * 18), 1, 2);
    p.fill(4, 38, 1, 22);
    p.fill(123, 38, 1, 22);
  },
  // a light runs over the pads, the pads it left glow on
  lauflicht: p => {
    p.text("LAUFLICHT", 4, 6, { s: 2 });
    for (let i = 0; i < 16; i++) {
      const [x, y] = padAt(i);
      if (i === 5) p.fill(x, y, 12, 12, RED);
      else if (i === 4) dim(p, x, y, 12, 12, RED);
      else if (i === 3) dim(p, x, y, 12, 12, RED, 4);
      else p.frame(x, y, 12, 12);
    }
  },
  // all red pads get brighter and darker together
  pulsieren: p => {
    p.text("PULSIEREN", 4, 3);
    for (let x = 0; x < 52; x++) p.fill(72 + x, 10 + Math.round(-5 * Math.sin((x / 26) * Math.PI)), 1, 2);
    for (let i = 0; i < 16; i++) {
      const [x, y] = padAt(i);
      dim(p, x, y, 12, 12, RED);
      p.frame(x, y, 12, 12, 1);
    }
  },
  // PLAY-Takt: the PLAY LED blinks on every quarter note while the pattern plays
  playtakt: p => {
    p.text("PLAY LED", 4, 3);
    p.frame(8, 20, 36, 26, 2);
    for (let i = 0; i < 9; i++) p.fill(21 + i, 24 + i, 1, 18 - 2 * i);
    for (const [x, y, w, h] of [[2, 32, 4, 2], [46, 32, 4, 2], [25, 14, 2, 4], [25, 48, 2, 4], [4, 16, 3, 2], [45, 16, 3, 2], [4, 48, 3, 2], [45, 48, 3, 2]]) p.fill(x, y, w, h);
    [1, 2, 3, 4].forEach((n, k) => {
      const x = 58 + k * 17;
      if (k === 0) p.fill(x, 20, 13, 13); else p.frame(x, 20, 13, 13);
      p.text(String(n), x + 7, 37, { align: "center" });
    });
    p.text("ON THE BEAT", 92, 52, { align: "center" });
  },
  // only while PART MUTE is held, a pad mutes its part or brings it back; the pads show the mutes
  momentmute: p => {
    p.fill(4, 3, 62, 11);
    p.text("PART MUTE", 35, 5, { align: "center", colour: null });
    p.text("HOLD", 124, 5, { align: "right" });
    const muted = new Set([2, 5, 9, 14]);
    for (let i = 0; i < 16; i++) {
      const [x, y] = padAt(i);
      if (muted.has(i)) { p.frame(x, y, 12, 12); for (let k = 0; k < 8; k++) { p.fill(x + 2 + k, y + 2 + k, 1, 1); p.fill(x + 9 - k, y + 2 + k, 1, 1); } }
      else p.fill(x, y, 12, 12, RED);
    }
  },
  // in Gate Arp the note stays where the finger came down, X picks the rhythm
  gatehold: p => {
    p.text("GATE ARP", 4, 3);
    p.text("HOLD", 124, 3, { align: "right" });
    p.frame(4, 14, 56, 46, 2);
    for (let y = -4; y <= 4; y++) { const w = Math.round(Math.sqrt(16 - y * y)); p.fill(22 - w, 40 + y, 2 * w + 1, 1); }
    p.fill(22, 16, 1, 18);
    p.fill(6, 40, 10, 1);
    p.fill(28, 40, 30, 1);
    for (let i = 0; i < 4; i++) { p.fill(54 - i, 37 + i, 1, 7 - 2 * i); }
    [1, 0, 1, 1, 0, 1, 1, 0].forEach((on, k) => {
      const x = 68 + k * 7;
      if (on) p.fill(x, 24, 5, 14); else p.fill(x, 36, 5, 2);
    });
    p.text("RHYTHM 3", 124, 50, { align: "right" });
  },
  // copies the steps of one bar to another bar of the pattern
  stepcopy: p => {
    p.text("STEP COPY", 4, 3);
    const steps = [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0];
    for (const [bx, label] of [[4, "BAR 1"], [74, "BAR 3"]]) {
      p.frame(bx, 16, 50, 24, 2);
      steps.forEach((on, k) => {
        const x = bx + 5 + (k % 8) * 5, y = k < 8 ? 21 : 30;
        if (on) p.fill(x, y, 4, 6); else p.fill(x + 1, y + 5, 2, 1);
      });
      p.text(label, bx + 25, 48, { align: "center" });
    }
    arrow(p, 57, 27);
  },
  // a step above velocity 96 plays with its own EG INT, DECAY and LEVEL: a taller, longer envelope on the lit pads
  betteraccent: p => {
    p.text("ACCENT", 4, 3);
    p.text("VEL > 96", 124, 3, { align: "right" });
    [0, 1, 0, 0, 1, 0, 0, 1].forEach((accent, k) => {
      const x = 6 + k * 15, h = accent ? 24 : 10;
      for (let i = 0; i < 13; i++) p.fill(x + i, 38 - Math.round(h * Math.exp(-i / (accent ? 6 : 2.5))), 1, 2);
      if (accent) p.fill(x, 46, 12, 12, RED); else p.frame(x, 46, 12, 12);
    });
  },
  // a TIE step and the step after it get more glide: the two notes slide into each other
  easyslides: p => {
    p.text("SLIDE", 4, 3);
    p.text("TIE", 124, 3, { align: "right" });
    p.fill(6, 44, 30, 3);
    for (let i = 0; i < 40; i++) p.fill(36 + i, 44 - Math.round(24 * (1 - Math.cos((i / 39) * Math.PI)) / 2), 1, 3);
    p.fill(76, 20, 46, 3);
    p.frame(6, 52, 12, 10);
    p.fill(36, 52, 40, 10, RED);
    p.frame(90, 52, 12, 10);
  },
  // every pad press also goes out as a MIDI note on its own channel: pad 1 = note 36 up to pad 16 = note 51
  midiecho: p => {
    p.text("MIDI ECHO", 4, 3);
    p.text("CH 10", 124, 3, { align: "right" });
    for (let i = 0; i < 8; i++) {
      const [x] = padAt(i);
      if (i === 2) p.fill(x, 16, 12, 12, RED); else p.frame(x, 16, 12, 12);
    }
    arrow(p, 18, 34);
    p.text("NOTE 38", 40, 36);
    p.text("VEL 100", 40, 50);
  },
  // clears the motion sequence of the selected part: the recorded knob curve goes flat
  motionclear: p => {
    p.text("CLEAR MOTION", 4, 3);
    p.text("PART 3", 124, 3, { align: "right" });
    p.frame(4, 16, 54, 34, 2);
    for (let x = 0; x < 48; x++) p.fill(7 + x, 33 - Math.round(12 * Math.sin((x / 47) * 2 * Math.PI)), 1, 2);
    arrow(p, 62, 30);
    p.frame(74, 16, 50, 34, 2);
    p.fill(77, 33, 44, 2);
    p.text("MENU -> BLECH", 64, 54, { align: "center" });
  },
};

mkdirSync(OUT, { recursive: true });
for (const [name, draw] of Object.entries(PLUGIN_ART)) {
  const p = picture();
  draw(p);
  writeFileSync(new URL(`${name}.svg`, OUT), svg(p));
  console.log(`site/img/plugins/${name}.svg`);
}
const ids = Object.keys(PLUGIN_ART).sort();
writeFileSync(LIST, `// Written by tools/plugin-art.mjs: the catalog plugins with a picture in site/img/plugins/<id>.svg.\nexport const PLUGIN_PICTURES = Object.freeze(${JSON.stringify(ids)});\n`);
console.log("data/script/plugin-pictures.mjs");
