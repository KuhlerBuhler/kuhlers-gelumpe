import { FONT, FONT_FIRST, GLYPH_WIDTH, GLYPH_HEIGHT, ADVANCE, fontByte } from "../../data/script/font.mjs";

/**
 * The 128 x 64 display as korg.display.* draws it, clipped and never wrapped.
 * Buffer layout is the device's display RAM (8 pages, bit 0 the top row). The
 * ARM runtime draws the same way from the same font table.
 */
export const WIDTH = 128;
export const HEIGHT = 64;
export { GLYPH_WIDTH, GLYPH_HEIGHT, ADVANCE };

/** Five column bytes of a character; the question mark for anything the font does not have. */
export function glyph(code) {
  return FONT[code - FONT_FIRST] ?? FONT["?".charCodeAt(0) - FONT_FIRST];
}

export class Display {
  constructor() {
    this.bytes = new Uint8Array((WIDTH * HEIGHT) / 8);
  }

  clear() {
    this.bytes.fill(0);
  }

  pixel(x, y, on = 1) {
    if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 || x >= WIDTH || y >= HEIGHT) return;
    const at = (y >> 3) * WIDTH + x;
    if (on) this.bytes[at] |= 1 << (y & 7);
    else this.bytes[at] &= ~(1 << (y & 7));
  }

  get(x, y) {
    if (x < 0 || y < 0 || x >= WIDTH || y >= HEIGHT) return 0;
    return (this.bytes[(y >> 3) * WIDTH + x] >> (y & 7)) & 1;
  }

  #fill(x, y, width, height, on) {
    const x1 = Math.min(WIDTH, x + width);
    const y1 = Math.min(HEIGHT, y + height);
    for (let yy = Math.max(0, y); yy < y1; yy++) for (let xx = Math.max(0, x); xx < x1; xx++) this.pixel(xx, yy, on);
  }

  rect(x, y, width, height) { this.#fill(x, y, width, height, 1); }

  clearRect(x, y, width, height) { this.#fill(x, y, width, height, 0); }

  /** Draw text with its top left corner at (x, y). Characters past the right edge are cut off, there is no wrap. */
  text(text, x, y) {
    let cursor = x;
    for (const char of String(text)) {
      if (cursor >= WIDTH) break;
      const columns = glyph(fontByte(char));
      for (let column = 0; column < GLYPH_WIDTH; column++) {
        for (let row = 0; row < GLYPH_HEIGHT; row++) if ((columns[column] >> row) & 1) this.pixel(cursor + column, y + row, 1);
      }
      cursor += ADVANCE;
    }
  }

  number(value, x, y) { this.text(String(value), x, y); }

  /** Text, then the number right after its last character (the number is cut off at the edge like any text). */
  textNumber(text, value, x, y) {
    this.text(text, x, y);
    this.number(value, x + ADVANCE * [...String(text)].length, y);
  }

  /**
   * Lit pixels of a picture whose slots are the display's own columns of 8 pixels (contract: BITMAP layout): a band is `width`
   * slots, bit 0 the top pixel, the bands follow from the top. (x, y) is where the top left corner goes and may lie beyond an
   * edge; only the part on the display is drawn, nothing is erased.
   */
  bitmap(slots, x, y, width) {
    const bands = Math.floor(slots.length / width);
    for (let band = 0; band < bands; band++) {
      for (let column = 0; column < width; column++) {
        const bits = slots[band * width + column] & 0xFF;
        for (let bit = 0; bit < 8; bit++) if ((bits >> bit) & 1) this.pixel(x + column, y + band * 8 + bit, 1);
      }
    }
  }

  /** 64 strings of 128 characters, `#` for a lit pixel. */
  rows() {
    return Array.from({ length: HEIGHT }, (_, y) => Array.from({ length: WIDTH }, (_, x) => (this.get(x, y) ? "#" : ".")).join(""));
  }
}

/** Firmware popup outline and content clipping, as a display picture for the script simulator. */
export function popupDisplay(content, base = null) {
  const popup = new Display();
  if (base) popup.bytes.set(base);
  for (let x = 1; x <= 126; x++) for (let y = 12; y <= 49; y++) popup.pixel(x, y, 0);
  for (let x = 1; x <= 126; x++) {
    popup.pixel(x, 13);
    popup.pixel(x, 48);
  }
  for (let y = 14; y <= 47; y++) {
    popup.pixel(1, y);
    popup.pixel(126, y);
  }
  for (let x = 3; x <= 125; x += 2) popup.pixel(x, 49);
  for (let y = 14; y <= 47; y++) {
    for (let x = 2; x <= 125; x++) if (content.get(x, y)) popup.pixel(x, y);
  }
  return popup;
}

/** The screen a faulted script leaves: its name, the source line and the error name, one text row each. */
export function drawFault(display, script, line, errorName) {
  display.clear();
  display.text(script, 4, 2);
  display.text("Line", 4, 12);
  display.number(line, 40, 12);
  display.text(errorName, 4, 22);
}
