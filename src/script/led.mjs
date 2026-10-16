import { SCRIPT_LED, SCRIPT_LED_VALID } from "../../data/script/contract.mjs";

const OFFSETS = Object.fromEntries(SCRIPT_LED.fields.map(f => [f.name, f.offset]));

/** LED requests share a last-value ledger; sending requires an atomic transport acceptance. */
export class ScriptLeds {
  #nextIndex;
  #sentThisFrame = 0;

  constructor() {
    this.bytes = new Uint8Array(SCRIPT_LED.size);
    for (const name of ["desired", "delivered", "pending", "valid"]) {
      this[name] = new Uint8Array(this.bytes.buffer, OFFSETS[name], SCRIPT_LED.count);
    }
    this.#nextIndex = new DataView(this.bytes.buffer, OFFSETS.nextIndex, 4);
  }

  get nextIndex() { return this.#nextIndex.getUint32(0, true); }

  /** Delivery knowledge expires each frame; only pending or explicit requests can cause another send. */
  beginFrame() {
    for (let i = 0; i < SCRIPT_LED.count; i++) this.valid[i] &= SCRIPT_LED_VALID.DESIRED;
    this.#sentThisFrame = 0;
  }

  request(index, level) {
    if (!Number.isInteger(index) || index < 0 || index >= SCRIPT_LED.count) throw new RangeError(`LED index must be between 0 and ${SCRIPT_LED.count - 1}`);
    if (!Number.isInteger(level) || level < 0 || level > SCRIPT_LED.levelMax) throw new RangeError(`LED level must be between 0 and ${SCRIPT_LED.levelMax}`);
    this.desired[index] = level;
    this.valid[index] |= SCRIPT_LED_VALID.DESIRED;
    this.pending[index] = (this.valid[index] & SCRIPT_LED_VALID.DELIVERED) && this.delivered[index] === level ? 0 : 1;
    return 0;
  }

  /** Drain at most one frame's allowance, retaining rejected commands and the round-robin cursor. */
  flushFrame({ queueFree, send, canSend = () => true }) {
    if (typeof queueFree !== "function" || typeof send !== "function" || typeof canSend !== "function") throw new TypeError("queueFree, send and canSend must be functions");
    let sent = 0;
    for (let scanned = 0; scanned < SCRIPT_LED.count && this.#sentThisFrame < SCRIPT_LED.perFrame; scanned += 1) {
      const index = this.nextIndex;
      if (this.pending[index]) {
        const allowed = canSend();
        if (typeof allowed !== "boolean") throw new TypeError("canSend must return a boolean frame-budget decision");
        if (!allowed) break;
        const free = queueFree();
        if (!Number.isSafeInteger(free) || free < 0) throw new RangeError("queueFree must return a nonnegative integer byte count");
        if (free < SCRIPT_LED.packetBytes + SCRIPT_LED.reserveBytes) break;
        const level = this.desired[index];
        const accepted = send(index, level);
        if (typeof accepted !== "boolean") throw new TypeError("send must return a boolean atomic acceptance");
        if (!accepted) break;
        this.delivered[index] = level;
        this.valid[index] |= SCRIPT_LED_VALID.DELIVERED;
        this.pending[index] = this.desired[index] === level ? 0 : 1;
        sent += 1;
        this.#sentThisFrame += 1;
      }
      this.#nextIndex.setUint32(0, (index + 1) % SCRIPT_LED.count, true);
    }
    return sent;
  }
}
