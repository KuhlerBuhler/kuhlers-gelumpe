/**
 * A recorded input run for Blechy: a stray touch, a tap near him, a stroke, a long stretch of walking and talking
 * (every line of his rotation, with no PLAY yet), a PLAY with a tap on the way to the middle, a long play with a stop,
 * more walking and talking (now with a favourite tempo and a play time in minutes), a second stop that changes nothing,
 * a PLAY that starts and stops while he is still walking, and EXIT. In the format the probe takes: `{ frame, event, args }`,
 * 40 ms to a frame.
 */
const TOUCHPAD = 34;
const PLAY = 2;
const STOP = 1;
const EXIT = 13;

const input = (frame, event, ...args) => ({ frame, event, args });
const tap = (frame, x, y) => [input(frame, "buttonPress", TOUCHPAD), input(frame, "touch", x, y), input(frame + 3, "buttonRelease", TOUCHPAD)];
const stroke = (frame, y) => [
  input(frame, "buttonPress", TOUCHPAD), input(frame, "touch", 100, y), input(frame + 1, "touch", 170, y),
  input(frame + 2, "touch", 240, y + 20), input(frame + 3, "touch", 300, y), input(frame + 50, "buttonRelease", TOUCHPAD),
];

export function blechyInputs() {
  return [
    input(3, "touch", 100, 100),
    ...tap(10, 160, 500),
    ...tap(40, 900, 500),
    ...stroke(70, 500),
    input(5000, "buttonPress", PLAY),
    ...tap(5030, 500, 500),
    input(7500, "buttonPress", STOP),
    input(7600, "buttonPress", STOP),
    input(14000, "buttonPress", PLAY),
    input(14100, "buttonPress", STOP),
    input(14200, "buttonPress", PLAY),
    input(14400, "buttonPress", STOP),
    input(14500, "buttonPress", EXIT),
  ];
}
