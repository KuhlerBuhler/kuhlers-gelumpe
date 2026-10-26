/**
 * The page Features under Gerät: everything BLECHTRIBE adds, what it does and how to reach it on
 * the device, with a picture of the display where there is one. The facts
 * come from README.md ("Was kann was?") and docs/patcher.md; a new patch gets its entry here.
 */
import { el } from "./fields.mjs";
import { drawDisplay } from "./emulator.mjs";
import { e2Outline } from "./e2-art.mjs";
import { t } from "./i18n.mjs";

const BOTH = ["red", "blue"];
const RED = ["red"];
/** The last group: what is planned (docs/ideen.md), without a date. */
const SOON = "features.group.soon";
const DEVICE = { red: "device.red", blue: "device.blue" };
const SHORT = { red: "device.red.short", blue: "device.blue.short" };

/** One entry per function. `how` is what you press, `where` which Electribe has it, `image` a picture of the display. */
export const FEATURES = [
  { group: "features.group.play", id: "note-assist", title: "features.noteAssist.title", where: BOTH, image: "img/features/note-assist.svg",
    text: "features.noteAssist.text",
    how: "features.noteAssist.how" },
  { group: "features.group.play", id: "dice", title: "features.dice.title", where: BOTH, image: "img/features/dice.svg",
    text: "features.dice.text",
    how: "features.dice.how" },
  { group: "features.group.play", id: "tap-motion", title: "features.tapMotion.title", where: BOTH, image: "img/features/tap-motion.svg",
    text: "features.tapMotion.text",
    how: "features.tapMotion.how" },
  { group: "features.group.play", id: "pattern-switch", title: "features.patternSwitch.title", where: BOTH, image: "img/features/pattern-switch.svg",
    text: "features.patternSwitch.text",
    how: "features.patternSwitch.how" },
  { group: "features.group.play", id: "sync-group", title: "features.syncGroup.title", where: BOTH,
    text: "features.syncGroup.text",
    how: "features.syncGroup.how" },
  { group: "features.group.play", id: "mfx2", title: "features.mfx2.title", where: BOTH, image: "img/features/mfx2.svg",
    text: "features.mfx2.text",
    how: "features.mfx2.how" },
  { group: "features.group.play", id: "exit-write", title: "features.exitWrite.title", where: BOTH, image: "img/features/exit-write.svg",
    text: "features.exitWrite.text",
    how: "features.exitWrite.how" },
  { group: "features.group.play", id: "exit-pad", title: "features.exitPad.title", where: BOTH,
    text: "features.exitPad.text",
    how: "features.exitPad.how" },

  { group: "features.group.look", id: "splash", title: "features.splash.title", where: BOTH, image: "img/features/splash.png",
    text: "features.splash.text",
    how: "features.splash.how" },
  { group: "features.group.look", id: "loading", title: "features.loading.title", where: RED, image: "img/features/loading.png",
    text: "features.loading.text",
    how: "features.loading.how" },
  { group: "features.group.look", id: "colors", title: "features.colors.title", where: BOTH, image: "img/features/colors.svg",
    text: "features.colors.text",
    how: "features.colors.how" },
  { group: "features.group.look", id: "theme", title: "features.theme.title", where: BOTH,
    text: "features.theme.text",
    how: "features.theme.how" },
  { group: "features.group.look", id: "power-off", title: "features.powerOff.title", where: BOTH,
    text: "features.powerOff.text",
    how: "features.powerOff.how" },
  { group: "features.group.look", id: "poly-pink", title: "features.polyPink.title", where: BOTH,
    text: "features.polyPink.text",
    how: "features.polyPink.how" },

  { group: "features.group.plugins", id: "plugins", title: "features.plugins.title", where: BOTH, image: "img/features/menu.svg",
    text: "features.plugins.text",
    how: "features.plugins.how" },
  { group: "features.group.plugins", id: "presets", title: "features.presets.title", where: RED, image: "img/features/presets.svg",
    text: "features.presets.text",
    how: "features.presets.how" },
  { group: "features.group.plugins", id: "doom", title: "features.doom.title", where: RED, image: "img/features/doom.svg",
    text: "features.doom.text",
    how: "features.doom.how" },

  { group: "features.group.safe", id: "rescue-switch", title: "features.rescueSwitch.title", where: BOTH,
    text: "features.rescueSwitch.text",
    how: "features.rescueSwitch.how" },
  { group: "features.group.safe", id: "sample-errors", title: "features.sampleErrors.title", where: RED,
    text: "features.sampleErrors.text",
    how: "features.sampleErrors.how" },
  { group: "features.group.safe", id: "migrate", title: "features.migrate.title", where: RED,
    text: "features.migrate.text",
    how: "features.migrate.how" },
  { group: "features.group.safe", id: "usb-update", title: "features.usbUpdate.title", where: RED,
    text: "features.usbUpdate.text",
    how: "features.usbUpdate.how" },
  ...[
    // from docs/ideen.md: what is planned or still being worked out, so people know what comes
    ["usb-samples", "features.usbSamples.title", "features.usbSamples.text"],
    ["preset-edit", "features.presetEdit.title", "features.presetEdit.text"],
    ["fx-export", "features.fxExport.title", "features.fxExport.text"],
    ["mod-live", "features.modLive.title", "features.modLive.text"],
    ["mac-midi", "features.macMidi.title", "features.macMidi.text"],
    ["more-samples", "features.moreSamples.title", "features.moreSamples.text"],
    ["factory-samples", "features.factorySamples.title", "features.factorySamples.text"],
    ["modular-rack", "features.modularRack.title", "features.modularRack.text"],
    ["osc-drawer", "features.oscDrawer.title", "features.oscDrawer.text"],
    ["filters", "features.filters.title", "features.filters.text"],
    ["mfx-free", "features.mfxFree.title", "features.mfxFree.text"],
    ["gapless", "features.gapless.title", "features.gapless.text"],
    ["fast-load", "features.fastLoad.title", "features.fastLoad.text"],
    ["tap-free", "features.tapFree.title", "features.tapFree.text"],
    ["blechy-voice", "features.blechyVoice.title", "features.blechyVoice.text"],
    ["bugfixes", "features.bugfixes.title", "features.bugfixes.text"],
  ].map(([id, title, text]) => ({ group: SOON, id, title, text, where: [], image: "img/features/soon.svg", soon: true })),
];

/** A picture cut to the one bit per pixel of the display and drawn like the plugin pictures of the catalog. */
function drawFeature(canvas, src) {
  const picture = new Image();
  picture.onload = () => {
    const work = document.createElement("canvas");
    work.width = 128;
    work.height = 64;
    const ctx = work.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(picture, 0, 0, 128, 64);
    const rgba = ctx.getImageData(0, 0, 128, 64).data;
    const bytes = new Uint8Array(1024);
    for (let i = 0; i < 128 * 64; i++) {
      if (rgba[i * 4] + rgba[i * 4 + 1] + rgba[i * 4 + 2] > 3 * 127) bytes[(i >> 10) * 128 + (i & 127)] |= 1 << ((i >> 7) & 7);
    }
    drawDisplay(canvas, bytes);
  };
  picture.src = src;
}

const pictures = [];
/** A canvas for an entry's picture; drawn once the list is in the page, where the canvas has its colours. */
function pictureOf(f) {
  const canvas = el("canvas", { className: "cee-lcd cee-catalog-thumb", width: 128, height: 64 });
  canvas.setAttribute("aria-hidden", "true");
  pictures.push([canvas, f.image]);
  return canvas;
}

export function featuresPage(root) {
  const groups = [...new Set(FEATURES.map(f => f.group))];
  root.replaceChildren(
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("features.title") })]),
    el("p", { className: "muted", textContent: t("features.lead") }),
    ...groups.map(group => el("section", { className: "ui-section cee-feature-group" }, [
      el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t(group) })]),
      group === SOON ? el("p", { className: "muted", id: "cee-features-soon-lead", textContent: t("features.soonLead") }) : null,
      el("ul", { className: "cee-features" }, FEATURES.filter(f => f.group === group).map(f => el("li", { className: "cee-feature", id: `cee-feature-${f.id}` }, [
        f.image ? pictureOf(f) : null,
        el("h3", { textContent: t(f.title) }),
        el("p", { textContent: t(f.text) }),
        f.how ? el("p", { className: "cee-feature-how" }, [el("strong", { textContent: t("features.how") }), t(f.how)]) : null,
        f.where.length ? Object.assign(el("ul", { className: "cee-feature-where" }, f.where.map(device => {
          const art = e2Outline(t(DEVICE[device]));
          art.setAttribute("aria-hidden", "true");
          const chip = el("li", { className: "ui-chip ui-chip-sm", title: t(DEVICE[device]) }, [art, t(SHORT[device])]);
          chip.dataset.device = device;
          return chip;
        })), { ariaLabel: t("features.where") }) : null,
      ]))),
    ])),
  );
  for (const [canvas, src] of pictures.splice(0)) drawFeature(canvas, src);
}
