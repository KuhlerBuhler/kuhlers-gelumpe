/**
 * The Doom page: besides the two downloads for a card reader, a button that writes both files over USB straight onto the card of
 * the connected Electribe (src/usb-update.mjs, storeDoom), with its progress in the page and a button that stops it.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { t } from "./i18n.mjs";
import { storeDoom } from "../../src/usb-update.mjs";
import { DOOM_FILES } from "../../src/patcher.mjs";
import { number } from "../../src/text.mjs";

const mb = bytes => `${number(Number((bytes / 1048576).toFixed(1)), { useGrouping: false, minimumFractionDigits: 1, maximumFractionDigits: 1 })} MB`;

export function doomPage(root, { device = null } = {}) {
  const send = root.querySelector("#cee-doom-usb");
  const help = root.querySelector("#cee-doom-usb-help");
  const job = root.querySelector("#cee-doom-job");
  let busy = false;
  const session = () => (device?.session && !device.session.sender.disconnected ? device.session : null);

  function render() {
    send.disabled = busy || !session();
    help.hidden = busy || !!session();
  }

  function progress(stop) {
    job.hidden = false;
    const bar = el("div", { className: "ui-progress", role: "progressbar" }, [el("span", { className: "ui-progress-bar" })]);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    const meta = el("span", { className: "ui-job-meta" });
    const name = t("doom.usb.job");
    const cancel = el("div", { className: "ui-job-actions" }, el("button", { type: "button", className: "btn", id: "cee-doom-cancel", textContent: t("common.cancel"), onclick: () => stop.abort() }));
    job.replaceChildren(el("div", { className: "ui-job-head" }, [el("span", { className: "ui-job-name", textContent: name }), cancel]), bar, meta);
    return {
      step(phase, done, total) { window.ui?.setProgress(bar, total ? Math.round((done / total) * 100) : 0, name); meta.textContent = phase; },
      end() { job.hidden = true; job.replaceChildren(); },
    };
  }

  async function toDevice() {
    const s = session();
    if (!s || busy) return;
    busy = true;
    render();
    const stop = new AbortController();
    const release = s.reserve({ wait: true });
    const p = progress(stop);
    try {
      p.step(t("doom.usb.loading"), 0, 0);
      const [bin, wad] = await Promise.all(DOOM_FILES.map(async file => {
        const res = await fetch(file, { signal: stop.signal });
        if (!res.ok) throw new Error(t("doom.usb.fetchFailed", { file: file.split("/").pop(), error: res.status }));
        return new Uint8Array(await res.arrayBuffer());
      }));
      await storeDoom(s, { bin, wad }, (done, total) => p.step(t("doom.usb.step", { done: mb(done), total: mb(total) }), done, total), stop.signal);
      toast(t("doom.usb.done"), "ok", { stay: true });
    } catch (e) {
      if (stop.signal.aborted) toast(t("doom.usb.aborted"), "info", { stay: true });
      else toast(`${t("doom.usb.job")}: ${e.message}`, "error");
    } finally {
      release();
      p.end();
      busy = false;
      render();
    }
  }

  send.addEventListener("click", () => toDevice());
  render();
  return { sessionChanged: render };
}
