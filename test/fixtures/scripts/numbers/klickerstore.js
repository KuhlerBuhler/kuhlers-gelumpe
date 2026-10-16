// Klicker that keeps its count, an app under TOOLS: TAP counts, korg.store.save() writes it to the card.
const TAP = 3;
const TAP_LED = 20;
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
  if (key == TAP) {
    count += 1;
    korg.store.set(SLOT, count);
    korg.store.save();
    korg.led(TAP_LED, count & 1 ? 255 : 0);
    show();
  }
});
