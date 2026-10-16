/**
 * Loaded into the page by the browser tests, before anyone clicks connect:
 * installs the simulated device as Web MIDI ports, with the same firmware
 * the test hands to the page, and optional failures from the URL query.
 * Never part of the published page.
 */
import { installWebMidiStub } from "/src/webmidi.mjs";
import { VsbImage } from "/src/image.mjs";

const q = new URLSearchParams(location.search);
const list = name => (q.get(name) || "").split(",").filter(Boolean).map(Number);

const bytes = new Uint8Array(await (await fetch("/test-support/files/system.vsb")).arrayBuffer());
const sim = installWebMidiStub({ image: new VsbImage(bytes), channel: 9, latencyMs: Number(q.get("latency") ?? 2) });

// ?exec=1: the stand-in takes an execute command and notes the address, which it never does otherwise.
if (q.has("exec")) sim.device.execute = addr => { (window.__ceeExec ??= []).push(addr); return true; };

const swallow = list("swallow");
const corrupt = list("corrupt");
const unplugAfter = q.has("unplugAfter") ? Number(q.get("unplugAfter")) : null;
if (swallow.length || corrupt.length || unplugAfter !== null) {
  const input = sim.access.inputs.get("sim-in");
  const output = sim.access.outputs.get("sim-out");
  // The page also polls the device (screen state, display), so the counts start only when a test arms them, just before its send.
  let armed = false;
  let replies = 0;
  let sent = 0;
  window.__ceeArm = () => { armed = true; replies = 0; sent = 0; };
  const realSend = output.send;
  output.send = msg => {
    if (armed) sent++;
    if (armed && unplugAfter !== null && sent > unplugAfter) {
      output.state = "disconnected";
      sim.access.onstatechange?.({ port: output });
      return;
    }
    realSend(msg);
  };
  // The page sets onmidimessage later; wrap whatever it sets.
  let handler = null;
  Object.defineProperty(input, "onmidimessage", {
    set(fn) { handler = fn; },
    get() {
      return e => {
        if (armed) replies++;
        if (armed && swallow.includes(replies)) return;
        let data = e.data;
        if (armed && corrupt.includes(replies) && (data[6] === 0x54 || data[6] === 0x40)) { data = Uint8Array.from(data); data[data.length - 2] ^= 1; }
        handler?.({ data });
      };
    },
  });
}
window.__ceeSim = sim;
