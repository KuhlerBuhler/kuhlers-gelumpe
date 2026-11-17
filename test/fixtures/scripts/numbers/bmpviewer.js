// Image Viewer, an app under TOOLS: shows the start images (.bmp) and the loading animations (.blla) in KORG/blechtribe/Media/
// on the card. The first screen lists IMAGES and ANIMATIONS with how many there are: the encoder or Part picks one, MENU opens
// it, MENU in it goes back to the list (EXIT closes the app).
// IMAGES: the encoder and Part page through the files and wrap around. After each change the name and the place show for two
// seconds, TAP keeps them there or hides them.
// ANIMATIONS: the encoder picks the file and shows its first picture, Part right and left go one picture on or back, TAP plays
// and pauses. Playing shows a picture every 96 ms, Part right and left halve and double that (48 to 384 ms). An animation runs
// through its progress pictures and its loop pictures, then starts again.
korg.app("Image Viewer", "TOOLS");
const pic = new Array(1024);
const nm = new Array(18);
let mode = 0;
let sel = 0;
let n0 = 0;
let n1 = 0;
let file = 0;
let frame = 0;
let total = 0;
let label = 0;
let until = 0;
let playing = 0;
let ms = 96;
let due = 0;
let isOpen = 0;

function digits(n) {
  let d = 1;
  while (n >= 10) {
    n = n / 10;
    d += 1;
  }
  return d;
}

function files() {
  if (mode == 1) return n0;
  return n1;
}

function drawList() {
  korg.display.clear();
  if (n0 < 0 || n1 < 0) {
    korg.display.text("NO CARD", 4, 26);
    return;
  }
  korg.display.textNumber("IMAGES ", n0, 12, 18);
  korg.display.textNumber("ANIMATIONS ", n1, 12, 32);
  korg.display.text(">", 4, 18 + sel * 14);
}

function list() {
  mode = 0;
  playing = 0;
  n0 = korg.file.count(0);
  n1 = korg.file.count(1);
  drawList();
}

function place(a, b) {
  korg.display.clearRect(0, 55, (digits(a) + digits(b)) * 6 + 9, 9);
  korg.display.number(a, 1, 56);
  korg.display.textNumber("/", b, 1 + digits(a) * 6, 56);
}

function draw() {
  korg.display.clear();
  if (files() <= 0) {
    if (mode == 1) korg.display.text("NO IMAGES", 4, 26);
    else korg.display.text("NO ANIMATIONS", 4, 26);
    return;
  }
  let len = korg.file.name(nm, mode - 1, file);
  if (total <= 0) {
    korg.display.chars(nm, 4, 18, 17);
    korg.display.text("BAD FILE", 4, 32);
    return;
  }
  korg.display.bitmap(pic, 0, 0, 128);
  if (label == 0 && until == 0) return;
  korg.display.clearRect(0, 0, len * 6 + 3, 9);
  korg.display.chars(nm, 1, 1, 17);
  if (mode == 1) place(file + 1, files());
  else place(frame + 1, total);
}

function show() {
  if (files() > 0) total = korg.file.picture(pic, mode - 1, file, frame);
  until = korg.millis() + 2000;
  draw();
}

function pick(delta) {
  let n = files();
  if (n <= 0) return;
  file = ((file + delta) % n + n) % n;
  frame = 0;
  playing = 0;
  show();
}

function step(delta) {
  if (total <= 0) return;
  frame = ((frame + delta) % total + total) % total;
  show();
}

korg.onEvent("open", () => {
  isOpen = 1;
  list();
});

korg.onEvent("close", () => {
  isOpen = 0;
  playing = 0;
});

korg.onEvent("frame", () => {
  if (mode == 0) return;
  if (playing == 1 && korg.millis() >= due) {
    if (until > 0 && korg.millis() >= until) until = 0;
    frame = (frame + 1) % total;
    total = korg.file.picture(pic, 1, file, frame);
    if (total <= 0) playing = 0;
    due += ms;
    if (due < korg.millis()) due = korg.millis() + ms;
    draw();
    return;
  }
  if (until > 0 && korg.millis() >= until) {
    until = 0;
    draw();
  }
});

korg.onEvent("encoder", (i, delta) => {
  if (isOpen == 0) return;
  if (mode == 0) {
    if (delta > 0) sel = 1;
    if (delta < 0) sel = 0;
    drawList();
    return;
  }
  pick(delta);
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 0) return;
  if (mode == 0) {
    if (key == 11) sel = 0;
    if (key == 15) sel = 1;
    if (key == 9 && n0 >= 0 && n1 >= 0) {
      mode = sel + 1;
      file = 0;
      frame = 0;
      label = 0;
      show();
      return;
    }
    drawList();
    return;
  }
  if (key == 9) {
    list();
    return;
  }
  if (mode == 1) {
    if (key == 15) pick(1);
    if (key == 11) pick(-1);
    if (key == 3 && files() > 0) {
      label = 1 - label;
      until = 0;
      draw();
    }
    return;
  }
  if (playing == 1) {
    if (key == 15 && ms > 48) ms = ms / 2;
    if (key == 11 && ms < 384) ms = ms * 2;
  } else {
    if (key == 15) step(1);
    if (key == 11) step(-1);
  }
  if (key == 3 && total > 0) {
    playing = 1 - playing;
    due = korg.millis() + ms;
    until = korg.millis() + 2000;
    draw();
  }
});
