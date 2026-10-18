/**
 * Call chains of firmware 2.02 with Hacktribe that code patches hook into
 * (docs/patcher.md, "Haken-Register"; src/hooks.mjs reads this).
 *
 * A chain lists the stages an event passes, upstream first; a stage groups
 * sites at the same point of the way. A hook on a site missing here is
 * refused. A stage with several sites can mean several entry paths to one
 * point (wheel, pad and MIDI all end in set_number), so ordering against an
 * upstream stage is conservative for it. Sources: the research notes
 * 2026-10-12-skript-laufzeit.md and 2026-10-12-patternwechsel.md, and the
 * two built patches.
 */
export const CHAINS = {
  "start": [
    { id: "after-rescue-paths", sites: [0xC002ADAC] },
    { id: "card-mount", sites: [0xC002AE60] },
    { id: "doom-select", sites: [0xC002AE64] },
    { id: "before-sample-load", sites: [0xC0038D34] },
    { id: "sample-load", sites: [0xC0038D60, 0xC00366D4] },
    { id: "after-sample-load", sites: [0xC0038D68] },
    { id: "after-native-initialization", sites: [0xC0028170] },
  ],
  "sample-errors": [
    { id: "loader-entry", sites: [0xC00364F0] },
    { id: "format-check", sites: [0xC0035FB4, 0xC0035FC4, 0xC0035FD4] },
    { id: "slot-refuse", sites: [0xC004EE0C, 0xC004EE50, 0xC004EE68] },
    { id: "result", sites: [0xC0036700] },
    { id: "done", sites: [0xC0036714] },
    { id: "window", sites: [0xC00630F0, 0xC0063144] },
  ],
  "start-image": [{ id: "early-draw", sites: [0xC002AC38] }],
  "global-screen": [
    { id: "vtable-literal", sites: [0xC0064D3C] },
    { id: "page-count", sites: [0xC0064980, 0xC0064D04] },
  ],
  "key-dispatch": [
    { id: "input-filter", sites: [0xC002837C] },
    { id: "tap-handler", sites: [0xC0042CC0] },
    { id: "dispatcher", sites: [0xC00700D8] },
    { id: "screen-slots", sites: [0xC00E34A0, 0xC00E34B0] },
  ],
  "pattern-set": [
    { id: "input-filter", sites: [0xC002837C] },
    // wheel, pad and MIDI all end in set_number: the entries are one stage, set_number the next
    { id: "select", sites: [0xC006513C, 0xC006EDE4, 0xC006EE00] },
    { id: "set-number", sites: [0xC0081F50] },
  ],
  "sequence-end": [{ id: "pattern-number", sites: [0xC005F1C4] }],
  "stop-pending": [{ id: "apply-pending", sites: [0xC0081B5C] }],
  "pattern-label": [{ id: "next-view", sites: [0xC0086DC4] }],
  "stopped-sync": [{ id: "load-chosen", sites: [0xC0081E18] }],
  "frame": [
    { id: "frame-call", sites: [0xC00836F0] },
    { id: "screen-tick", sites: [0xC00836F8] },
    { id: "screen-tick-entry", sites: [0xC006F178] },
    { id: "frame-hook", sites: [0xC00836FC] },
    { id: "display-flush", sites: [0xC008370C] },
  ],
  "type-set": [{ id: "setter", sites: [0xC0048A64] }],
  "filter-key": [{ id: "selection", sites: [0xC006FCE8] }],
  "filter-type-store": [{ id: "setter", sites: [0xC00495DC] }],
  "pattern-write": [{ id: "staging-copy", sites: [0xC004C2BC] }],
  "save": [{ id: "entry", sites: [0xC004C1B4] }],
  "seq-step": [{ id: "step", sites: [0xC00589EC] }],
  "seq-beat": [{ id: "beat", sites: [0xC005BD7C] }],
  "seq-tick": [{ id: "tick", sites: [0xC005E918] }],
  "play": [{ id: "state-machine", sites: [0xC0083000] }],
  "stop": [{ id: "transport-stop", sites: [0xC0082D40] }],
  "rec": [{ id: "rec-ready", sites: [0xC0082944] }],
  "menu-ring": [
    { id: "factory", sites: [0xC006E664, 0xC006E68C, 0xC0061B68, 0xC0061B90] },
    { id: "neighbours", sites: [0xC0064D84, 0xC0061880, 0xC0064430, 0xC0067754] },
  ],
  "menu-top-level": [{ id: "screen-switch", sites: [0xC006E8D8, 0xC0061DDC] }],
  "menu-write": [{ id: "write-key", sites: [0xC006F094] }],
  "menu-counter": [{ id: "page-counter", sites: [0xC008A83C, 0xC008A8A8] }],
  "led-meter": [{ id: "meter-update", sites: [0xC0088284] }],
  "backlight": [
    { id: "power-save-switch", sites: [0xC0028AB4] },
    { id: "pin-setters", sites: [0xC0016C98, 0xC0016CE0, 0xC0016D28] },
    { id: "dim-irq", sites: [0xC00289F4] },
  ],
  "lcd-invert": [{ id: "page-write", sites: [0xC00161A4] }],
  "power-off": [{ id: "hold-wait", sites: [0xC0038A74] }],
  "sysex-request": [
    { id: "classify", sites: [0xC0026A8C, 0xC002240C] },   // the second of each is the synth build's
    { id: "process", sites: [0xC0026418, 0xC0021D70] },
  ],
  "tap-led": [
    { id: "beat-flash", sites: [0xC00881E0] },
    { id: "led-tick", sites: [0xC0087740] },
  ],
  "pad-note": [
    { id: "keyboard-pad", sites: [0xC0044B3C] },
    { id: "pad-light", sites: [0xC008870C] },
  ],
  "led-tick-end": [{ id: "tick-end", sites: [0xC00877D4] }],
  "led-send": [{ id: "sender", sites: [0xC00876A8] }],
  "mode-key": [{ id: "mode-keys", sites: [0xC006FEDC] }],
};

/** Patch id pairs that cannot be applied together, with the reason shown to the user. */
export const INCOMPATIBLE = [
  {
    patches: ["splash-editor", "script-runtime"],
    sharedSites: [0xC002ADAC, 0xC0064D3C],
    reason: "Start-Haken 0xC002ADAC oder Global-Literal 0xC0064D3C ist doppelt beansprucht. Die gemeinsame BLECH-Laufzeit bringt den Startbild-Editor als eingebautes Modul mit.",
  },
];
