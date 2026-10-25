/**
 * "Neue Version verfügbar" in the desktop app. The app (src-tauri) tells the
 * page its version through window.__GELUMPE_APP; a browser has none and shows
 * nothing. The latest release comes from the public GitHub API. While the
 * repository is private that answers 404, which is quietly no news. A click
 * downloads and installs it from inside the app (src-tauri/src/update.rs).
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

/**
 * Downloads and installs `release` through the desktop app's update_install command. `label` shows the progress;
 * any failure goes to the toast and the release page opens instead. Never throws.
 */
export async function installRelease(release, { core = globalThis.__TAURI__?.core, toast, label = () => {}, openPage }) {
  const idle = "Neue Version verfügbar";
  try {
    if (!core?.invoke || !core.Channel) throw new Error("Die App kann sich hier nicht selbst aktualisieren.");
    const events = new core.Channel();
    events.onmessage = e => {
      if (e.stage === "install") label("Installation startet …");
      else label(e.total ? `Lade … ${Math.floor(100 * e.received / e.total)} %` : "Lade …");
    };
    label("Lade …");
    const done = await core.invoke("update_install", { tag: release.tag_name, events });
    label(done.quits ? "Installation läuft, die App schließt sich" : "Installation geöffnet");
    toast(done.quits ? "Die App schließt sich und installiert die neue Version." : `Die neue Version liegt in Downloads: ${done.file}`, "ok");
    return true;
  } catch (reason) {
    label(idle);
    toast(`Die neue Version ließ sich nicht selbst laden: ${reason?.message ?? reason}. Die Release-Seite öffnet sich.`, "error");
    openPage(release.html_url);
    return false;
  }
}

/** @param {HTMLAnchorElement} link the hidden entry at the top of the sidebar */
export function watchForUpdate(link, app = window.__GELUMPE_APP, toast = () => {}) {
  if (!app?.version) return;
  const text = link.querySelector("span");
  let release = null;
  let busy = false;
  link.addEventListener("click", async e => {
    if (!release || !window.__TAURI__?.core) return;
    e.preventDefault();
    if (busy) return;
    busy = true;
    await installRelease(release, { toast, label: t => { text.textContent = t; }, openPage: url => { window.location.href = url; } });
    busy = false;
  });
  const check = async () => {
    const found = await newerRelease(app.version);
    if (!found) return;
    release = found;
    link.href = found.html_url;
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
