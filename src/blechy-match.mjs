/**
 * Finds the cases of Blechy's first question that fit what someone typed, in any of the app's languages. Each case has
 * phrases (its label and hint in every language, data/blechy-cases.mjs, and the loose words of data/blechy-words.mjs);
 * a typed word counts for a case when it is one of its words, the start of one (still typing), another form of it (a
 * shared stem) or close to it (a typo, by letter triples). Rare words weigh more than words many cases share.
 */
import { CASE_TEXTS } from "../data/blechy-cases.mjs";
import { WORDS } from "../data/blechy-words.mjs";

// Words that say nothing about a case. Negations are not here: "startet nicht" and "startet, aber" are different cases.
const STOP = new Set(`
der die das den dem des ein eine einer einem einen und oder aber ich du er sie es wir ihr mein meine meinen meiner dein
ist sind war bin hat habe hab wird wenn dann da dort hier mit von zu zum zur auf im in an am bei für was wie noch mal
schon nur auch so ja doch denn halt jetzt immer gerade beim
the a an and or but i you he she it we they my your is are was am be been has have had will when then there here with
of to on in at for what how just also so yes now still its it's this that me
le la les un une des et ou mais je tu il elle mon ma mes est sont de du au aux en dans sur pour avec que qui
el los las una y o pero yo mi mis es son del al en con por para que
il lo gli uno e ma io mio mia è sono di da nel con per che
de het een en of maar ik mijn is zijn van op in met voor dat
o os as um uma e ou mas eu meu minha é são do da no na com para que
i a ale ja mój moja jest są w z na do że się
a ale já můj moje je jsou v ve z na do že se
и а но я мой моя мои это он она в на с к по для что как у
і а але я мій моя мої це він вона в на з до для що як у
`.trim().split(/\s+/));

/** Lower case, no accents, letters and digits only, so "Gerät", "GERAT" and "gerat" are one word. */
export function normalize(text) {
  return String(text).toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replace(/ß/g, "ss").replace(/[’']/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

export const words = text => normalize(text).split(" ").filter(w => w && !STOP.has(w) && (w.length > 1 || /\d/.test(w)));

const bigrams = list => list.slice(1).map((w, i) => `${list[i]} ${w}`);

const triples = w => {
  const padded = ` ${w} `;
  const out = new Set();
  for (let i = 0; i + 3 <= padded.length; i++) out.add(padded.slice(i, i + 3));
  return out;
};

const dice = (a, b) => {
  let shared = 0;
  for (const x of a) if (b.has(x)) shared++;
  return (2 * shared) / (a.size + b.size);
};

/** How well the typed word `q` stands for the word `w`, 0 to 1. `last`: the word is still being typed. */
function likeness(q, w, qt, wt, last) {
  if (q === w) return 1;
  let common = 0;
  while (common < q.length && common < w.length && q[common] === w[common]) common++;
  const short = Math.min(q.length, w.length);
  // another form of the same word: "startet" and "starten", "samples" and "sample"
  if (common >= 4 && common >= short * 0.75) return 0.85;
  if (last && q.length >= 3 && common === q.length) return 0.7;
  if (q.length < 4 || w.length < 4) return 0;
  const d = dice(qt, wt);
  return d >= 0.5 ? d * 0.8 : 0;
}

/**
 * The matcher over `cases` ({ id: [phrase, ...] }). match(query) gives the fitting case ids, best first, with their score.
 */
export function makeMatcher(cases) {
  const vocab = Object.fromEntries(Object.entries(cases).map(([id, phrases]) => [id, new Set(phrases.flatMap(words))]));
  // two typed words in a row that stand in a row in a phrase: "no file" is one case, "no" alone is in several
  const pairs = Object.fromEntries(Object.entries(cases).map(([id, phrases]) => [id, new Set(phrases.flatMap(p => bigrams(words(p))))]));
  const ids = Object.keys(vocab);
  const df = new Map();
  for (const id of ids) for (const w of vocab[id]) df.set(w, (df.get(w) ?? 0) + 1);
  const weight = w => Math.log(1 + ids.length / df.get(w));
  const all = [...df.keys()].map(w => ({ w, t: triples(w), weight: weight(w) }));

  return function match(query, { limit = 5 } = {}) {
    const typed = words(query);
    if (!typed.length) return [];
    const endsTyping = !/\s$/.test(query);
    const scores = Object.fromEntries(ids.map(id => [id, 0]));
    typed.forEach((q, i) => {
      const qt = triples(q);
      const best = Object.fromEntries(ids.map(id => [id, 0]));
      for (const { w, t, weight: wgt } of all) {
        const like = likeness(q, w, qt, t, endsTyping && i === typed.length - 1);
        if (!like) continue;
        for (const id of ids) if (vocab[id].has(w)) best[id] = Math.max(best[id], like * wgt);
      }
      for (const id of ids) scores[id] += best[id];
    });
    bigrams(typed).forEach(pair => {
      for (const id of ids) if (pairs[id].has(pair)) scores[id] += 0.5;
    });
    const ranked = ids.map(id => ({ id, score: scores[id] / typed.length })).filter(r => r.score > 0).sort((a, b) => b.score - a.score);
    if (!ranked.length) return [];
    // the cases close to the best, not every case that shares one common word
    return ranked.filter(r => r.score >= ranked[0].score * 0.5).slice(0, limit);
  };
}

/** All phrases of the cases: labels and hints in every language, the loose words, and `extra` (the texts as shown now). */
export function casePhrases(extra = {}) {
  const ids = new Set([...Object.keys(CASE_TEXTS), ...Object.keys(WORDS)]);
  return Object.fromEntries([...ids].map(id => [id, [
    ...Object.values(CASE_TEXTS[id] ?? {}).flat(),
    ...Object.values(WORDS[id] ?? {}).flatMap(list => list.split(",")),
    ...(extra[id] ?? []),
  ].filter(Boolean)]));
}
