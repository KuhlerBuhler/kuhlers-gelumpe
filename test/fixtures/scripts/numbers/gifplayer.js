// GIF Player, an app under TOOLS: plays the picture files GIF00.E2G to GIF99.E2G from KORG/blechtribe/Gif/ on the card
// (tools/gif/gif2e2g.py makes one from a GIF). The encoder picks the file, Part left and right halve and double the speed
// (25 to 400 percent), TAP pauses. The runtime draws once per frame of 40 ms, so a picture stays at least that long.
korg.app("GIF Player", "TOOLS");
const pic = new Array(1024);
let file = 0;
let index = 0;
let speed = 100;
let paused = 0;
let due = 0;
let isOpen = 0;

function info(pause) {
  korg.display.clear();
  korg.display.textNumber("GIF ", file, 4, 14);
  if (pause == 1) korg.display.text("Pause", 4, 26);
  else korg.display.text("keine Datei", 4, 26);
  korg.display.textNumber("Tempo % ", speed, 4, 38);
}

function next() {
  let delay = korg.file.frame(pic, file, index);
  if (delay == 0 && index > 0) {
    index = 0;
    delay = korg.file.frame(pic, file, 0);
  }
  if (delay <= 0) {
    info(0);
    due = korg.millis() + 500;
    return;
  }
  korg.display.clear();
  korg.display.bitmap(pic, 0, 0, 128);
  index += 1;
  due = korg.millis() + delay * 100 / speed;
}

korg.onEvent("open", () => {
  isOpen = 1;
  index = 0;
  due = 0;
  next();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("frame", () => {
  if (paused == 0 && korg.millis() >= due) next();
});

korg.onEvent("encoder", (i, delta) => {
  if (isOpen == 0) return;
  file += delta;
  if (file < 0) file = 0;
  if (file > 99) file = 99;
  index = 0;
  due = 0;
  if (paused == 1) next();
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 0) return;
  if (key == 11 && speed > 25) speed = speed / 2;
  if (key == 15 && speed < 400) speed = speed * 2;
  if (key == 3) paused = 1 - paused;
  if (key == 3 && paused == 1) info(1);
  if (key == 3 && paused == 0) due = 0;
});
