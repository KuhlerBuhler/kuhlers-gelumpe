// Klicker that keeps its count, an app under TOOLS: TAP counts, korg.store.save() writes it to the card.
// korg.key.TAP is the key code of the TAP button, korg.led.TAP the number of its LED.
// The compiler writes the numbers in, so a name costs nothing in the block.
korg.app("Klicker Store", "TOOLS");
const SLOT = 0;
let count = korg.store.get(SLOT, 0);

function show() {
  korg.display.clear();
  korg.display.text("Klicks", 0, 0);
  korg.display.number(count, 0, 16);
}

korg.onEvent("open", () => show());

korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) {
    count += 1;
    korg.store.set(SLOT, count);
    korg.store.save();
    korg.led(korg.led.TAP, count & 1 ? 255 : 0);
    show();
  }
});
