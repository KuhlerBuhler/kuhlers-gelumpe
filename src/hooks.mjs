/**
 * Hook registry: where each code patch hooks into the firmware, checked
 * across all patches that are applied together (docs/patcher.md, "Haken-Register").
 *
 * A patch may carry an optional `hooks` list next to `changes` (patch format
 * stays version 1, a patch without it is not registered):
 *
 *   { site: "0xC00700D8", kind: "instruction", chain: "key-dispatch",
 *     position: "before", swallow: true, note: "..." }
 *
 * `site` is the RAM address of the changed word, `kind` what it is (call
 * replaced, vtable slot, literal, instruction), `chain` the named call chain
 * from data/hooks.mjs it intercepts (one name or a list), `position` where the
 * hook runs relative to the original (before, after, replace) and `swallow`
 * whether it can keep the event from reaching the original and the stages
 * behind it.
 *
 * Refused: two hooks on one site, two hooks on one stage of a chain when one
 * replaces, hooks on a site or chain the table does not know, and the pairs
 * in INCOMPATIBLE when their declared exclusive sites overlap. Reported as
 * a dependency, not refused: a hook that can
 * swallow sits upstream of another patch's hook on the same chain.
 */
import { CHAINS, INCOMPATIBLE } from "../data/hooks.mjs";
import { SAMPLER_OF_SYNTH } from "../data/synth-sites.mjs";

export const HOOK_KINDS = ["call", "vtable-slot", "literal", "instruction"];
export const HOOK_POSITIONS = ["before", "after", "replace"];
const RAM_FROM = 0xC0000000;
const RAM_TO = 0xC0200000;

const hex = n => `0x${n.toString(16).toUpperCase()}`;

function parseHook(id, raw, index, synth = false) {
  const at = `${id}: Haken ${index + 1}`;
  if (!raw || typeof raw !== "object") return { error: `${at}: keine Beschreibung` };
  const site = typeof raw.site === "string" && /^0x[0-9a-f]{8}$/i.test(raw.site) ? parseInt(raw.site, 16) : NaN;
  if (!(site >= RAM_FROM && site < RAM_TO)) return { error: `${at}: site ist eine Adresse im Abbild wie "0xC00700D8"` };
  if (!HOOK_KINDS.includes(raw.kind)) return { error: `${at} (${hex(site)}): kind ist einer von ${HOOK_KINDS.join(", ")}` };
  if (!HOOK_POSITIONS.includes(raw.position)) return { error: `${at} (${hex(site)}): position ist einer von ${HOOK_POSITIONS.join(", ")}` };
  if (typeof raw.swallow !== "boolean") return { error: `${at} (${hex(site)}): swallow ist true oder false` };
  const names = Array.isArray(raw.chain) ? raw.chain : [raw.chain];
  if (!names.length || names.some(n => typeof n !== "string")) return { error: `${at} (${hex(site)}): chain nennt eine Kette` };
  const chains = [];
  for (const name of names) {
    const stages = CHAINS[name];
    if (!stages) return { error: `${at} (${hex(site)}): die Kette "${name}" ist nicht bekannt (data/hooks.mjs)` };
    // the chains name the Sampler's places; a synth patch's site is looked up by the Sampler place it corresponds to
    const place = synth ? SAMPLER_OF_SYNTH.get(site) ?? site : site;
    const stage = stages.findIndex(s => s.sites.includes(place) || s.sites.includes(site));
    if (stage < 0) return { error: `${at} (${hex(site)}): die Stelle gehört nicht zur Kette "${name}" (data/hooks.mjs)` };
    chains.push({ chain: name, stage, stageId: stages[stage].id });
  }
  return { hook: { patch: id, site, kind: raw.kind, position: raw.position, swallow: raw.swallow, chains } };
}

/**
 * The hooks of all patches against each other.
 * @returns {{ok: boolean, reasons: string[], dependencies: string[], hooks: object[]}}
 */
export function checkHooks(patches) {
  const reasons = [];
  const dependencies = [];
  const hooks = [];
  const seen = new Set();
  const ids = [];
  for (const patch of patches) {
    if (!patch || typeof patch !== "object" || patch.hooks === undefined) continue;
    const id = patch.id ?? "?";
    if (!Array.isArray(patch.hooks)) { reasons.push(`${id}: hooks ist eine Liste`); continue; }
    ids.push(id);
    patch.hooks.forEach((raw, i) => {
      const parsed = parseHook(id, raw, i, Array.isArray(patch.builds) && patch.builds.includes("synth"));
      if (parsed.error) { reasons.push(parsed.error); return; }
      const { hook } = parsed;
      if (hooks.some(h => h.patch === id && h.site === hook.site)) {
        reasons.push(`${id}: Einhängestelle ${hex(hook.site)} ist doppelt beschrieben`);
        return;
      }
      hooks.push(hook);
    });
  }

  const conflicts = INCOMPATIBLE.filter(({ patches: [x, y], sharedSites }) =>
    ids.includes(x) && ids.includes(y) && (!sharedSites || sharedSites.some(site =>
      hooks.some(h => h.patch === x && h.site === site) && hooks.some(h => h.patch === y && h.site === site))));
  const incompatible = (a, b) => conflicts.some(({ patches: [x, y] }) => (a === x && b === y) || (a === y && b === x));
  for (const { patches: [x, y], reason } of conflicts) {
    reasons.push(`${x} und ${y} passen nicht zusammen: ${reason}`);
  }

  const say = (key, list, text) => {
    if (seen.has(key)) return;
    seen.add(key);
    list.push(text);
  };
  for (const [i, a] of hooks.entries()) {
    for (const b of hooks.slice(i + 1)) {
      if (a.patch === b.patch || incompatible(a.patch, b.patch)) continue;
      if (a.site === b.site) {
        say(`site:${a.patch}:${b.patch}:${a.site}`, reasons,
          `${b.patch}: Einhängestelle ${hex(b.site)} ist schon von ${a.patch} besetzt.`);
      }
      for (const ca of a.chains) {
        const cb = b.chains.find(c => c.chain === ca.chain);
        if (!cb) continue;
        if (ca.stage === cb.stage && a.site !== b.site && (a.position === "replace" || b.position === "replace")) {
          const who = a.position === "replace" ? a : b;
          say(`stage:${a.patch}:${b.patch}:${ca.chain}:${ca.stage}`, reasons,
            `${b.patch}: Haken an ${hex(b.site)} und ${a.patch}: Haken an ${hex(a.site)} liegen in der Kette "${ca.chain}" an derselben Stelle (${ca.stageId}), und ${who.patch} ersetzt dort.`);
        }
        for (const [up, down, cu, cd] of [[a, b, ca, cb], [b, a, cb, ca]]) {
          if (up.swallow && cu.stage < cd.stage) {
            say(`dep:${up.patch}:${up.site}:${down.patch}:${down.site}:${ca.chain}`, dependencies,
              `${down.patch}: Der Haken an ${hex(down.site)} (Kette "${ca.chain}") liegt hinter dem Haken von ${up.patch} an ${hex(up.site)}, der Ereignisse verschlucken kann. Was ${up.patch} verschluckt, erreicht ${down.patch} nicht.`);
          }
        }
      }
    }
  }
  return { ok: reasons.length === 0, reasons, dependencies, hooks };
}
