/** The sequencer and panel state a script can read, for the simulated device. The values follow the firmware's ranges. */
import { SCRIPT_KNOBS } from "../../data/script/contract.mjs";
import { KEY_NAMES } from "../../data/script/names.mjs";

const KEY_TOUCHPAD = KEY_NAMES.find(n => n.name === "TOUCHPAD").value;
const KEY_PLAY = KEY_NAMES.find(n => n.name === "PLAY").value;
const KEY_STOP = KEY_NAMES.find(n => n.name === "STOP").value;

export class SimHardware {
  /** @param {(event: string, ...args: number[]) => void} [emit] where hardware events go, in the page the runtime's ring */
  constructor(emit = () => {}) {
    this.emit = emit;
    this.stepFraction = 0;
    this.transport = 0;
    this.tempo = 1200;
    this.pattern = 0;
    this.part = 0;
    this.steps = new Int32Array(16);
    this.mutes = new Uint8Array(16);
    this.knobs = new Int32Array(SCRIPT_KNOBS);
    this.backlight = [1, 1, 1];
    this.ledHold = 0;
    /** 0 finger up, 1 the press came and the first position has not, 2 the first position is out. */
    this.touch = 0;
  }

  /** Host functions for the read API entries. */
  api() {
    return {
      "korg.read.transport": () => this.transport,
      "korg.read.tempo": () => this.tempo,
      "korg.read.pattern": () => this.pattern,
      "korg.read.part": () => this.part,
      "korg.read.step": part => this.steps[part],
      "korg.read.mute": part => this.mutes[part],
      "korg.read.knob": index => this.knobs[index],
      "korg.play": () => { if (this.transport !== 1) { this.transport = 1; this.emit("play"); } },
      "korg.stop": () => { if (this.transport !== 0) { this.transport = 0; this.steps.fill(0); this.emit("stop"); } },
      "korg.pattern": index => { this.pattern = index; this.emit("patternChange", index); },
      "korg.tempo": tenths => { this.tempo = tenths; this.emit("tempo", tenths); },
      "korg.part": part => { this.part = part; this.emit("partChange", part); },
      "korg.backlight": (red, green, blue) => { this.backlight = [red, green, blue]; },
      "korg.ledHold": on => { this.ledHold = on; },
      "korg.mute": (part, muted) => { if (this.mutes[part] !== muted) { this.mutes[part] = muted; this.emit("mute", part, muted); } },
    };
  }

  /** The sequencer moves on by one frame: while playing, steps (16ths) and beats follow the tempo. */
  tick(frameMs) {
    if (this.transport !== 1) return;
    this.stepFraction += (this.tempo * 4 / 600) * (frameMs / 1000);
    while (this.stepFraction >= 1) {
      this.stepFraction -= 1;
      this.steps.fill((this.steps[0] + 1) % 64);
      this.emit("step", this.steps[0]);
      if (this.steps[0] % 4 === 0) this.emit("beat");
    }
  }

  /**
   * An input as the input filter sees it: the last value per knob stays readable, and a touch position gets its third value
   * `first`, 1 for the first position after the press (or after nothing, when a position comes without a press) and 0 for
   * the ones that follow. Returns the values the event carries.
   */
  input(event, ...args) {
    if (event === "knob" && args[0] >= 0 && args[0] < SCRIPT_KNOBS) this.knobs[args[0]] = args[1] | 0;
    // PLAY and STOP reach the firmware even while an app is open, and the app sees the key as well
    if (event === "buttonPress" && args[0] === KEY_PLAY) this.api()["korg.play"]();
    if (event === "buttonPress" && args[0] === KEY_STOP) this.api()["korg.stop"]();
    if (event === "buttonPress" && args[0] === KEY_TOUCHPAD) this.touch = 1;
    if (event === "buttonRelease" && args[0] === KEY_TOUCHPAD) this.touch = 0;
    if (event === "touch") {
      const first = this.touch === 2 ? 0 : 1;
      this.touch = 2;
      return [args[0], args[1], first];
    }
    return args;
  }
}
