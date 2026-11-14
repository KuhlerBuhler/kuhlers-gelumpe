// STOP-Takt: solange der Sequencer läuft, blinkt die STOP-LED kurz im Tempo des Patterns, bei STOP und in der Pause ist
// sie aus. Die PLAY-LED fasst das Plugin nicht an, sie gehört ganz der Firmware und zeigt weiter Spielen und Pause. Dabei
// zeigt es die Timer der Plugin-API (API 11): `beat` kommt auf jede Viertel und macht die LED an, korg.afterSteps(1, off)
// macht sie einen Schritt später wieder aus, so folgt das Blinken dem Tempo. STOP und Pause räumen den Timer mit
// korg.cancel ab.
let dark = -1;

function off() {
  korg.led(19, 0);
}

korg.onEvent("ready", () => { off(); });

korg.onEvent("beat", () => {
  korg.cancel(dark);
  korg.led(19, 255);
  dark = korg.afterSteps(1, off);
});

korg.onEvent("stop", () => {
  korg.cancel(dark);
  off();
});
