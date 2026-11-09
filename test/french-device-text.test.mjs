import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { loadLanguage, setLanguage, localize } from "../site/app/i18n.mjs";
import fr from "../site/app/i18n-fr-device.mjs";
import { FIELDS } from "../src/map/index.mjs";
import { converter } from "../src/map/convert.mjs";
import { GROUPS, PARAM_LABELS } from "../data/map/fx-labels.mjs";
import { GROUPS as UNIT_GROUPS, UNITS, PARAMS, paramLabel } from "../data/fx/labels.mjs";
import { FX_CATALOG, MOD_CATALOG } from "../data/fx/catalog.mjs";
import { describeScreen } from "../site/app/follow.mjs";

const DEVICE_NAMES = new Set(["Acid Drive", "Asobi", "Blend", "Chorus", "Drive", "Exciter", "Fader", "Flanger", "Gain", "Grain Shifter", "Lo-Fi (Decimator)", "Looper", "Mod Delay", "PD Thru", "Peak-Hold B1", "Phase", "Phaser", "Punch", "Scratch", "Tremolo", "Vinyl Break", "Wah", "One-Shot"]);

test("French covers legacy map labels and every field help, including expert fields", () => {
  const missing = [];
  for (const f of FIELDS.values()) {
    if (f.label.de !== f.label.en && !(f.label.de in fr) && !DEVICE_NAMES.has(f.label.de)) missing.push(`${f.id}: ${f.label.de}`);
    if (f.note && !(f.note in fr)) missing.push(`${f.id}: ${f.note}`);
  }
  for (const label of [...GROUPS.map(g => g.label), ...UNIT_GROUPS]) {
    if (!["EQ", "Modulation"].includes(label) && !(label in fr)) missing.push(label);
  }
  for (const p of [...FX_CATALOG, ...MOD_CATALOG]) assert.ok(fr[p.description], p.name);
  assert.deepEqual(missing, []);
});

test("German effect parameter and unit names cannot silently return to French pages", () => {
  // Device and DSP identifiers, and established effect names, are intentionally kept.
  const labels = [...Object.values(PARAM_LABELS).map(p => p.de), ...Object.values(PARAMS), ...Object.values(UNITS).flatMap(k => Object.values(k).flat())];
  assert.deepEqual([...new Set(labels)].filter(s => !(s in fr) && !DEVICE_NAMES.has(s)), []);
  const placeholders = s => [...s.matchAll(/\{\w+\}/g)].map(m => m[0]).sort();
  for (const [source, translated] of Object.entries(fr)) {
    assert.ok(translated.trim(), source);
    assert.deepEqual(placeholders(translated), placeholders(source), source);
  }
});

test("field choices, formatter output and screen reader descriptions follow French without changing raw values", async () => {
  const onOff = converter("onOff");
  const length = converter("patternLength");
  try {
    await loadLanguage("fr");
    assert.equal(localize(FIELDS.get("fx.name").label), "Nom");
    assert.equal(paramLabel("output_level"), "Niveau de sortie");
    assert.deepEqual(onOff.choices.map(o => o.label), ["Désactivé", "Activé"]);
    assert.deepEqual(length.choices.map(o => o.raw), [0, 1, 2, 3]);
    assert.equal(length.format(1), "2 mesures");
    assert.equal(length.toRaw(1), 1);
    assert.equal(length.format(255), "inconnu (255)");
    assert.equal(converter("glideMs").format(127), "environ 40 s");
    assert.equal(converter("oscPitchCents").format(24), "+6 demi-tons");
    assert.equal(describeScreen({ name: { de: "Hauptbildschirm", en: "Main screen" }, part: 0 }), "Écran principal · Partie 1");
    assert.equal(localize({ de: "Name", fr: "Un libellé explicite" }), "Un libellé explicite");
    assert.equal(localize("I_mkp2_comp"), "I_mkp2_comp");
    setLanguage("de");
    assert.deepEqual(onOff.choices.map(o => o.label), ["Aus", "An"]);
    assert.equal(length.format(1), "2 Takte");
  } finally { setLanguage("de"); }
});

test("app views do not force German metadata and the desktop build includes translated guides", () => {
  for (const file of ["fields", "fx", "follow"]) {
    const source = readFileSync(new URL(`../site/app/${file}.mjs`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /(?:label|name)\??\.de\b/, file);
  }
  const build = readFileSync(new URL("../tools/build-site.mjs", import.meta.url), "utf8");
  const pattern = new RegExp(build.match(/const SKIP_PATTERN = \/(.+)\/;/)[1]);
  for (const lang of ["", ".en", ".fr"]) assert.ok(!pattern.test(`docs/plugins${lang}.md`));
  assert.ok(pattern.test("docs/development.md"));
});
