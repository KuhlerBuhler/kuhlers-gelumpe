/**
 * Parameter sets offered on top of an existing preset. A suggestion never
 * brings a record of its own: the user's record keeps every byte nobody
 * decoded, and only the listed parameters change.
 *
 * Nothing here has been heard. The values stay inside what the factory
 * presets of the same unit use, and say so as `untested`.
 */
export default [
  {
    id: "pseudoReverb",
    label: { de: "Pseudo Reverb", en: "Pseudo reverb" },
    unit: 0x18,
    stage: "ifx1",
    untested: true,
    note: "short delay with feedback and a dark repeat, as an ambience per part; no real reverb",
    hint: "Short Delay mit kurzer Zeit, Rückkopplung und dunklen Wiederholungen als Raum pro Part. Kein echter Hall, und am Gerät nicht gehört.",
    params: { tempo_sync: 0, off_delay_time: 19, fb_depth: 64, high_damp: 72, low_damp: 8, wet_level: 56 },
    source: "unknown",
  },
];
