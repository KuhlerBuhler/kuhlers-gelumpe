import { electribePorts } from "../../src/session.mjs";
import { t } from "./i18n.mjs";

/**
 * What the app sees of MIDI, for someone whose Electribe is "not found": every port by name, which pair counts as an
 * Electribe, and why the list may be empty. `collectMidi` asks, `midiReport` turns the answer into plain text for Discord.
 */

const ACCESS = {
  granted: "settings.midi.access.granted",
  denied: "settings.midi.access.denied",
  prompt: "settings.midi.access.prompt",
  unsupported: "settings.midi.access.unsupported",
  unknown: "settings.midi.access.unknown",
};
const USB = { present: "usb.present", connected: "usb.connected", absent: "usb.absent", unknown: "usb.unknown" };

const portInfo = port => ({
  name: String(port.name ?? ""),
  ...(port.manufacturer ? { manufacturer: String(port.manufacturer) } : {}),
  ...(port.state ? { state: String(port.state) } : {}),
  ...(port.connection ? { connection: String(port.connection) } : {}),
});

async function permission(permissions) {
  if (!permissions?.query) return "unknown";
  try { return (await permissions.query({ name: "midi", sysex: true })).state; } catch { return "unknown"; }
}

/**
 * Lists the ports. Web MIDI is only asked when the permission stands already or `ask` is set (a click), so opening
 * the settings never brings up the browser's question. Native MIDI lists every port of the system, not only the
 * Electribe ones the transport keeps.
 */
export async function collectMidi({ transport, permissions = null, ask = false, usb = "unknown", app = null, agent = "" }) {
  const report = { transport: transport.native ? "native" : "web", access: "unknown", error: null, inputs: [], outputs: [], pairs: [], usb, version: app?.version ?? null, agent };
  if (!transport.supported) { report.access = "unsupported"; return report; }
  if (!transport.native) {
    report.access = await permission(permissions);
    if (report.access !== "granted" && !ask) return report;
  }
  let access;
  try { access = await transport.requestAccess(); } catch (error) {
    report.access = error?.name === "NotAllowedError" || error?.name === "SecurityError" ? "denied" : "error";
    report.error = error?.message || String(error);
    if (transport.native && transport.listPorts) {
      try { const ports = await transport.listPorts(); report.inputs = ports.inputs.map(portInfo); report.outputs = ports.outputs.map(portInfo); } catch {}
    }
    return report;
  }
  report.access = "granted";
  const all = transport.native && transport.listPorts ? await transport.listPorts() : { inputs: [...access.inputs.values()], outputs: [...access.outputs.values()] };
  report.inputs = all.inputs.map(portInfo);
  report.outputs = all.outputs.map(portInfo);
  report.pairs = electribePorts(access).map(pair => ({ out: pair.out.name, in: pair.in.name }));
  return report;
}

const portLine = port => {
  const extra = [port.manufacturer, port.state, port.connection].filter(Boolean);
  return `  ${port.name || "?"}${extra.length ? ` [${extra.join(", ")}]` : ""}`;
};

/**
 * Korg's own USB-MIDI driver on Windows names the ports after the jacks ("electribe2 sampler 1 PAD/KNOB", with the
 * rename "Electribe 3 SOUND"), and the device's SysEx replies do not come through it (measured 2026-10-28, driver
 * 1.15.63). Windows' own driver names them "Electribe 3" and works.
 */
const JACK = / (PAD\/KNOB|SOUND)$/;
const jackNames = report => [...report.inputs, ...report.outputs].some(port => JACK.test(port.name));
export const korgDriver = report => /Windows/.test(report.agent) && jackNames(report);

/**
 * What the Rettung page says to "the app does not find my Electribe", from a report and the mode picked in the navbar
 * ("emu" or "device"); null when the report shows nothing to go by. The same port names on another system than Windows
 * are not measured yet, so they only lead to the report, not to a cause.
 */
export function midiVerdict(report, mode) {
  if (report.access === "unsupported" || report.access === "denied") return report.access;
  const ports = [...report.inputs, ...report.outputs];
  if (report.access !== "granted" && !ports.length) return null;
  if (jackNames(report)) return /Windows/.test(report.agent) ? "korgWindows" : "korgOther";
  if (!report.pairs.length) return ports.some(port => /electribe/i.test(port.name)) ? "unpaired" : "none";
  return mode === "device" ? "paired" : "emu";
}

/** The report as plain text, one fact per line. */
export function midiReport(report) {
  const none = `  ${t("settings.midi.none")}`;
  const access = report.access === "error" ? t("settings.midi.access.error", { error: report.error }) : t(ACCESS[report.access] ?? ACCESS.unknown);
  return [
    t("settings.midi.report"),
    ...(report.version ? [t("settings.version", { version: report.version })] : []),
    ...(report.agent ? [t("settings.midi.system", { agent: report.agent })] : []),
    t("settings.midi.transport", { transport: t(report.transport === "native" ? "settings.midi.transport.native" : "settings.midi.transport.web") }),
    t("settings.midi.access", { state: access }),
    ...(report.error && report.access !== "error" ? [t("settings.midi.error", { error: report.error })] : []),
    t("settings.midi.usb", { state: t(USB[report.usb] ?? USB.unknown) }),
    t("settings.midi.inputs", { count: report.inputs.length }),
    ...(report.inputs.length ? report.inputs.map(portLine) : [none]),
    t("settings.midi.outputs", { count: report.outputs.length }),
    ...(report.outputs.length ? report.outputs.map(portLine) : [none]),
    t("settings.midi.pairs", { count: report.pairs.length }),
    ...(report.pairs.length ? report.pairs.map(pair => `  ${t("settings.midi.pair", { out: pair.out, in: pair.in })}`) : [none]),
    ...(korgDriver(report) ? [t("settings.midi.korgDriver")] : []),
  ].join("\n");
}
