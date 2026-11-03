// Image Viewer, an app under TOOLS: shows the pictures of a picture file GIF00.E2G to GIF99.E2G from KORG/blechtribe/Gif/
// on the card one at a time (tools/gif/gif2e2g.py puts several BMPs or other pictures into one file, one frame each).
// Part right and left show the next and the previous picture, the encoder picks the file. After each change the top left
// corner shows the number of the picture for two seconds, TAP keeps it there or hides it. Backwards past the first picture
// goes to the last one once the viewer has been through the file and knows how many there are.
korg.app("Image Viewer", "TOOLS");
const pic = new Array(1024);
let file = 0;
let index = 0;
let count = 0;
let shown = 0;
let label = 0;
let until = 0;
let isOpen = 0;

function digits(n) {
  let d = 1;
  while (n >= 10) {
    n = n / 10;
    d += 1;
  }
  return d;
}

function draw() {
  korg.display.clear();
  korg.display.bitmap(pic, 0, 0, 128);
  if (label == 0 && until == 0) return;
  let width = digits(index + 1) * 6 + 3;
  if (count > 0) width += digits(count) * 6 + 6;
  korg.display.clearRect(0, 0, width, 9);
  korg.display.number(index + 1, 1, 1);
  if (count > 0) korg.display.textNumber("/", count, 1 + digits(index + 1) * 6, 1);
}

function show() {
  let delay = korg.file.frame(pic, file, index);
  if (delay == 0 && index > 0) {
    count = index;
    index = 0;
    delay = korg.file.frame(pic, file, 0);
  }
  if (delay <= 0) {
    shown = 0;
    korg.display.clear();
    korg.display.textNumber("GIF ", file, 4, 14);
    korg.display.text("no file", 4, 26);
    return;
  }
  shown = 1;
  until = korg.millis() + 2000;
  draw();
}

korg.onEvent("open", () => {
  isOpen = 1;
  show();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("frame", () => {
  if (shown == 1 && until > 0 && korg.millis() >= until) {
    until = 0;
    draw();
  }
});

korg.onEvent("encoder", (i, delta) => {
  if (isOpen == 0) return;
  file += delta;
  if (file < 0) file = 0;
  if (file > 99) file = 99;
  index = 0;
  count = 0;
  show();
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 0) return;
  if (key == 15) {
    index += 1;
    show();
  }
  if (key == 11) {
    if (index > 0) index -= 1;
    else if (count > 0) index = count - 1;
    show();
  }
  if (key == 3 && shown == 1) {
    label = 1 - label;
    until = 0;
    draw();
  }
});
