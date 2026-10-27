/**
 * Blechy's frames. The pictures are the 56 x 56 PNG sprites in assets/blechy/sprites (black is a lit pixel, made by
 * tools/art/make_blechy.py); a frame here names a sprite and where its top left corner sits on the 128 x 64 display
 * (what lies beyond an edge is cut off). To use other pictures, change the PNGs, or point a frame at another sprite,
 * and run `node tools/blechy-build.mjs`: it makes the plugin source from this table, nothing else needs to change.
 *
 * idle is the standing picture, the calm sprite. twitch is the idle sprite (brow up, one eye lower) that shows now
 * and then. angry (tap) and happy (stroke) are the idle pose with another face. flail0 to flail3 are the four
 * terror sprites, one per step. listen is the standing picture again, beside the speech bubble. wave0 and wave1 are
 * the greeting, the calm pose with the right arm raised and the hand leaning one way and the other.
 *
 * Frames with the same family are the same figure with a changed face: the build draws what they share once and
 * redraws only the part where they differ when one replaces another. A frame without a family is drawn whole.
 *
 * walk is the walking picture, one of the stand family. back0 and back1 are the calm and the walk picture mirrored left to
 * right for when he walks to the left (the app mirrors him the same way); the axis is the middle of the box around both
 * pictures, so a mirrored picture lies in the same box and the walk limits stay the same. The walk alternates the calm and
 * the walk picture (idle or back0, walk or back1) every 240 ms, as the Discord page does. flail0 to flail3 are a family of their own: what the four share is drawn
 * once, which also keeps his block inside its 16 KiB. Every picture is drawn at its table position plus an offset the logic
 * passes (ox, oy), which is how he walks across the display with the same bitmaps.
 */
export const SPRITE_DIR = "assets/blechy/sprites/";

const STAND = { x: -3, y: 4 };
const stand = sprite => ({ sprite, ...STAND, family: "stand" });
const alone = sprite => ({ sprite, ...STAND });
const mirrored = sprite => ({ sprite, ...STAND, mirror: ["calm", "walk"] });
const flailing = sprite => ({ sprite, ...STAND, family: "flail" });

export const FRAMES = Object.freeze({
  idle: stand("calm"),
  twitch: stand("idle"),
  angry: stand("angry"),
  happy: stand("happy"),
  flail0: flailing("terror-1"),
  flail1: flailing("terror-2"),
  flail2: flailing("terror-3"),
  flail3: flailing("terror-4"),
  wave0: stand("wave-1"),
  wave1: stand("wave-2"),
  walk: stand("walk"),
  back0: mirrored("calm"),
  back1: mirrored("walk"),
});

export const FRAME_ORDER = Object.freeze(Object.keys(FRAMES));
