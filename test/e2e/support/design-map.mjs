/**
 * Where the rules of DESIGN.md live in the page: which selector carries which spacing level and
 * which component. design.e2e.mjs measures every page against it. A token name refers to
 * DESIGN.md's frontmatter (spacing.<name>, components.<name>).
 */
import { readFileSync } from "node:fs";

/** Containers whose gap is a level. Mobile is 720px and narrower, as in site/design/root.min.css. */
export const LEVELS = [
  { selector: ".cee-main.ui-page", gap: "page", mobile: "page-mobile" },
  { selector: ".cee-home", gap: "page", mobile: "page-mobile" },
  { selector: ".ui-section, .cee-sec, .cee-patch-panel", gap: "section", mobile: "section-mobile" },
  { selector: ".ui-field", gap: "block", mobile: "block" },
  { selector: ".cee-cards", gap: "card-grid", mobile: "card-grid" },
  { selector: ".ui-page-actions, .cee-patch-nav", gap: "row", mobile: "row" },
];

/** DESIGN.md components.<name> and the selector of its root. */
export const COMPONENTS = {
  "section-title": ".ui-section-title",
  card: ".cee-card",
  // A device card reserves room for its popout icon on the right (DESIGN.md, rule 6).
  "entry-card": ".cee-entry-step:not(.cee-device-card)",
  note: ".cee-note",
};

export const MOBILE = 720;

/** The frontmatter of DESIGN.md as nested objects; enough YAML for that file, nothing more. */
export function designTokens(path = new URL("../../../DESIGN.md", import.meta.url)) {
  const [, front] = readFileSync(path, "utf8").split(/^---$/m);
  const root = {};
  const stack = [{ indent: -1, node: root }];
  for (const raw of front.split("\n")) {
    if (!raw.trim() || raw.trim().startsWith("#")) continue;
    const indent = raw.length - raw.trimStart().length;
    const m = raw.trim().match(/^"?([^":]+)"?:\s*(.*)$/);
    if (!m) continue;
    while (stack.at(-1).indent >= indent) stack.pop();
    const parent = stack.at(-1).node;
    const value = m[2].replace(/^"(.*)"$/, "$1");
    if (value === "") {
      parent[m[1]] = {};
      stack.push({ indent, node: parent[m[1]] });
    } else parent[m[1]] = value;
  }
  return root;
}

/** "{spacing.card-padding}" to "16px"; a literal stays as it is. */
export function resolve(tokens, value) {
  const m = String(value).match(/^\{([\w.-]+)\}$/);
  if (!m) return value;
  return m[1].split(".").reduce((node, key) => node?.[key], tokens);
}

/** Elements a class may sit on: a class on the wrong tag looks right and is not reachable by keyboard. */
export const ELEMENTS = [
  { selector: ".btn", tags: ["button", "a", "label"] },
  { selector: ".cee-entry-step", tags: ["a", "button"] },
  { selector: ".ui-section-title", tags: ["h2"] },
];

/** Nesting and order of the components, checked with support/structure.mjs on every page they appear on. */
export const STRUCTURES = [
  {
    id: "card-grid",
    root: ".cee-cards",
    tree: { tag: "ul", classes: ["cee-cards"], children: [{ tag: "li", classes: ["cee-card"], repeatable: true, children: [{ tag: "h3", classes: [] }, { tag: "p", classes: [] }] }] },
  },
  {
    id: "entry-steps",
    root: ".cee-entry-steps",
    tree: { tag: "ul", classes: ["cee-entry-steps"], children: [{ tag: "li", classes: [], repeatable: true, children: [{ classes: ["cee-entry-step"] }] }] },
  },
  {
    id: "section-head",
    root: ".ui-section-head",
    tree: { tag: "div", classes: ["ui-section-head"], children: [{ tag: "h2", classes: ["ui-section-title"] }] },
  },
  {
    // Zurück first, then the rest (DESIGN.md, rule 5).
    id: "flow-nav",
    root: ".cee-patch-nav",
    tree: { tag: "div", classes: ["cee-patch-nav"], children: [{ tag: "button", id: "cee-patch-back", classes: [] }, { tag: "button", classes: [], repeatable: true }] },
  },
];
