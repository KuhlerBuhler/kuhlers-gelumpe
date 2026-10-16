// BLECH theme art: our own glyphs and icons for the device display, drawn as text like the
// README banner font (tools/readme-banner.mjs). "#" is ink, "." is empty, top row first. A glyph
// is an array of rows; a leading number says how many rows the last row lies below the baseline
// (g, p, q, y, j: -2). Leading empty columns become the glyph's x offset. null keeps the
// firmware's glyph. tools/patch/blech_theme.mjs checks every drawing against the firmware's boxes.
//
// Style: sheet metal and terror eyes. Corners are cut, not rounded; the capital O is an eye with
// a slit pupil and the zero carries the pupil, so every number has an eye in it; the A is peaked;
// the capital Q drips. Each font keeps the rows and the advance widths of the font it replaces.
import font0 from "./blech_theme_art/font0.mjs";
import font1 from "./blech_theme_art/font1.mjs";
import font2 from "./blech_theme_art/font2.mjs";
import font3 from "./blech_theme_art/font3.mjs";
import icons from "./blech_theme_art/icons.mjs";

export const FONT_ART = { 0: font0, 1: font1, 2: font2, 3: font3 };
export const ICON_ART = icons;
