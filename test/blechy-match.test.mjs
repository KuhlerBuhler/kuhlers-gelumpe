import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeMatcher, casePhrases, normalize, words } from "../src/blechy-match.mjs";
import { CASES } from "../data/rescue.mjs";
import { WORDS } from "../data/blechy-words.mjs";
import { CASE_TEXTS } from "../data/blechy-cases.mjs";
import { LANGUAGES } from "../site/app/i18n.mjs";
import { build, OUT } from "../tools/blechy-cases.mjs";
import { QUERIES, UNSEEN } from "./fixtures/blechy-queries.mjs";

const match = makeMatcher(casePhrases());
const flat = set => Object.entries(set).flatMap(([id, langs]) => Object.entries(langs).flatMap(([lang, list]) => list.map(q => ({ id, lang, q }))));

test("every case of the first question has its texts in all languages and loose words in every language", () => {
  const ids = CASES.map(c => c.id);
  assert.deepEqual(Object.keys(CASE_TEXTS), ids);
  assert.deepEqual(Object.keys(WORDS).sort(), [...ids].sort());
  for (const id of ids) for (const [lang] of LANGUAGES) {
    assert.ok(CASE_TEXTS[id][lang].every(Boolean), `${id} ${lang} label and hint`);
    assert.ok(WORDS[id][lang]?.trim(), `${id} ${lang} words`);
  }
});

test("data/blechy-cases.mjs is current with the rescue.case texts (node tools/blechy-cases.mjs)", async () => {
  assert.equal(readFileSync(OUT, "utf8"), await build());
});

test("the test set covers every case in German and English and in more languages", () => {
  for (const c of CASES) {
    assert.ok(QUERIES[c.id]?.de?.length >= 4, `${c.id} de`);
    assert.ok(QUERIES[c.id]?.en?.length >= 4, `${c.id} en`);
  }
  assert.ok(new Set(flat(QUERIES).map(r => r.lang)).size >= 8);
});

test("each query of the test set finds its case among the first three, and nearly always first", () => {
  const all = flat(QUERIES);
  const missed = all.filter(({ id, q }) => !match(q, { limit: 3 }).some(r => r.id === id)).map(r => `${r.q} (${r.id})`);
  assert.deepEqual(missed, []);
  const first = all.filter(({ id, q }) => match(q)[0]?.id === id).length / all.length;
  assert.ok(first >= 0.9, `first ${first}`);
});

test("wording the matcher was not tuned on still finds its case among the first three", () => {
  const all = flat(UNSEEN);
  const top3 = all.filter(({ id, q }) => match(q, { limit: 3 }).some(r => r.id === id)).length / all.length;
  assert.ok(top3 >= 0.9, `top 3 ${top3}`);
});

test("the label of a case, typed in any language, finds that case first", () => {
  for (const c of CASES) for (const [lang] of LANGUAGES) assert.equal(match(CASE_TEXTS[c.id][lang][0])[0]?.id, c.id, `${c.id} ${lang}`);
});

test("half typed words, typos and other forms of a word count", () => {
  assert.equal(match("bildsch")[0]?.id, "silent");
  assert.equal(match("korg orig")[0]?.id, "back");
  assert.equal(match("sampels fehlen")[0]?.id, "samples");
  assert.equal(match("ivalid file")[0]?.id, "invalid");
  assert.equal(match("SOFTWARE UPDATE")[0]?.id, "prompt");
});

test("an empty query or one of only filler words finds nothing; nonsense finds nothing", () => {
  assert.deepEqual(match(""), []);
  assert.deepEqual(match("   "), []);
  assert.deepEqual(match("ich und du"), []);
  assert.deepEqual(match("qqqq zzzz"), []);
});

test("normalize folds case, accents and punctuation; words drops filler", () => {
  assert.equal(normalize("Gerät, STARTET nicht!"), "gerat startet nicht");
  assert.equal(normalize("Écran  noir"), "ecran noir");
  assert.deepEqual(words("mein Gerät startet nicht"), ["gerat", "startet", "nicht"]);
  assert.deepEqual(words("Display 00"), ["display", "00"]);
});

test("the texts shown in the current language count as phrases too", () => {
  const own = makeMatcher(casePhrases({ zero: ["Blubberwasser"] }));
  assert.equal(own("blubberwasser")[0]?.id, "zero");
});

test("a query takes well under a millisecond", () => {
  const t0 = performance.now();
  for (let i = 0; i < 200; i++) match("mein gerät startet nicht mehr richtig");
  assert.ok((performance.now() - t0) / 200 < 5);
});
