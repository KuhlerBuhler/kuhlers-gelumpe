import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { LEVELS, COMPONENTS, ELEMENTS, STRUCTURES, MOBILE, designTokens, resolve } from "./support/design-map.mjs";
import { matchComponentTree, serializeSubtree } from "./support/structure.mjs";
import { makeFirmware, makeRecord } from "../helpers.mjs";

// Every page against DESIGN.md: the gap of each spacing level, no margins that add to a gap,
// nothing in the flow overlapping, no horizontal scroll, and each component as the frontmatter
// describes it, the same on every page. At 1280, 860 and 390px.
const VIEWPORTS = [{ width: 1280, height: 900 }, { width: 860, height: 900 }, { width: 390, height: 844 }];

/** How a person reaches each page; the scripts entry has five pages of its own. */
const PAGES = [
  ["start", page => page.click("#cee-tab-start")],
  ["emu", page => page.click("#cee-tab-emu")],
  ["device", page => go(page, "device")],
  ["console", page => page.click("#cee-tab-console")],
  ["features", page => page.click("#cee-tab-features")],
  ["rescue", page => page.click("#cee-tab-rescue")],
  ["patcher", page => page.click("#cee-tab-patcher")],
  ["splash", page => page.click("#cee-tab-splash")],
  ["fx", async page => { await page.click("#cee-tab-fx"); await page.locator("#cee-fx-slot").waitFor({ timeout: 15_000 }); }],
  ["mod", page => page.click("#cee-tab-mod")],
  ["ptools", page => page.click("#cee-tab-ptools")],
  ["samples", page => page.click("#cee-tab-samples")],
  ["scripts catalog", async page => { await page.click("#cee-tab-scripts"); await page.click("#cee-scripts-page-catalog"); }],
  ["scripts editor", page => page.click("#cee-scripts-page-editor")],
  ["scripts run", page => page.click("#cee-scripts-page-run")],
  ["scripts docs", page => page.click("#cee-scripts-page-docs")],
  ["changelog", page => page.click("#cee-tab-changelog")],
  ["settings", page => page.click("#cee-settings-button")],
];

let h;
let fake;
let firmware;
const tokens = designTokens();
before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: h.dir });
  const gate = makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64, 64] } });
  gate.setDevice("mfx", 0x27);
  firmware = await makeFirmware([{ kind: "ifx", slot: 50, record: gate }]);
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

/** The page with the emulator running, so Presets and Modulationen are open, and ?labs for the hidden pages. */
async function open() {
  for (const context of h.browser.contexts()) await context.close();
  const page = await h.page();
  await page.setViewportSize(VIEWPORTS[0]);
  await page.goto(`${h.url}?labs#emu=${fake.port}:${TOKEN}`);
  await page.locator("#cee-e2-power").waitFor();
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-e2-power");
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  return page;
}

/** What the page breaks of DESIGN.md at its current width, one line per finding. Runs in the page. */
function measure({ levels, components, mobile }) {
  const found = [];
  const wide = window.innerWidth > mobile;
  const scope = document.querySelector(".cee-main");
  const name = el => {
    const id = el.id ? `#${el.id}` : "";
    const cls = [...el.classList].slice(0, 2).map(c => `.${c}`).join("");
    return `${el.tagName.toLowerCase()}${id}${cls}`;
  };
  const shown = el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "contents";
  };

  const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (overflow > 1) found.push(`scrolls sideways by ${overflow}px`);

  // Levels: the gap, a column, and children that add no margin of their own (rules 1 and 2).
  for (const { selector, px, column } of levels) {
    for (const el of [...scope.querySelectorAll(selector)].filter(shown)) {
      const cs = getComputedStyle(el);
      const gap = cs.rowGap === "normal" ? "0px" : cs.rowGap;
      const along = column ? gap : (cs.columnGap === "normal" ? "0px" : cs.columnGap);
      if (along !== px) found.push(`${name(el)}: gap ${along}, level says ${px}`);
      if (!column) continue;
      for (const child of [...el.children].filter(shown)) {
        const c = getComputedStyle(child);
        if (c.position === "absolute" || c.position === "fixed") continue;
        if (parseFloat(c.marginTop) || parseFloat(c.marginBottom)) {
          found.push(`${name(el)} > ${name(child)}: margin ${c.marginTop} / ${c.marginBottom} on top of the gap`);
        }
      }
    }
  }

  // Rule 6: siblings in the flow never cover each other.
  const flow = el => {
    const cs = getComputedStyle(el);
    return shown(el) && !["absolute", "fixed", "sticky"].includes(cs.position) && cs.display !== "inline" && !el.closest("svg, canvas");
  };
  let overlaps = 0;
  for (const parent of scope.querySelectorAll("*")) {
    if (overlaps >= 15 || !flow(parent)) continue;
    const kids = [...parent.children].filter(flow);
    for (let i = 0; i < kids.length; i++) {
      const a = kids[i].getBoundingClientRect();
      for (let j = i + 1; j < kids.length; j++) {
        const b = kids[j].getBoundingClientRect();
        const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const hgt = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (w > 1 && hgt > 1) {
          overlaps++;
          found.push(`${name(parent)}: ${name(kids[i])} and ${name(kids[j])} overlap by ${Math.round(w)}x${Math.round(hgt)}px`);
        }
      }
    }
  }

  // Inline styles carry no raw colours.
  for (const el of scope.querySelectorAll("[style]")) {
    const style = el.getAttribute("style").replace(/--[\w-]+\s*:[^;]*;?/g, "");
    if (/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i.test(style)) found.push(`${name(el)}: inline colour in style="${style.trim().slice(0, 60)}"`);
  }

  // Components: the computed style of each shown instance, for the frontmatter and the cross-page check.
  const seen = {};
  for (const [component, { selector }] of Object.entries(components)) {
    const el = [...scope.querySelectorAll(selector)].find(shown);
    if (!el) continue;
    const cs = getComputedStyle(el);
    seen[component] = {
      element: name(el),
      padding: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(" "),
      borderRadius: cs.borderTopLeftRadius,
      backgroundColor: cs.backgroundColor,
      color: cs.color,
      fontSize: cs.fontSize,
      fontFamily: cs.fontFamily.split(",")[0].replace(/["']/g, "").trim(),
      fontWeight: cs.fontWeight,
    };
  }
  return { found, seen, wide };
}

/** Classes on the wrong element and components built out of their order. */
async function structure(page) {
  const out = [];
  for (const { selector, tags } of ELEMENTS) {
    const wrong = await page.$$eval(`.cee-main ${selector}`, (els, allowed) =>
      els.filter(el => el.getClientRects().length && !allowed.includes(el.tagName.toLowerCase())).map(el => `<${el.tagName.toLowerCase()} class="${el.className}">`), tags);
    for (const w of wrong.slice(0, 3)) out.push(`${selector} must be <${tags.join("|")}>, is ${w}`);
  }
  for (const { id, root, tree } of STRUCTURES) {
    const trees = await page.$$eval(`.cee-main ${root}`, (els, source) => {
      const serialize = new Function(`return (${source})`)();
      return els.filter(el => el.getClientRects().length).slice(0, 5).map(el => serialize(el, 6));
    }, serializeSubtree.toString());
    for (const subtree of trees) {
      const result = matchComponentTree(subtree, tree, id);
      if (!result.ok) out.push(result.reason);
    }
  }
  return out;
}

/** [r, g, b, a] of "#rrggbbaa" or "rgba(…)". */
function rgba(value) {
  const hex = String(value).match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/i);
  if (hex) return [0, 2, 4].map(i => parseInt(hex[1].slice(i, i + 2), 16)).concat(hex[2] ? parseInt(hex[2], 16) / 255 : 1);
  const m = String(value).match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
  return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
}
const sameColor = (a, b) => {
  const [x, y] = [rgba(a), rgba(b)];
  return !!x && !!y && x.slice(0, 3).every((v, i) => Math.abs(v - y[i]) <= 1) && Math.abs(x[3] - y[3]) < 0.01;
};
/** "12px 16px" to the four sides as computed. */
const sides = value => {
  const p = String(value).split(/\s+/);
  const [t, r = t, b = t, l = r] = p;
  return [t, r, b, l].join(" ");
};

/** Findings of a component against its frontmatter entry. */
function againstSpec(component, style, wide) {
  const spec = tokens.components[component];
  const out = [];
  if (spec.padding && style.padding !== sides(resolve(tokens, spec.padding))) out.push(`padding ${style.padding}, DESIGN.md says ${sides(resolve(tokens, spec.padding))}`);
  if (spec.rounded && style.borderRadius !== resolve(tokens, spec.rounded)) out.push(`radius ${style.borderRadius}, DESIGN.md says ${resolve(tokens, spec.rounded)}`);
  if (spec.backgroundColor && !sameColor(style.backgroundColor, resolve(tokens, spec.backgroundColor))) out.push(`background ${style.backgroundColor}, DESIGN.md says ${resolve(tokens, spec.backgroundColor)}`);
  if (spec.textColor && !sameColor(style.color, resolve(tokens, spec.textColor))) out.push(`colour ${style.color}, DESIGN.md says ${resolve(tokens, spec.textColor)}`);
  if (spec.typography) {
    const key = spec.typography.replace(/^\{typography\.|\}$/g, "");
    const type = (!wide && tokens.typography[`${key}-mobile`]) || tokens.typography[key];
    if (style.fontSize !== type.fontSize) out.push(`font size ${style.fontSize}, DESIGN.md says ${type.fontSize}`);
    if (style.fontFamily !== type.fontFamily) out.push(`font ${style.fontFamily}, DESIGN.md says ${type.fontFamily}`);
    if (style.fontWeight !== String(type.fontWeight)) out.push(`weight ${style.fontWeight}, DESIGN.md says ${type.fontWeight}`);
  }
  return out.map(f => `${component} (${style.element}): ${f}`);
}

test("every page keeps DESIGN.md: spacing levels, no overlap, components as specified and alike on every page", async () => {
  const page = await open();
  const findings = [];
  const looks = {};
  for (const [id, show] of PAGES) {
    await page.setViewportSize(VIEWPORTS[0]);
    await show(page);
    for (const f of await structure(page)) findings.push(`${id}: ${f}`);
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize(viewport);
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      const wide = viewport.width > MOBILE;
      const levels = LEVELS.map(({ selector, gap, mobile }) => ({
        selector,
        px: tokens.spacing[wide ? gap : mobile],
        column: !selector.includes("actions") && !selector.includes("nav") && !selector.includes("cards"),
      }));
      const components = Object.fromEntries(Object.entries(COMPONENTS).map(([k, selector]) => [k, { selector }]));
      const result = await page.evaluate(measure, { levels, components, mobile: MOBILE });
      const where = `${id} @${viewport.width}`;
      for (const f of result.found) findings.push(`${where}: ${f}`);
      for (const [component, style] of Object.entries(result.seen)) {
        for (const f of againstSpec(component, style, result.wide)) findings.push(`${where}: ${f}`);
        const key = `${component}@${wide ? "wide" : "narrow"}`;
        const first = looks[key] ??= { where, style };
        for (const prop of ["padding", "borderRadius", "backgroundColor", "fontSize", "fontFamily"]) {
          if (style[prop] !== first.style[prop]) findings.push(`${where}: ${component} ${prop} ${style[prop]}, on ${first.where} ${first.style[prop]}`);
        }
      }
    }
  }
  const unique = [...new Set(findings)];
  assert.deepEqual(unique, [], `${unique.length} findings against DESIGN.md:\n${unique.join("\n")}`);
  assert.deepEqual(page.errors, []);
});
