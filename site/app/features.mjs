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
  { group: "features.group.play", id: "key-pads", title: "features.keyPads.title", where: BOTH, image: "img/features/key-pads.svg",
    text: "features.keyPads.text",
    how: "features.keyPads.how" },
  { group: "features.group.play", id: "filter-toggle", title: "features.filterToggle.title", where: BOTH, image: "img/features/filter-toggle.svg",
    text: "features.filterToggle.text",
    how: "features.filterToggle.how" },
  { group: "features.group.play", id: "dice", title: "features.dice.title", where: BOTH, image: "img/features/dice.svg",
    text: "features.dice.text",
    how: "features.dice.how" },
  { group: "features.group.play", id: "tap-motion", title: "features.tapMotion.title", where: BOTH, image: "img/features/tap-motion.svg",
    text: "features.tapMotion.text",
    how: "features.tapMotion.how" },
  { group: "features.group.play", id: "pattern-switch", title: "features.patternSwitch.title", where: BOTH, image: "img/features/pattern-switch.svg",
    text: "features.patternSwitch.text",
    how: "features.patternSwitch.how" },
  { group: "features.group.play", id: "preview", title: "features.preview.title", where: BOTH, image: "img/features/preview.svg",
    text: "features.preview.text",
    how: "features.preview.how" },
  { group: "features.group.play", id: "sync-group", title: "features.syncGroup.title", where: BOTH, image: "img/features/sync-group.svg",
    text: "features.syncGroup.text",
    how: "features.syncGroup.how" },
  { group: "features.group.play", id: "mfx2", title: "features.mfx2.title", where: BOTH, image: "img/features/mfx2.svg",
    text: "features.mfx2.text",
    how: "features.mfx2.how" },
  { group: "features.group.play", id: "exit-write", title: "features.exitWrite.title", where: BOTH, image: "img/features/exit-write.svg",
    text: "features.exitWrite.text",
    how: "features.exitWrite.how" },
  { group: "features.group.play", id: "last-pattern", title: "features.lastPattern.title", where: BOTH, image: "img/features/last-pattern.svg",
    text: "features.lastPattern.text",
    how: "features.lastPattern.how" },
  { group: "features.group.play", id: "init-pattern", title: "features.initPattern.title", where: BOTH, image: "img/features/init-pattern.svg",
    text: "features.initPattern.text",
    how: "features.initPattern.how" },
  { group: "features.group.play", id: "stereo-pad", title: "features.stereoPad.title", where: RED, image: "img/features/stereo-pad.svg",
    text: "features.stereoPad.text",
    how: "features.stereoPad.how" },
  { group: "features.group.play", id: "ht-osc", title: "features.htOsc.title", where: RED, image: "img/features/ht-osc.svg",
    text: "features.htOsc.text",
    how: "features.htOsc.how" },
  { group: "features.group.play", id: "beat-eighth", title: "features.beatEighth.title", where: BOTH, image: "img/features/beat-eighth.svg",
    text: "features.beatEighth.text",
    how: "features.beatEighth.how" },
  { group: "features.group.play", id: "touch-scale-zero", title: "features.touchScaleZero.title", where: BOTH, image: "img/features/touch-scale-zero.svg",
    text: "features.touchScaleZero.text",
    how: "features.touchScaleZero.how" },
  { group: "features.group.play", id: "exit-pad", title: "features.exitPad.title", where: BOTH, image: "img/features/exit-pad.svg",
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
  { group: "features.group.look", id: "theme", title: "features.theme.title", where: BOTH, image: "img/features/theme.svg",
    text: "features.theme.text",
    how: "features.theme.how" },
  { group: "features.group.look", id: "power-off", title: "features.powerOff.title", where: BOTH, image: "img/features/power-off.svg",
    text: "features.powerOff.text",
    how: "features.powerOff.how" },
  { group: "features.group.look", id: "poly-pink", title: "features.polyPink.title", where: BOTH, image: "img/features/poly-pink.svg",
    text: "features.polyPink.text",
    how: "features.polyPink.how" },

  { group: "features.group.plugins", id: "plugins", title: "features.plugins.title", where: BOTH, image: "img/features/menu.svg",
    text: "features.plugins.text",
    how: "features.plugins.how" },
  { group: "features.group.plugins", id: "presets", title: "features.presets.title", where: RED, image: "img/features/presets.svg",
    text: "features.presets.text",
    how: "features.presets.how" },
  { group: "features.group.plugins", id: "play-plugins", title: "features.playPlugins.title", where: BOTH, image: "img/features/play-plugins.svg",
    text: "features.playPlugins.text",
    how: "features.playPlugins.how" },
  { group: "features.group.plugins", id: "doom", title: "features.doom.title", where: RED, image: "img/features/doom.svg",
    text: "features.doom.text",
    how: "features.doom.how" },

  { group: "features.group.safe", id: "rescue-switch", title: "features.rescueSwitch.title", where: BOTH, image: "img/features/rescue-switch.svg",
    text: "features.rescueSwitch.text",
    how: "features.rescueSwitch.how" },
  { group: "features.group.safe", id: "sample-errors", title: "features.sampleErrors.title", where: RED, image: "img/features/sample-errors.svg",
    text: "features.sampleErrors.text",
    how: "features.sampleErrors.how" },
  { group: "features.group.safe", id: "migrate", title: "features.migrate.title", where: BOTH, image: "img/features/migrate.svg",
    text: "features.migrate.text",
    how: "features.migrate.how" },
  { group: "features.group.safe", id: "usb-update", title: "features.usbUpdate.title", where: BOTH, image: "img/features/usb-update.svg",
    text: "features.usbUpdate.text",
    how: "features.usbUpdate.how" },
  { group: "features.group.safe", id: "auto-save", title: "features.autoSave.title", where: BOTH, image: "img/features/auto-save.svg",
    text: "features.autoSave.text",
    how: "features.autoSave.how" },
  { group: "features.group.safe", id: "backup", title: "features.backup.title", where: BOTH, image: "img/features/backup.svg",
    text: "features.backup.text",
    how: "features.backup.how" },
  ...[
    // from docs/ideen.md: what is planned or still being worked out, so people know what comes
    ["sample-editor", "features.sampleEditor.title", "features.sampleEditor.text"],
    ["waveform", "features.waveform.title", "features.waveform.text"],
    ["ratchet", "features.ratchet.title", "features.ratchet.text"],
    ["param-locks", "features.paramLocks.title", "features.paramLocks.text"],
    ["blechy-chat", "features.blechyChat.title", "features.blechyChat.text"],
    ["usb-samples", "features.usbSamples.title", "features.usbSamples.text"],
    ["preset-edit", "features.presetEdit.title", "features.presetEdit.text"],
    ["mod-live", "features.modLive.title", "features.modLive.text"],
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
    ["time-stretch", "features.timeStretch.title", "features.timeStretch.text"],
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
    // coloured pixels (pad colours) keep their colour, the rest is the one bit of the display
    const out = canvas.getContext("2d");
    const shown = out.getImageData(0, 0, 128, 64);
    for (let i = 0; i < 128 * 64; i++) {
      const [r, g, b] = rgba.subarray(i * 4, i * 4 + 3);
      if (Math.max(r, g, b) - Math.min(r, g, b) > 60) shown.data.set([r, g, b, 255], i * 4);
    }
    out.putImageData(shown, 0, 0);
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
