// Takt-Blinker: zeigt die Timer der Plugin-API (API 11). Die TAP-LED blinkt alle 500 ms, ohne dass das Plugin
// Rahmen zählt; bei PLAY leuchtet Pad 1 auf jeden vierten Schritt kurz auf: korg.afterSteps zählt die Schritte,
// korg.after macht das Licht nach 100 ms wieder aus. STOP hält die Schritte an, korg.cancel räumt auf.
let on = 0;
let beat = -1;

function blink() {
  on = 1 - on;
  korg.led(20, on * 255);
}

function padOff() {
  korg.led(44, 0);
}

function nextBeat() {
  korg.led(44, 255);
  korg.after(100, padOff);
  beat = korg.afterSteps(4, nextBeat);
}

korg.onEvent("ready", () => { korg.every(500, blink); });
korg.onEvent("play", () => { korg.cancel(beat); beat = korg.afterSteps(4, nextBeat); });
korg.onEvent("stop", () => { korg.cancel(beat); padOff(); });
