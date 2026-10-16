import { field, offsetOf, typeOf } from "../../src/map/index.mjs";
import { ramEntry } from "../../src/map/address.mjs";

/**
 * The RAM bytes of one sample as the three tables hold them, built from nothing: [{ addr, bytes }].
 * `entry` carries index, name and any of the measured fields; what it leaves out stays zero.
 */
export function sampleRam({ index, name = "", tune = 0, rate = 0, pcmBytes = 0, stereo = 0, category = 0, importNumber = 0, oneShot = 0, loop = 0, end = 0, start = 0 }) {
  const part = (block, size, values) => {
    const bytes = new Uint8Array(size);
    for (const [id, value] of values) typeOf(field(id)).write(bytes, offsetOf(field(id)), value);
    return { addr: ramEntry(block, index).ram, bytes };
  };
  return [
    part("sampleName", 0x20, [["sample.name", name], ["sample.category", category], ["sample.importNumber", importNumber]]),
    part("samplePlayback", 0x10, [["sample.start", start], ["sample.loop", loop], ["sample.end", end], ["sample.oneShot", oneShot]]),
    part("sampleMeta", 0x45c, [["sample.pcmBytes", pcmBytes], ["sample.stereo", stereo], ["sample.rate", rate], ["sample.tune", tune]]),
  ];
}

/** Put one sample into a SimDevice. */
export function putEntry(device, entry) {
  for (const { addr, bytes } of sampleRam(entry)) if (!device.poke(addr, bytes)) throw new Error(`no RAM at 0x${addr.toString(16)}`);
}
