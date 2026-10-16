/**
 * The simulated device dressed up as MIDI ports.
 *
 * A browser application talks to the Electribe through Web MIDI. Install this
 * and the same application talks to the simulation instead, without knowing
 * and without a line of test-only code inside it.
 *
 * The point is not to let the application succeed. It is to let it fail
 * loudly: everything the device refuses is collected in `faults`, where the
 * real hardware would have answered with silence.
 */
import { SimDevice } from "./device.mjs";
import { VsbImage } from "./image.mjs";

const PORT_NAME = "electribe2 sampler PAD/KNOB";

function makePort(id, name, type) {
  return {
    id, name, type, manufacturer: "simulated", version: "0",
    state: "connected", connection: "open",
    async open() { return this; },
    async close() { return this; },
  };
}

/**
 * @param {object} opts
 * @param {import("./image.mjs").VsbImage} [opts.image] without one, RAM commands are refused with a reason
 * @param {Uint8Array} [opts.pattern] what the pattern buffer holds at the start
 * @param {number} [opts.channel] the global channel to answer on. Leave it
 *   away from zero on purpose: scripts that assume zero are the single most
 *   common reason a device looks like it has no extended commands.
 * @param {number} [opts.latencyMs] how long a reply takes to come back
 * @param {boolean} [opts.hacktribe] answers Hacktribe's commands 0x52 to 0x57
 * @param {boolean|number} [opts.blech] answers BLECH's own commands
 * @param {object} [opts.target] where to install; defaults to globalThis.navigator
 */
export function installWebMidiStub({ image = null, channel = 9, latencyMs = 2, target = null, pattern = null, hacktribe = true, blech = false } = {}) {
  const nav = target || globalThis.navigator;
  if (!nav) throw new Error("no navigator to install on");

  // The simulation writes into its image. Give it a copy, or every dry run
  // would quietly edit the firmware the user loaded.
  const device = new SimDevice({ image: image ? new VsbImage(image.bytes) : null, channel, pattern, hacktribe, blech });
  const input = makePort("sim-in", PORT_NAME, "input");
  const output = makePort("sim-out", PORT_NAME, "output");
  input.onmidimessage = null;

  output.send = data => {
    const reply = device.handle(data);
    if (!reply) return;                       // the hardware's way of saying no
    setTimeout(() => {
      if (input.onmidimessage) input.onmidimessage({ data: Uint8Array.from(reply) });
    }, latencyMs);
  };

  const access = {
    sysexEnabled: true,
    inputs: new Map([[input.id, input]]),
    outputs: new Map([[output.id, output]]),
    addEventListener() {},
    removeEventListener() {},
    onstatechange: null,
  };

  const previous = nav.requestMIDIAccess;
  nav.requestMIDIAccess = async (options = {}) => {
    if (!options.sysex) {
      device.fault("no-sysex",
        "the page asked for MIDI without SysEx. Everything this device understands is SysEx, " +
        "so the ports would open and nothing would work.");
    }
    return access;
  };

  return {
    device,
    access,
    get faults() { return device.faults; },
    restore() { nav.requestMIDIAccess = previous; },
  };
}
