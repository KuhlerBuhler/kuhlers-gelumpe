import KNOWN from "/data/devices.mjs";
import { DeviceSession, electribePorts } from "/src/session.mjs";
import { Pattern } from "/src/pattern.mjs";

/** Pattern transport in the browser, with generated data and Web MIDI ports. */
export async function patternSession() {
  const start = new Uint8Array(await (await fetch("/test-support/files/pattern.bin")).arrayBuffer());
  window.__ceeSim.device.pattern = start.slice();
  const access = await navigator.requestMIDIAccess({ sysex: true });
  const session = new DeviceSession({ port: electribePorts(access)[0], known: KNOWN });
  await session.connect();
  const pattern = new Pattern(await session.fetchPattern());
  return { session, pattern, start, sim: window.__ceeSim };
}
