/**
 * Changelogs: the GitHub releases of the repository, newest first, laid out like
 * GitHub's releases page. A release newer than the last one opened here puts a "!"
 * on the tab. While the repository is private the API answers 404 and the page
 * says so with a link. Versions GitHub no longer has, or all of them when it cannot
 * be reached, come from the notes the app carries (data/release-notes.mjs).
 */
import { el } from "./fields.mjs";
import { stateText } from "./state.mjs";
import { toast } from "./toast.mjs";
import { t, tNodes, locale, language } from "./i18n.mjs";
import { isNewer } from "./update.mjs";
import { RELEASE_NOTES } from "../../data/release-notes.mjs";

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

/** The release notes: headings, lists (an indented item belongs to the one above) and paragraphs of GitHub's markdown, as DOM, never as HTML. */
export function notes(md) {
  const out = [];
  let list = null;
  let sub = null;
  let para = [];
  const flush = () => { if (para.length) out.push(el("p", {}, inline(para.join(" ")))); para = []; };
  for (const raw of String(md ?? "").split(/\r?\n/)) {
    const line = raw.trim();
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    const li = line.match(/^[-*]\s+(.*)$/);
    if (!line) { flush(); list = null; sub = null; continue; }
    if (h) { flush(); list = null; sub = null; out.push(el(h[1].length <= 2 ? "h3" : "h4", {}, inline(h[2]))); continue; }
    if (li) {
      flush();
      const parent = list?.lastElementChild;
      if (/^\s{2,}/.test(raw) && parent) {
        if (!sub) { sub = el("ul"); parent.append(sub); }
        sub.append(el("li", {}, inline(li[1])));
        continue;
      }
      sub = null;
      if (!list) { list = el("ul"); out.push(list); }
      list.append(el("li", {}, inline(li[1])));
      continue;
    }
    list = null;
    sub = null;
    para.push(line);
  }
  flush();
  return out;
}

const date = iso => new Date(iso).toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" });

/** The system the page runs on, as GitHub's release files name it: "mac", "windows" or "linux"; null when it is none of them. */
export function systemOf(nav = globalThis.navigator) {
  const name = `${nav?.userAgentData?.platform ?? ""} ${nav?.platform ?? ""} ${nav?.userAgent ?? ""}`;
  if (/mac/i.test(name)) return "mac";
  if (/win/i.test(name)) return "windows";
  if (/linux|x11/i.test(name) && !/android/i.test(name)) return "linux";
  return null;
}

// A browser on a Mac says "Intel" on both kinds of Mac, so the Mac gets both files to choose from.
const APP_FILES = {
  mac: [[/_aarch64\.dmg$/i, "changelog.app.macArm"], [/_x64\.dmg$/i, "changelog.app.macIntel"]],
  windows: [[/(setup\.exe|\.msi)$/i, "changelog.app.windows"]],
  linux: [[/\.AppImage$/i, "changelog.app.linux"]],
};

/** The downloads of a release: the app for this system (both on a Mac) and BLECH.patch; the rest stays on GitHub. */
export function downloads(assets = [], system = systemOf()) {
  const apps = (APP_FILES[system] ?? []).map(([file, label]) => [assets.find(a => file.test(a.name)), label]).filter(([a]) => a);
  const patch = assets.find(a => a.name === "BLECH.patch");
  return [
    ...apps.map(([a, label]) => ({ href: a.browser_download_url, label: t(label) })),
    patch ? { href: patch.browser_download_url, label: t("changelog.patch") } : null,
  ].filter(Boolean);
}

// The blocks tools/release-lib.mjs (downloadBlock) puts above the notes of each language: links, install hints, the patch.
const DOWNLOAD_BLOCK = [/^\*\*(Herunterladen|Download)\b/, /^- \*\*(Windows|Mac|Linux)\b/, /^(Auf dem Mac nach|On the Mac, after)\b/,
  /^(Die vielen Dateien|You do not need the many files)\b/, /^\*\*(Ohne App patchen|Patch without the app)\*\*/];

/** A release body without the download blocks at the top of each language, for the release the person already has. */
export function withoutDownloads(body) {
  return String(body ?? "").replace(/\r\n/g, "\n").split(/^(## English[ \t]*)$/m).map(part => {
    const blocks = part.split(/\n[ \t]*\n/);
    let at = 0;
    while (at < blocks.length && (!blocks[at].trim() || DOWNLOAD_BLOCK.some(re => re.test(blocks[at].trim())))) at++;
    return at ? `\n${blocks.slice(at).join("\n\n")}` : part;
  }).join("");
}

/**
 * True for the release the desktop app runs, and for the newest release when it is newer: the update button in the
 * navbar brings that one. Neither needs its downloads here. A browser has no installed version and keeps them all.
 */
export function hasIt(tag, latest, installed = globalThis.window?.__GELUMPE_APP?.version) {
  if (!installed) return false;
  const same = !isNewer(tag, installed) && !isNewer(installed, tag);
  return same || (tag === latest && isNewer(latest, installed));
}

function release(r, latest) {
  // The version is the heading and the way to the release on GitHub; the date stands beside it.
  const side = el("header", { className: "cee-release-side" }, [
    el("h2", {}, [el("a", { className: "cee-text-link", href: r.html_url, target: "_blank", rel: "noopener noreferrer", textContent: r.tag_name })]),
    el("time", { dateTime: r.published_at, textContent: date(r.published_at) }),
    r.prerelease ? stateText("warn", t("changelog.prerelease")) : null,
  ]);
  const own = hasIt(r.tag_name, latest);
  const get = own ? [] : downloads(r.assets);
  const body = releaseBody(r);
  return el("article", { className: "cee-release" }, [
    side,
    el("div", { className: "cee-release-body" }, [
      r.name && r.name !== r.tag_name ? el("h3", { textContent: r.name }) : null,
      ...notes(own ? withoutDownloads(body) : body),
      get.length ? el("div", { className: "actions cee-release-get" }, get.map(d => el("a", { className: "btn", href: d.href, textContent: d.label }))) : null,
    ]),
  ]);
}

/** Prefer a carried French translation even when the release was fetched from GitHub. */
export function releaseBody(r, carriedNotes = RELEASE_NOTES) {
  const version = r.tag_name.replace(/^v/, "");
  return language() === "fr" ? carriedNotes.find(n => n.version === version)?.fr ?? r.body : r.body;
}

/** A version from the notes the app carries, with English and German as fallbacks. */
function carried(n) {
  const body = n[language()] ?? n.en ?? n.de;
  return el("article", { className: "cee-release" }, [
    el("header", { className: "cee-release-side" }, [el("h2", { textContent: `v${n.version}` })]),
    el("div", { className: "cee-release-body" }, notes(body)),
  ]);
}

/** GitHub's releases and, for the versions it does not have, the carried notes; newest first. */
export function entries(releases = [], carriedNotes = RELEASE_NOTES) {
  const tags = new Set(releases.map(r => r.tag_name.replace(/^v/, "")));
  const all = [...releases.map(r => ({ version: r.tag_name, r })), ...carriedNotes.filter(n => !tags.has(n.version)).map(n => ({ version: n.version, n }))];
  return all.sort((a, b) => (isNewer(a.version, b.version) ? -1 : isNewer(b.version, a.version) ? 1 : 0));
}

const show = latest => e => (e.r ? release(e.r, latest) : carried(e.n));

/**
 * @param {HTMLElement} root the page
 * @param {HTMLElement} tab the nav entry that gets the "!"
 * @returns {{ opened(): void }}
 */
export function changelogPage(root, tab, fetchImpl = globalThis.fetch) {
  const list = el("div", { className: "cee-releases", "aria-live": "polite" }, [el("p", { className: "muted", textContent: t("changelog.loading") })]);
  root.append(el("h1", { className: "ui-sr-only", textContent: t("nav.changelog") }), list);
  let latest = null;
  const badge = el("span", { className: "cee-nav-badge", textContent: "!", title: t("changelog.new") });
  badge.setAttribute("aria-label", t("changelog.new"));
  const mark = () => {
    if (latest && latest !== read()) tab.append(badge);
    else badge.remove();
  };
  // The list loads at the start; that it could not is said once the page is opened, not on every start.
  let offline = false;
  (async () => {
    let releases = null;
    try {
      const res = await fetchImpl(`https://api.github.com/repos/${REPO}/releases?per_page=30`, { headers: { Accept: "application/vnd.github+json" } });
      if (res.ok) releases = (await res.json()).filter(r => !r.draft);
    } catch {}
    if (!releases?.length) {
      offline = true;
      list.replaceChildren(el("p", {}, tNodes("changelog.alsoOn", { github: el("a", { className: "cee-text-link", href: PAGE, target: "_blank", rel: "noopener noreferrer", textContent: "GitHub" }) })), ...entries().map(show(null)));
      return;
    }
    const top = releases.find(r => !r.prerelease) ?? releases[0];
    latest = top.tag_name;
    list.replaceChildren(...entries(releases).map(show(latest)));
    if (!root.closest("[hidden]")) keep(latest);
    mark();
  })();
  return { opened() { if (offline) toast(t("changelog.offline"), "info"); if (latest) keep(latest); mark(); } };
}
