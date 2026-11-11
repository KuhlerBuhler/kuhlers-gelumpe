// PLAY-Takt: solange der Sequencer läuft, blinkt die PLAY-LED im Tempo des Patterns, bei STOP und Pause leuchtet sie
// ruhig. Dabei zeigt es die Timer der Plugin-API (API 11): `beat` kommt auf jede Viertel und macht die LED an,
// korg.afterSteps(2, off) macht sie zwei Schritte später wieder aus, so folgt das Blinken dem Tempo. STOP und Pause räumen
// den Timer mit korg.cancel ab. In der Pause blinkt die Firmware die PLAY-LED selbst, das Plugin setzt sie dort in jedem
// Rahmen wieder an.
let dark = -1;

function playLed(level) {
  korg.led(9, level);
  korg.led(21, level);
}

function off() {
  playLed(0);
}

korg.onEvent("ready", () => { if (korg.transport == 0) playLed(255); });

korg.onEvent("beat", () => {
  korg.cancel(dark);
  playLed(255);
  dark = korg.afterSteps(2, off);
});

korg.onEvent("stop", () => {
  korg.cancel(dark);
  playLed(255);
});

korg.onEvent("frame", () => { if (korg.transport == 2) playLed(255); });
