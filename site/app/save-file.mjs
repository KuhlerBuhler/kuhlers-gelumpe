/**
 * Every download of the app goes through here, so each one says that it happened: the browser and the app window save
 * without a word, and a second click then looks like the first one hung.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";

/**
 * @param {Uint8Array|string} bytes
 * @param {string} name file name the user gets
 * @param {{type?: string, note?: string}} [options] note: what to do with the file, appended to the toast
 */
export function saveFile(bytes, name, { type = "application/octet-stream", note = "" } = {}) {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  toast(`„${name}“ gespeichert, im Ordner Downloads.${note ? ` ${note}` : ""}`, "ok");
}
