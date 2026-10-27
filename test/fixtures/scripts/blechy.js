// Blechy, a run-down nose, built into BLECH: he is the last page of the Electribe's menu ring, open (and with the
// open event) whenever the firmware shows that page, closed (close event) when it shows another one.
// The firmware registers him as a hidden app before this body runs, so the line below only names him; the browser
// model needs it to let him draw.
// Open: he stands at the left edge, about a second after you land on his page he waves (once per landing), then he
// walks slowly to the right edge and back, again and again. Now and then, when he has reached an edge, he stops and
// says something in a speech bubble (a rotation of short lines, among them the favourite tempo and how long you have
// been at it). A tap on the touchpad near him makes him angry, stroking makes him happy.
// PLAY: he walks to the middle, says he will listen for a moment, listens, and then dances (schranz) as long as the
// pattern plays; the pose changes on step events, not on a clock. On stop he walks again.
// The stats live in RAM only. Closed, he draws nothing and only counts. His pictures are the frame tables
// in data/script/blechy-art.mjs, drawn as bitmaps at an offset (posX, posY); the drawing only runs when the picture changes.
korg.app("Blechy", "GAMES");
// The frame numbers and the pictures below are made from data/script/blechy-art.mjs by tools/blechy-build.mjs.
const F_IDLE = 0;
const F_TWITCH = 1;
const F_ANGRY = 2;
const F_HAPPY = 3;
const F_FLAIL = 4;
const F_WAVE = 8;
const F_WALK = 10;
const F_BACK = 11;
const FIG_LEFT = 5;
const FIG_RIGHT = 45;
const WALK_RIGHT = 48;

const P_STAND_BASE = [
  0, 0, 0, 0, 224, 16, 140, 134, 130, 99, 161, 161, 161, 3, 18, 22, 28, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 127, 255, 7, 1, 28, 99, 65, 140, 140, 140, 65, 99, 28, 0, 0, 0, 16, 0, 0, 0, 0, 0, 0, 0, 16, 192, 128, 0, 0, 0, 0,
  0, 0, 0, 240, 31, 7, 12, 8, 13, 26, 20, 20, 116, 74, 69, 64, 64, 64, 64, 64, 101, 40, 48, 16, 24, 8, 13, 7, 1, 1, 3, 2, 28, 240,
  8, 4, 0, 7, 28, 112, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 112, 28, 7,
  0, 0, 0, 0, 0, 0, 1, 7, 28, 48, 96, 192, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 96, 48, 28, 7, 1, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameStandBase(ox, oy) {
  korg.display.bitmap(P_STAND_BASE, ox + 7, oy + 7, 34);
}

const P_STAND_CORE = [
  0, 0, 0, 0, 192, 32, 24, 8, 0, 192, 64, 64, 64, 0, 32, 40, 56, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 254, 255, 14, 3, 57, 199, 130, 25, 25, 25, 130, 198, 56, 0, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0, 32, 128, 0, 0, 0, 0, 0,
  0, 0, 0, 224, 63, 14, 24, 16, 26, 52, 41, 41, 233, 148, 138, 128, 128, 128, 128, 128, 202, 80, 96, 32, 48, 16, 26, 14, 3, 3, 6, 4, 56, 224,
  16, 8, 0, 15, 56, 224, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 224, 56, 15,
  0, 0, 0, 0, 0, 0, 3, 14, 56, 96, 192, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 192, 96, 56, 14, 3, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 6, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameStandCore(ox, oy) {
  korg.display.bitmap(P_STAND_CORE, ox + 7, oy + 6, 34);
}

const P_IDLE = [
  0, 0, 0, 0, 0, 0, 0, 2, 1, 0, 4, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 196, 52, 20, 204, 202, 202, 18, 50, 194, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 6, 36, 73, 73, 73, 36, 6, 0, 0, 0, 0, 64, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32, 64, 128, 128, 0,
  2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 240, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 208, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 96, 96, 96, 124, 99, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 96, 99, 124, 96, 96, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameIdle(ox, oy) {
  korg.display.bitmap(P_IDLE, ox + 5, oy + 11, 41);
}

const P_TWITCH = [
  0, 0, 0, 0, 0, 0, 0, 4, 2, 0, 8, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 4, 132, 130, 66, 66, 66, 129, 129, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 12, 17, 32, 78, 78, 78, 32, 17, 12, 0, 0, 0, 128, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 64, 128, 0, 0, 0,
  4, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 160, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 192, 192, 248, 199, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 199, 248, 192, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameTwitch(ox, oy) {
  korg.display.bitmap(P_TWITCH, ox + 5, oy + 10, 41);
}

const P_ANGRY = [
  0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 4, 136, 152, 152, 16, 32, 16, 0, 0, 0, 112, 56, 24, 252, 236, 236, 14, 30, 99, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 18, 36, 36, 36, 18, 3, 0, 0, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 32, 64, 64, 128,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 232, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 62, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 62, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameAngry(ox, oy) {
  korg.display.bitmap(P_ANGRY, ox + 5, oy + 4, 41);
}

const P_HAPPY = [
  0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 192, 0, 0, 0, 193, 1, 0, 0, 0, 0, 96, 25, 201, 101, 101, 101, 201, 25, 96, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 18, 36, 36, 36, 18, 3, 0, 0, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 32, 64, 64, 128,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 232, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 62, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 62, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameHappy(ox, oy) {
  korg.display.bitmap(P_HAPPY, ox + 5, oy + 4, 41);
}

const P_WAVE0 = [
  0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 224, 128, 0,
  0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 0, 128, 128, 128, 0, 0, 0, 0, 0, 0, 98, 26, 10, 230, 229, 229, 9, 25, 97, 0, 0, 0, 0, 0, 0, 159, 127, 30,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 18, 36, 36, 36, 18, 3, 0, 0, 0, 0, 0, 16, 14, 1, 0, 0,
  0, 128, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 232, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 62, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 62, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameWave0(ox, oy) {
  korg.display.bitmap(P_WAVE0, ox + 5, oy + 4, 39);
}

const P_WAVE1 = [
  0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 224, 224,
  0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 0, 128, 128, 128, 0, 0, 0, 0, 0, 0, 98, 26, 10, 230, 229, 229, 9, 25, 97, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 223, 63, 31, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 18, 36, 36, 36, 18, 3, 0, 0, 0, 0, 32, 0, 32, 16, 12, 2, 1, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 232, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 62, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 62, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameWave1(ox, oy) {
  korg.display.bitmap(P_WAVE1, ox + 5, oy + 4, 44);
}

const P_WALK = [
  0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 2, 0, 128, 128, 128, 0, 0, 0, 0, 0, 0, 98, 26, 10, 230, 229, 229, 9, 25, 97, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 18, 36, 36, 36, 18, 3, 0, 0, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0,
  16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 8, 16, 16,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 192, 32, 24, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 32, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 48, 48, 48, 48, 60, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 51, 60, 48, 48, 48, 0, 0, 0, 0, 0, 0
];

function frameWalk(ox, oy) {
  korg.display.bitmap(P_WALK, ox + 9, oy + 4, 37);
}

const P_FLAIL_BASE = [
  0, 0, 0, 128, 0, 32, 0, 0, 16, 8, 8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 1, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 64, 0, 128, 0, 0, 0,
  240, 14, 0, 0, 0, 0, 0, 0, 0, 0, 5, 32, 32, 32, 32, 32, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 4, 248,
  0, 0, 48, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 48, 0, 0,
  0, 0, 0, 0, 0, 4, 0, 0, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlailBase(ox, oy) {
  korg.display.bitmap(P_FLAIL_BASE, ox + 10, oy + 8, 31);
}

function frameFlailCore(ox, oy) {
  korg.display.bitmap(P_FLAIL_BASE, ox + 10, oy + 8, 31);
}

const P_FLAIL0 = [
  0, 0, 0, 0, 0, 0, 0, 128, 224, 32, 48, 24, 136, 12, 4, 12, 136, 152, 144, 176, 224, 0, 0, 0, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  8, 48, 192, 0, 0, 128, 238, 119, 12, 4, 178, 15, 4, 114, 114, 98, 8, 24, 96, 0, 0, 0, 128, 97, 1, 33, 33, 33, 64, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 64, 32,
  0, 0, 0, 3, 132, 8, 63, 30, 48, 32, 53, 105, 82, 82, 130, 16, 43, 0, 0, 0, 0, 3, 172, 136, 35, 167, 167, 144, 216, 115, 28, 48, 64, 128, 0, 96, 24, 4, 0, 1, 0, 0,
  0, 0, 0, 0, 0, 248, 128, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 3, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 128, 240, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 16, 112, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 112, 8, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 128, 96, 17, 15, 2, 4, 4, 28, 16, 16, 0, 0, 0, 0, 0, 32, 32, 60, 70, 131, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 12, 12, 12, 12, 14, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 103, 120, 96, 96, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlail0(ox, oy) {
  korg.display.bitmap(P_FLAIL0, ox + 6, oy + 4, 42);
}

const P_FLAIL1 = [
  0, 128, 192, 96, 48, 24, 8, 8, 136, 152, 16, 176, 32, 0, 0, 0, 0, 0, 0, 0, 64, 64, 64, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 96, 16,
  243, 255, 112, 24, 192, 26, 11, 228, 197, 228, 8, 24, 224, 0, 0, 1, 113, 141, 129, 57, 57, 56, 2, 198, 56, 128, 128, 0, 0, 0, 0, 0, 0, 96, 8, 6, 1, 0, 0,
  1, 7, 126, 0, 64, 65, 106, 208, 164, 164, 164, 83, 0, 0, 0, 0, 0, 0, 149, 137, 233, 41, 57, 20, 26, 15, 1, 1, 2, 2, 12, 84, 3, 0, 0, 0, 0, 0, 0,
  0, 0, 248, 128, 0, 0, 0, 0, 0, 0, 1, 3, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 112, 92, 0, 0, 0, 0, 0, 0, 0,
  8, 6, 1, 0, 0, 0, 12, 24, 96, 192, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 224, 48, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 6, 4, 4, 4, 16, 96, 128, 0, 0, 8, 216, 60, 4, 6, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 27, 28, 24, 28, 13, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlail1(ox, oy) {
  korg.display.bitmap(P_FLAIL1, ox + 8, oy + 5, 39);
}

const P_FLAIL2 = [
  128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 96, 48, 24, 12, 70, 66, 66, 34, 6, 4, 12, 56, 32, 0, 64, 64, 32, 32, 32, 32, 16, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 3, 4, 8, 48, 64, 128, 0, 0, 252, 255, 28, 2, 48, 142, 135, 33, 57, 57, 2, 134, 56, 0, 0, 0, 224, 24, 8, 100, 228, 228, 0, 8, 224, 192, 128, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 1, 0, 2, 12, 25, 70, 28, 16, 16, 24, 49, 41, 41, 232, 128, 8, 0, 0, 0, 0, 0, 235, 82, 100, 36, 48, 27, 15, 0, 0, 3, 4, 4, 8, 16, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 28, 112, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 28, 4, 2, 4, 8,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 14, 8, 112, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 96, 48, 26, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 96, 25, 7, 1, 3, 2, 2, 0, 0, 0, 0, 0, 4, 4, 4, 4, 7, 24, 48, 192, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 24, 24, 28, 13, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 6, 7, 6, 6, 0, 0, 0, 0
];

function frameFlail2(ox, oy) {
  korg.display.bitmap(P_FLAIL2, ox, oy + 6, 44);
}

const P_FLAIL3 = [
  0, 48, 200, 112, 16, 24, 12, 4, 132, 6, 2, 66, 70, 76, 72, 120, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 116, 251, 134, 2, 25, 197, 131, 58, 57, 57, 129, 132, 116, 0, 0, 0, 96, 25, 10, 226, 230, 229, 5, 25, 194, 2, 0, 0, 0, 0, 0, 0, 0, 128, 96, 0, 24, 4, 2,
  128, 31, 7, 13, 8, 24, 52, 40, 41, 193, 145, 20, 0, 0, 0, 0, 0, 16, 211, 162, 164, 228, 80, 98, 48, 29, 24, 32, 64, 0, 32, 24, 0, 6, 1, 0, 0, 0, 0, 0,
  124, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 120, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 24, 48, 192, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 192, 112, 16, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 1, 13, 246, 4, 12, 8, 8, 0, 0, 0, 192, 48, 16, 12, 6, 3, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 12, 12, 12, 14, 13, 0, 0, 0, 0, 24, 24, 30, 59, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlail3(ox, oy) {
  korg.display.bitmap(P_FLAIL3, ox + 11, oy + 5, 40);
}

const P_BACK0 = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 224, 176, 144, 152, 136, 8, 8, 24, 16, 48, 224, 128, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 225, 25, 9, 229, 229, 230, 10, 26, 226, 0, 0, 0, 224, 24, 8, 229, 229, 229, 11, 30, 228, 12, 57, 255, 248, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 128, 224, 48, 24, 12, 14, 56, 107, 82, 228, 164, 164, 82, 43, 0, 0, 0, 0, 0, 43, 82, 164, 164, 164, 210, 107, 64, 96, 56, 255, 131, 0, 0, 0, 0, 0,
  128, 64, 64, 32, 16, 63, 224, 128, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 3, 2, 2, 2, 2, 2, 2, 2, 3, 0, 0, 0, 0, 0, 0, 128, 224, 63, 32, 32, 64, 128, 0,
  0, 0, 0, 0, 0, 0, 0, 3, 14, 56, 224, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 224, 56, 14, 3, 0, 0, 0, 0, 0, 0, 1,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 14, 248, 16, 16, 16, 16, 16, 16, 16, 16, 24, 8, 8, 252, 6, 3, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 62, 49, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 49, 62, 48, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameBack0(ox, oy) {
  korg.display.bitmap(P_BACK0, ox + 5, oy + 4, 41);
}

const P_BACK1 = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 224, 176, 144, 152, 136, 8, 8, 24, 16, 48, 96, 192, 128, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 225, 25, 9, 229, 229, 230, 10, 26, 226, 0, 0, 0, 224, 24, 8, 229, 229, 229, 11, 30, 228, 12, 56, 255, 248, 0, 0, 0,
  0, 0, 0, 0, 0, 128, 224, 48, 24, 12, 14, 56, 107, 82, 228, 164, 164, 82, 43, 0, 0, 0, 0, 0, 43, 82, 164, 164, 164, 210, 107, 64, 96, 56, 255, 131, 0, 0, 0,
  16, 16, 8, 8, 8, 63, 224, 128, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 3, 2, 2, 2, 2, 2, 2, 2, 3, 0, 0, 0, 0, 0, 0, 128, 224, 63, 16, 32, 64,
  0, 0, 0, 0, 0, 0, 0, 3, 14, 56, 224, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 224, 56, 14, 3, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 193, 35, 30, 16, 16, 16, 16, 16, 16, 16, 16, 16, 24, 8, 12, 4, 30, 35, 193, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 48, 48, 48, 60, 51, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 60, 48, 48, 48, 48, 0, 0, 0
];

function frameBack1(ox, oy) {
  korg.display.bitmap(P_BACK1, ox + 5, oy + 4, 39);
}

const DX_MAX = 127 - WALK_RIGHT;
const DX_MID = 24;
const WALK_MS = 120;
const STEP_MS = 240;
const BRISK_MS = 70;
const LISTEN_MS = 2800;
const TALK_MS = 3500;
const TALK_FIRST = 8000;
const TALK_GAP = 8000;
const TALK_SPREAD = 8000;
const B_LISTEN = 9;
const ANGRY_MS = 1200;
const HAPPY_MS = 1600;
const STROKE = 120;
const POSE = [0, 2, 1, 3, 2, 0, 3, 1];
const WAVE_DELAY_MS = 1000;
const WAVE_STEP_MS = 220;
const WAVE_MS = 1760;

let isOpen = 0;
let openMs = 0;
let lastSig = -1;
let lastFrame = -1;
let lastBubble = 0;
let lastPos = -1;
let seed = 4711;
let twitchUntil = 0;
let nextTwitch = 0;
let reactKind = 0;
let reactUntil = 0;
let flail = 0;
let waved = 0;
let waveAt = 0;
let posX = 0;
let posY = 0;
let dir = 1;
let walkAt = 0;
let holdUntil = 0;
let mode = 0;
let listenAt = 0;
let nextTalk = 0;
let wantTalk = 0;
let talkKind = 0;
let talkNo = 0;
let talkSide = 0;
let playing = korg.read.transport() == 1 ? 1 : 0;
let playedOnce = 0;
let firstPlayAt = 0;
let bestBpm = 0;
let bestCount = 0;
let touching = 0;
let near = 0;
let moved = 0;
let lastX = 0;
let lastY = 0;
const beats = new Array(256);

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function abs(v) {
  return v < 0 ? -v : v;
}

function numLen(n) {
  let d = 1;
  while (n >= 10) {
    n = n / 10;
    d += 1;
  }
  return d;
}

function bubbleBox(l, r) {
  const w = r - l + 1;
  korg.display.rect(l, 8, w, 1);
  korg.display.rect(l, 41, w, 1);
  korg.display.rect(l, 8, 1, 34);
  korg.display.rect(r, 8, 1, 34);
}

// The tail points at him: to the left of a box on his right, to the right of a box on his left.
function tailLeft(l) {
  korg.display.pixel(l - 1, 22, 1);
  korg.display.rect(l - 2, 23, 2, 1);
  korg.display.rect(l - 3, 24, 3, 1);
  korg.display.rect(l - 2, 25, 2, 1);
  korg.display.pixel(l - 1, 26, 1);
}

function tailRight(r) {
  korg.display.pixel(r + 1, 22, 1);
  korg.display.rect(r + 1, 23, 2, 1);
  korg.display.rect(r + 1, 24, 3, 1);
  korg.display.rect(r + 1, 25, 2, 1);
  korg.display.pixel(r + 1, 26, 1);
}

function drawBubble(kind, side) {
  let l = 53;
  let r = 127;
  if (kind == B_LISTEN) l = 73;
  if (side) {
    l = 0;
    r = 74;
  }
  bubbleBox(l, r);
  if (side) tailRight(r);
  else tailLeft(l);
  const x = l + 3;
  if (kind == B_LISTEN) {
    korg.display.text("ich hoer", x, 11);
    korg.display.text("mir das", x, 22);
    korg.display.text("kurz an", x, 33);
  } else if (kind == 1) {
    korg.display.text("yo", x, 14);
    korg.display.text("na du?", x, 26);
  } else if (kind == 2) {
    if (bestCount > 0) {
      korg.display.text("Lieblings-", x, 12);
      korg.display.textNumber("tempo ", bestBpm, x, 26);
    } else {
      korg.display.text("mein Tempo", x, 12);
      korg.display.text("ist 150 bpm", x, 26);
    }
  } else if (kind == 3) {
    const t = korg.millis() - (playedOnce ? firstPlayAt : 0);
    korg.display.text(playedOnce ? "Spielt seit" : "Laeuft seit", x, 12);
    if (t >= 60000) {
      const m = t / 60000;
      korg.display.number(m, x, 26);
      korg.display.text("min", x + 6 + numLen(m) * 6, 26);
    } else {
      const s = t / 1000;
      korg.display.number(s, x, 26);
      korg.display.text("sek", x + 6 + numLen(s) * 6, 26);
    }
  } else if (kind == 4) {
    korg.display.text("Blech ist", x, 14);
    korg.display.text("mein Ding", x, 26);
  } else if (kind == 5) {
    korg.display.text("kein Mund,", x, 14);
    korg.display.text("kein Problem", x, 26);
  } else if (kind == 6) {
    korg.display.text("bisschen", x, 14);
    korg.display.text("mehr Bass?", x, 26);
  } else if (kind == 7) {
    korg.display.text("nicht so", x, 14);
    korg.display.text("doll tippen", x, 26);
  } else {
    korg.display.text("Schranz", x, 14);
    korg.display.text("ist Liebe", x, 26);
  }
}

function drawFrame(f, last, ox, oy) {
  if (f == 0 || f == 1 || f == 2 || f == 3 || f == 8 || f == 9 || f == 10) {
    if (last == 0 || last == 1 || last == 2 || last == 3 || last == 8 || last == 9 || last == 10) {
      korg.display.clearRect(ox + 5, oy + 9, 44, 49);
      frameStandCore(ox, oy);
    } else {
      korg.display.clear();
      frameStandBase(ox, oy);
    }
    if (f == 0) frameIdle(ox, oy);
    else if (f == 1) frameTwitch(ox, oy);
    else if (f == 2) frameAngry(ox, oy);
    else if (f == 3) frameHappy(ox, oy);
    else if (f == 8) frameWave0(ox, oy);
    else if (f == 9) frameWave1(ox, oy);
    else if (f == 10) frameWalk(ox, oy);
  } else if (f == 4 || f == 5 || f == 6 || f == 7) {
    if (last == 4 || last == 5 || last == 6 || last == 7) {
      korg.display.clearRect(ox, oy + 6, 51, 53);
      frameFlailCore(ox, oy);
    } else {
      korg.display.clear();
      frameFlailBase(ox, oy);
    }
    if (f == 4) frameFlail0(ox, oy);
    else if (f == 5) frameFlail1(ox, oy);
    else if (f == 6) frameFlail2(ox, oy);
    else if (f == 7) frameFlail3(ox, oy);
  } else {
    korg.display.clear();
    if (f == 11) frameBack0(ox, oy);
    else if (f == 12) frameBack1(ox, oy);
  }
}

function standing(now) {
  return now < twitchUntil ? F_TWITCH : F_IDLE;
}

// One step towards target every gap ms, px pixels at a time; 1 once he is there.
function move(now, target, gap, px) {
  if (posX == target) return 1;
  dir = target > posX ? 1 : -1;
  if (now - walkAt >= gap) {
    walkAt = now;
    if (abs(target - posX) <= px) posX = target;
    else posX += dir * px;
  }
  return posX == target ? 1 : 0;
}

function startTalk(now, side) {
  wantTalk = 0;
  talkSide = side;
  talkNo = talkNo % 8 + 1;
  talkKind = talkNo;
  holdUntil = now + TALK_MS;
  nextTalk = holdUntil + TALK_GAP + rnd() % TALK_SPREAD;
}

// The walk cycle: the calm and the walk picture in turn every STEP_MS (as on the Discord page), mirrored when he goes left.
// The walk picture sits one row lower, which makes the step.
function walking(now) {
  const pose = (now / STEP_MS) & 1;
  posY = pose;
  if (dir < 0) return F_BACK + pose;
  return pose ? F_WALK : F_IDLE;
}

// Which picture belongs to the moment, and where he is: a reaction first, then the play states (to the middle,
// listening, dancing), then the wave (once per landing, WAVE_DELAY_MS after it, the hand swings every WAVE_STEP_MS),
// then the walk (the pictures alternate, mirrored to the left) with its stops at the edges, the twitch, standing.
function pick(now) {
  if (!playing) mode = 0;
  else if (mode == 0) {
    mode = 1;
    waved = 1;
    talkKind = 0;
    wantTalk = 0;
    holdUntil = 0;
  }
  posY = 0;
  if (reactKind != 0 && now < reactUntil) {
    walkAt = now;
    return reactKind == 1 ? F_ANGRY : F_HAPPY;
  }
  if (mode == 1) {
    if (move(now, DX_MID, BRISK_MS, 2)) {
      mode = 2;
      listenAt = now;
      talkSide = 0;
      return standing(now);
    }
    return walking(now);
  }
  if (mode == 2 && now - listenAt >= LISTEN_MS) mode = 3;
  if (mode == 3) return F_FLAIL + flail;
  if (mode == 2) return F_IDLE;
  if (!waved && now - openMs >= WAVE_DELAY_MS) {
    waved = 1;
    waveAt = now;
  }
  if (waved && now - waveAt < WAVE_MS) return F_WAVE + (((now - waveAt) / WAVE_STEP_MS) & 1);
  if (!waved || now < holdUntil) return standing(now);
  if (now >= nextTalk) wantTalk = 1;
  if (move(now, dir > 0 ? DX_MAX : 0, WALK_MS, 1)) {
    talkKind = 0;
    if (wantTalk) startTalk(now, dir > 0 ? 1 : 0);
    else holdUntil = now + 1000;
    dir = 0 - dir;
    return standing(now);
  }
  return walking(now);
}

function bubbleAt(now) {
  if (mode == 2 && now - listenAt < LISTEN_MS) return B_LISTEN;
  if (mode == 0 && talkKind > 0 && now < holdUntil) return talkKind;
  return 0;
}

korg.onEvent("open", () => {
  isOpen = 1;
  openMs = korg.millis();
  nextTwitch = openMs + 1500;
  nextTalk = openMs + TALK_FIRST + rnd() % TALK_SPREAD;
  twitchUntil = 0;
  reactKind = 0;
  waved = playing;
  waveAt = 0;
  posX = 0;
  dir = 1;
  holdUntil = 0;
  talkKind = 0;
  wantTalk = 0;
  mode = 0;
  lastSig = -1;
  lastFrame = -1;
});

korg.onEvent("close", () => {
  isOpen = 0;
  touching = 0;
});

korg.onEvent("frame", () => {
  const now = korg.millis();
  if (now >= nextTwitch) {
    twitchUntil = now + 160;
    nextTwitch = now + 1500 + rnd() % 2500;
  }
  const f = pick(now);
  const b = bubbleAt(now);
  const pos = posX * 2 + posY;
  const sig = f + b * 16 + (b > 0 ? talkSide * 256 : 0) + pos * 512;
  if (sig != lastSig) {
    // a bubble that was there has to be wiped, so only a frame that stood alone, in the same place, is changed in place
    drawFrame(f, lastBubble == 0 && lastPos == pos ? lastFrame : -1, posX, posY);
    if (b > 0) drawBubble(b, talkSide);
    lastSig = sig;
    lastFrame = f;
    lastBubble = b;
    lastPos = pos;
  }
});

korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TOUCHPAD) {
    touching = 1;
    near = 0;
    moved = 0;
  }
});

korg.onEvent("touch", (x, y, first) => {
  if (!touching || !isOpen) return;
  if (first) {
    const px = x / 8;
    near = px >= FIG_LEFT + posX - 4 && px <= FIG_RIGHT + posX + 4 ? 1 : 0;
  } else {
    moved += abs(x - lastX) + abs(y - lastY);
  }
  lastX = x;
  lastY = y;
  if (near && moved >= STROKE) {
    reactKind = 2;
    reactUntil = korg.millis() + HAPPY_MS;
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.TOUCHPAD && touching) {
    touching = 0;
    if (isOpen && near && moved < STROKE) {
      reactKind = 1;
      reactUntil = korg.millis() + ANGRY_MS;
    }
  }
});

korg.onEvent("play", () => {
  if (!playing) {
    playing = 1;
    if (!playedOnce) {
      playedOnce = 1;
      firstPlayAt = korg.millis();
    }
  }
});

korg.onEvent("stop", () => {
  if (!playing) return;
  playing = 0;
  nextTalk = korg.millis() + TALK_GAP;
  lastSig = -1;
  lastFrame = -1;
});

korg.onEvent("step", (s) => {
  if ((s & 1) == 0) flail = POSE[(s >> 1) & 7];
});

korg.onEvent("beat", () => {
  const bpm = (korg.read.tempo() + 5) / 10;
  if (bpm < 256) {
    beats[bpm] += 1;
    if (beats[bpm] > bestCount) {
      bestCount = beats[bpm];
      bestBpm = bpm;
    }
  }
});
