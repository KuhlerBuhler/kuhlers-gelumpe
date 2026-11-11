import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { PRESETS } from "../data/script/presets.mjs";
import { compile } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { PLUGIN_PICTURES } from "../data/script/plugin-pictures.mjs";

const DIR = new URL("../site/img/plugins/", import.meta.url);

/** The display a catalog card shows: the plugin after 40 frames, as renderThumb in site/app/scripts.mjs runs it. */
function shown(preset) {
  const result = compile(preset.source, { name: preset.id });
  assert.ok(result.ok, preset.id);
  const device = new SimDevice({ storage: { load: () => null, save: () => {} } });
  const loaded = device.load(result.blob);
  if (loaded.ok && device.apps.length) device.openApp(device.apps[0].id);
  device.run(40);
  return device.shown;
}

test("every catalog plugin that leaves the display alone has its own picture, and every picture belongs to one", () => {
  for (const preset of PRESETS) {
    if (shown(preset).some(b => b)) continue;
    assert.ok(existsSync(new URL(`${preset.id}.svg`, DIR)), `${preset.id}: no picture in site/img/plugins (node tools/plugin-art.mjs)`);
  }
  assert.deepEqual(readdirSync(DIR).map(f => f.replace(/\.svg$/, "")).sort(), [...PLUGIN_PICTURES], "the list the catalog looks up names every picture");
  const ids = new Set(PRESETS.map(p => p.id));
  for (const file of readdirSync(DIR)) assert.ok(ids.has(file.replace(/\.svg$/, "")), `${file} is no catalog plugin`);
});

test("the pictures are display pictures: 128 x 64 whole pixels, each one different", () => {
  const files = readdirSync(DIR);
  const texts = files.map(f => readFileSync(new URL(f, DIR), "utf8"));
  for (const [i, text] of texts.entries()) assert.match(text, /^<svg [^>]*viewBox="0 0 128 64" shape-rendering="crispEdges"><rect width="128" height="64"\/><path /, files[i]);
  assert.equal(new Set(texts).size, texts.length);
});
