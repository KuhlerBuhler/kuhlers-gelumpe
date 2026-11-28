/** Measured search reply and immutable code signatures for the supported build. */
export default [{
  version: [2, 2],
  label: "Electribe 2 Sampler 2.02 mit vermessenem Hacktribe",
  evidence: "measure:2026-10-08/geraeteprotokoll",
  fingerprints: [
    { addr: 0xc0000040, length: 64, sha256: "0ecfbf472eb414c359f29af80817ad36cac542fe94b1f4e3cd4fe078a50e6de0" },
    { addr: 0xc017059c, length: 512, sha256: "94975043805a3baa09d4916636d9ba93c9ab7c367efbf7b8d8d8e1b848219470" },
  ],
  measurements: {
    transport: "Linux USB ALSA",
    searchMaxMs: 2.392, read16384MaxMs: 80.835,
    ramAckSmallMaxMs: 186.974, ramAck52400Ms: 684.319, patternAckMs: 183.377,
    ramWriteProvenBytes: 52400,
  },
}, {
  version: [2, 2],
  build: "stock",
  label: "Electribe 2 Sampler 2.02, Korgs Original, mit BLECHTRIBE",
  evidence: "measure:2026-10-15/blech-sysex",
  // Code of Korg's build that no BLECH patch touches and that Hacktribe changed (0xC0026450), and the run Hacktribe's code fills (FF at Korg's).
  fingerprints: [
    { addr: 0xc0000040, length: 64, sha256: "0ecfbf472eb414c359f29af80817ad36cac542fe94b1f4e3cd4fe078a50e6de0" },
    { addr: 0xc0026430, length: 64, sha256: "c39f99455af200a946c704d0eeb8c653aa50c9c40f39145391eb9d4830e4dc00" },
    { addr: 0xc0170000, length: 256, sha256: "3d6876a0146de8576eb2395a858de1213d1b92c65b779df3a331cfd5a4584546" },
  ],
  measurements: { transport: "emulated DIN, BLECH's own commands" },
}, {
  version: [2, 2],
  build: "synth",
  label: "Electribe 2 (blau) 2.02, Korgs Original, mit BLECHTRIBE",
  evidence: "measure:2026-10-16/blech-synth",
  // Code of Korg's blue build that no BLECH patch touches and that the red builds have otherwise; only asked of a device that
  // answers the search as model 0x23.
  fingerprints: [
    { addr: 0xc0000040, length: 64, sha256: "8d17b1133ba069a7e11ae80ccb4fadbcb918028ce4744c162474731600099330" },
    { addr: 0xc0001000, length: 256, sha256: "823cbc23d78acfbd1ea75268dd36475df86f264cfe3c11607a835d8daa44d422" },
    { addr: 0xc0020000, length: 256, sha256: "60482e157eef57ef2ef2cf63368a983fe2d4d301fe6c282b5008e0970eb4b6c7" },
  ],
  measurements: { transport: "emulated DIN, BLECH's own commands with model byte 0x23" },
}];
