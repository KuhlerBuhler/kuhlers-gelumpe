/**
 * "Neue Version verfügbar" in the desktop app. The app (src-tauri) tells the
 * page its version through window.__GELUMPE_APP; a browser has none and shows
 * nothing. The latest release comes from the public GitHub API. While the
 * repository is private that answers 404, which is quietly no news.
 */
import { NEWS } from "../../data/news.mjs";

const REPO = "KuhlerBuhler/kuhlers-gelumpe";
const SEEN = "gelumpe.newsSeen";
const EVERY_MS = 4 * 60 * 60 * 1000;

/** True when version `a` is newer than `b`; both "1.2.3", with or without a leading v. */
export function isNewer(a, b) {
  const n = v => String(v).replace(/^v/, "").split("-")[0].split(".").map(x => parseInt(x, 10) || 0);
  const [x, y] = [n(a), n(b)];
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  }
  return false;
}

/** The release page of a newer version, or null. Never throws. */
export async function newerRelease(current, fetchImpl = fetch) {
  try {
    const res = await fetchImpl(`https://api.github.com/repos/${REPO}/releases/latest`, { headers: { Accept: "application/vnd.github+json" } });
    if (!res.ok) return null;
    const release = await res.json();
    return typeof release?.tag_name === "string" && typeof release.html_url === "string" && isNewer(release.tag_name, current) ? release : null;
  } catch {
    return null;
  }
}

/** @param {HTMLAnchorElement} link the hidden entry at the top of the sidebar */
export function watchForUpdate(link, app = window.__GELUMPE_APP) {
  if (!app?.version) return;
  const check = async () => {
    const release = await newerRelease(app.version);
    if (!release) return;
    link.href = release.html_url;
    link.hidden = false;
  };
  check();
  setInterval(check, EVERY_MS);
}

/** The news of every version after `seen` up to `current`, oldest first; with nothing seen, the news of `current` alone. */
export function unseenNews(current, seen, news = NEWS) {
  return news.filter(n => !isNewer(n.version, current) && (seen ? isNewer(n.version, seen) : !isNewer(current, n.version)));
}

/** Once after an update with news, a one-line toast that stays and points to the changelogs; then the version counts as seen. Never throws. */
export function showNews(toast, app = globalThis.window?.__GELUMPE_APP, storage = globalThis.localStorage) {
  if (!app?.version) return;
  try {
    const fresh = unseenNews(app.version, storage.getItem(SEEN));
    storage.setItem(SEEN, app.version);
    if (!fresh.length) return;
    toast(`BLECHTRIBE ${fresh.at(-1).version.replace(/\.0$/, "")} ist da. Was neu ist, steht unter Changelogs.`, "info", { stay: true });
  } catch { /* no storage: no news, the app works as before */ }
}
