// Counter in the style of Korg Klicker, an app under TOOLS: TAP counts and lights the TAP LED
// always, the count shows on the app's own screen, which opens from the BLECH menu.
const TAP = 3;
const TAP_LED = 20;
korg.app("Klicker", "TOOLS");
let count = 0;

function show() {
  korg.display.clear();
  korg.display.text("Klicks", 0, 0);
  korg.display.number(count, 0, 16);
}

korg.onEvent("open", () => show());

korg.onEvent("buttonPress", (key) => {
  if (key == TAP) {
    count += 1;
    korg.led(TAP_LED, count & 1 ? 255 : 0);
    show();
  }
});
