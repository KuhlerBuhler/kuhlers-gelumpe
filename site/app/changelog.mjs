/**
 * Changelogs: the GitHub releases of the repository, newest first, laid out like
 * GitHub's releases page. A release newer than the last one opened here puts a "!"
 * on the tab. While the repository is private the API answers 404 and the page
 * says so with a link.
 */
import { el } from "./fields.mjs";

const REPO = "KuhlerBuhler/kuhlers-gelumpe";
const SEEN = "cee.changelog.seen";
const PAGE = `https://github.com/${REPO}/releases`;

const read = () => { try { return localStorage.getItem(SEEN); } catch { return null; } };
const keep = tag => { try { localStorage.setItem(SEEN, tag); } catch {} };

/** Inline text with [label](https://...) links and **bold**; everything else stays text. */
function inline(text) {
  const out = [];
  const re = /\[([^\]]+)\]\((https:\/\/[^)\s]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g;
  let at = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > at) out.push(text.slice(at, m.index));
    if (m[1]) out.push(el("a", { className: "cee-text-link", href: m[2], target: "_blank", rel: "noopener noreferrer", textContent: m[1] }));
    else if (m[3]) out.push(el("strong", { textContent: m[3] }));
    else out.push(el("code", { textContent: m[4] }));
    at = m.index + m[0].length;
  }
  if (at < text.length) out.push(text.slice(at));
  return out;
}

/** The release notes: headings, lists and paragraphs of GitHub's markdown, as DOM, never as HTML. */
export function notes(md) {
  const out = [];
  let list = null;
  let para = [];
  const flush = () => { if (para.length) out.push(el("p", {}, inline(para.join(" ")))); para = []; };
  for (const raw of String(md ?? "").split(/\r?\n/)) {
    const line = raw.trim();
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    const li = line.match(/^[-*]\s+(.*)$/);
    if (!line) { flush(); list = null; continue; }
    if (h) { flush(); list = null; out.push(el(h[1].length <= 2 ? "h3" : "h4", {}, inline(h[2]))); continue; }
    if (li) {
      flush();
      if (!list) { list = el("ul"); out.push(list); }
      list.append(el("li", {}, inline(li[1])));
      continue;
    }
    list = null;
    para.push(line);
  }
  flush();
  return out;
}

const date = iso => new Date(iso).toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });

function release(r, latest) {
  const head = el("header", { className: "cee-release-head" }, [
    el("h2", {}, [el("a", { className: "cee-text-link", href: r.html_url, target: "_blank", rel: "noopener noreferrer", textContent: r.name || r.tag_name })]),
    latest ? el("span", { className: "cee-status", textContent: "Aktuell" }) : null,
    r.prerelease ? el("span", { className: "cee-status", textContent: "Vorabversion" }) : null,
  ]);
  head.querySelectorAll(".cee-status").forEach(s => { s.dataset.tone = s.textContent === "Aktuell" ? "ok" : "warn"; });
  const side = el("div", { className: "cee-release-side" }, [
    el("time", { dateTime: r.published_at, textContent: date(r.published_at) }),
    r.name && r.name !== r.tag_name ? el("code", { textContent: r.tag_name }) : null,
  ]);
  const assets = (r.assets ?? []).map(a => el("li", {}, [el("a", { className: "cee-text-link", href: a.browser_download_url, textContent: a.name })]));
  return el("article", { className: "cee-release" }, [
    side,
    el("div", { className: "cee-release-body" }, [
      head,
      ...notes(r.body),
      assets.length ? el("details", { className: "ui-details" }, [el("summary", { textContent: `Dateien (${assets.length})` }), el("ul", { className: "ui-details-body" }, assets)]) : null,
    ]),
  ]);
}

/**
 * @param {HTMLElement} root the page
 * @param {HTMLElement} tab the nav entry that gets the "!"
 * @returns {{ opened(): void }}
 */
export function changelogPage(root, tab, fetchImpl = globalThis.fetch) {
  const list = el("div", { className: "cee-releases", "aria-live": "polite" }, [el("p", { className: "muted", textContent: "Lade Releases..." })]);
  root.append(el("h1", { className: "ui-sr-only", textContent: "Changelogs" }), list);
  let latest = null;
  const badge = el("span", { className: "cee-nav-badge", textContent: "!", title: "Neues Release" });
  badge.setAttribute("aria-label", "Neues Release");
  const mark = () => {
    if (latest && latest !== read()) tab.append(badge);
    else badge.remove();
  };
  (async () => {
    let releases = null;
    try {
      const res = await fetchImpl(`https://api.github.com/repos/${REPO}/releases?per_page=30`, { headers: { Accept: "application/vnd.github+json" } });
      if (res.ok) releases = (await res.json()).filter(r => !r.draft);
    } catch {}
    if (!releases?.length) {
      list.replaceChildren(el("p", {}, ["Die Releases sind gerade nicht erreichbar. Sie stehen auch auf ", el("a", { className: "cee-text-link", href: PAGE, target: "_blank", rel: "noopener noreferrer", textContent: "GitHub" }), "."]));
      return;
    }
    const top = releases.find(r => !r.prerelease) ?? releases[0];
    latest = top.tag_name;
    list.replaceChildren(...releases.map(r => release(r, r === top)));
    if (!root.closest("[hidden]")) keep(latest);
    mark();
  })();
  return { opened() { if (latest) keep(latest); mark(); } };
}
