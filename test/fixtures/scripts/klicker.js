// Counter in the style of Korg Klicker, an app under TOOLS: TAP counts and lights the TAP LED
// always, the count shows on the app's own screen, which opens from the BLECH menu.
// korg.key.TAP is the key code of the TAP button, korg.led.TAP the number of its LED.
// The compiler writes the numbers in, so a name costs nothing in the block.
korg.app("Klicker", "TOOLS");
let count = 0;

function show() {
  korg.display.clear();
  korg.display.text("Klicks", 0, 0);
  korg.display.number(count, 0, 16);
}

korg.onEvent("open", () => show());

korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) {
    count += 1;
    korg.led(korg.led.TAP, count & 1 ? 255 : 0);
    show();
  }
});
