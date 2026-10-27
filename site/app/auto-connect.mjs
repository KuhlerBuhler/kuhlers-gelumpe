import { t } from "./i18n.mjs";

/**
 * Connects to the Electribe once the USB watch sees it, and again after a pull or a lost session. A failed series
 * says so three times at most, then waits until the device comes and goes again or someone clicks connect.
 * A manual disconnect holds it off the same way.
 *
 * `attempt` resolves "ok", "failed" or "skip" (nothing to do: a session runs, several devices, no ports).
 */
export function createAutoConnect({ usb, attempt, enabled = () => true, toast, diagnose, timers = globalThis, settle = 1500, retry = [3000, 6000] }) {
  let failures = 0;
  let stopped = false;
  let held = false;
  let timer = null;
  let running = false;
  const cancel = () => { timers.clearTimeout(timer); timer = null; };
  const schedule = ms => {
    cancel();
    if (held || stopped || !enabled()) return;
    timer = timers.setTimeout(run, ms);
  };
  const fresh = () => { failures = 0; stopped = false; };

  async function run() {
    timer = null;
    if (running || held || stopped || usb.state !== "present" || !enabled()) return;
    running = true;
    let result;
    try { result = await attempt(); } catch { result = "failed"; } finally { running = false; }
    if (result === "ok") { fresh(); return; }
    if (result !== "failed" || held) return;
    failures++;
    if (failures === 1) toast(t("device.auto.retry"), "info");
    else if (failures === 2) toast(t("device.auto.still"), "info");
    else toast(t("device.auto.gaveUp"), "error", { action: { label: t("device.auto.diagnose"), run: diagnose } });
    if (failures < 3) schedule(retry[failures - 1]);
    else stopped = true;
  }

  usb.subscribe(state => {
    if (state === "present") schedule(settle);
    else if (state === "absent") { cancel(); fresh(); held = false; }
    else if (state === "connected") { cancel(); fresh(); }
    else cancel();
  });

  return {
    /** The connect button: a new series, and a manual disconnect before it no longer holds. */
    manualConnect() { cancel(); fresh(); held = false; },
    /** The disconnect button: no automatic connect until the cable comes back or the button is clicked. */
    manualDisconnect() { cancel(); held = true; },
    get failures() { return failures; },
  };
}
