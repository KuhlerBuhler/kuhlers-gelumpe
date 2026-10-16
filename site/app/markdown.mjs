/**
 * A small Markdown reader for the docs the page shows (docs/plugins.md): headings, paragraphs, lists, tables, code blocks,
 * quotes, and code, bold, italic and links inside text. It builds DOM nodes, never HTML text, so a doc cannot inject markup.
 * Links to other docs have no place on the page and come out as their label; links to http(s) open in a new tab; links to
 * a heading of the same doc go to `onJump(id)`.
 */
import { el } from "./fields.mjs";

export const slug = text => text.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, "").trim().replace(/\s+/g, "-");

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)]+\))|(\*[^*\s][^*]*\*)/g;

function inline(text, onJump) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const [token] = m;
    if (m[1]) out.push(el("code", { textContent: token.slice(1, -1) }));
    else if (m[2]) out.push(el("strong", {}, inline(token.slice(2, -2), onJump)));
    else if (m[3]) {
      const [, label, href] = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (/^https?:/.test(href)) out.push(el("a", { className: "cee-text-link", href, target: "_blank", rel: "noopener noreferrer" }, inline(label, onJump)));
      else if (href.startsWith("#")) out.push(el("button", { type: "button", className: "cee-text-link cee-doc-jump", onclick: () => onJump(href.slice(1)) }, inline(label, onJump)));
      else out.push(...inline(label, onJump));
    } else out.push(el("em", {}, inline(token.slice(1, -1), onJump)));
    last = m.index + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Splits a table row at the bars that are not inside a code span. */
function cells(line) {
  const out = [];
  let cell = "";
  let code = false;
  for (const ch of line.trim().replace(/^\||\|$/g, "")) {
    if (ch === "`") code = !code;
    if (ch === "|" && !code) { out.push(cell.trim()); cell = ""; } else cell += ch;
  }
  out.push(cell.trim());
  return out;
}

const isTableStart = (line, next) => line.trim().startsWith("|") && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(next ?? "") && next.includes("-");
const LIST = /^(\s*)(?:[-*]|\d+\.)\s+/;

/**
 * @returns {{ blocks: {node: HTMLElement, heading?: {level: number, text: string, id: string}}[] }}
 */
export function parseMarkdown(source, { onJump = () => {} } = {}) {
  const lines = source.replace(/\r/g, "").split("\n");
  const blocks = [];
  const add = (node, heading) => blocks.push({ node, heading });
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const fence = /^```(\w*)/.exec(line);
    if (fence) {
      const body = [];
      for (i++; i < lines.length && !lines[i].startsWith("```"); i++) body.push(lines[i]);
      i++;
      add(el("pre", { className: "cee-doc-code" }, [el("code", { textContent: body.join("\n") })]));
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const text = heading[2].replace(/`/g, "");
      const level = heading[1].length;
      add(el(`h${Math.min(level + 1, 6)}`, { className: "cee-doc-heading", id: `doc-${slug(text)}` }, inline(heading[2], onJump)), { level, text, id: `doc-${slug(text)}` });
      i++;
      continue;
    }
    if (isTableStart(line, lines[i + 1])) {
      const head = cells(line);
      const rows = [];
      for (i += 2; i < lines.length && lines[i].trim().startsWith("|"); i++) rows.push(cells(lines[i]));
      add(el("div", { className: "cee-doc-table" }, [el("table", { className: "cee-names" }, [
        el("thead", {}, el("tr", {}, head.map(h => el("th", { scope: "col" }, inline(h, onJump))))),
        el("tbody", {}, rows.map(r => el("tr", {}, r.map(c => el("td", {}, inline(c, onJump)))))),
      ])]));
      continue;
    }
    if (LIST.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && lines[i].trim()) {
        if (LIST.test(lines[i])) items.push(lines[i].replace(LIST, "").trim());
        else items[items.length - 1] += ` ${lines[i].trim()}`;
        i++;
      }
      add(el(ordered ? "ol" : "ul", { className: "cee-doc-list" }, items.map(t => el("li", {}, inline(t, onJump)))));
      continue;
    }
    if (line.startsWith(">")) {
      const body = [];
      for (; i < lines.length && lines[i].startsWith(">"); i++) body.push(lines[i].replace(/^>\s?/, ""));
      add(el("blockquote", { className: "cee-doc-quote" }, inline(body.join(" "), onJump)));
      continue;
    }
    if (/^-{3,}$/.test(line.trim())) { i++; continue; }
    const body = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|>)/.test(lines[i]) && !LIST.test(lines[i]) && !isTableStart(lines[i], lines[i + 1])) body.push(lines[i++].trim());
    if (!body.length) body.push(lines[i++].trim());
    add(el("p", {}, inline(body.join(" "), onJump)));
  }
  return { blocks };
}
