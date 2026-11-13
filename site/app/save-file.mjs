/**
 * Every download of the app goes through here, so each one says that it happened: the browser and the app window save
 * without a word, and a second click then looks like the first one hung.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { t } from "./i18n.mjs";

/**
 * @param {Uint8Array|string} bytes
 * @param {string} name file name the user gets
 * @param {{type?: string, note?: string}} [options] note: what to do with the file, appended to the toast
 */
export function saveFile(bytes, name, { type = "application/octet-stream", note = "" } = {}) {
  if (globalThis.__GELUMPE_MOBILE) return saveMobile(bytes, name, note);
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  toast((note ? t("save.doneNote", { name, note }) : t("save.done", { name })), "ok");
}

/**
 * The Android WebView drops a blob link: the app asks the system's save dialog for a place and writes the file there
 * (file_save in src-tauri/src/mobile.rs). Cancelling says nothing.
 */
async function saveMobile(bytes, name, note) {
  const body = typeof bytes === "string" ? new TextEncoder().encode(bytes) : bytes;
  try {
    const saved = await globalThis.__TAURI__.core.invoke("file_save", body, { headers: { "x-file-name": encodeURIComponent(name) } });
    if (saved) toast((note ? t("save.doneMobileNote", { name, note }) : t("save.doneMobile", { name })), "ok");
  } catch (e) {
    toast(t("save.failed", { name, error: e?.message ?? String(e) }), "error");
  }
}
