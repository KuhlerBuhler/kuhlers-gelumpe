/**
 * The 5 x 7 font of the script display, one row of five column bytes per
 * character from 0x20 to 0x7e (bit 0 is the top row), then ä, ö and ü as 0x7f to
 * 0x81. The ARM runtime and the browser model draw from this one table. A
 * preview-quality font of our own, not the firmware's.
 */
export const FONT_FIRST = 0x20;
export const FONT_LAST = 0x81;
export const GLYPH_WIDTH = 5;
export const GLYPH_HEIGHT = 7;
export const ADVANCE = 6;

/** The umlauts behind "~": in a plugin string each is the one byte here, so a text slot keeps one byte per character. */
export const UMLAUTS = Object.freeze({ "ä": 0x7f, "ö": 0x80, "ü": 0x81 });

/** The byte a character of a string is stored and drawn as. */
export const fontByte = char => UMLAUTS[char] ?? char.charCodeAt(0);

const ROWS = [
  "0000000000", "00005f0000", "0007000700", "147f147f14", "242a7f2a12", "2313086462", "3649552250", "0005030000",
  "001c224100", "0041221c00", "14083e0814", "08083e0808", "0050300000", "0808080808", "0060600000", "2010080402",
  "3e5149453e", "00427f4000", "4261514946", "2141454b31", "1814127f10", "2745454539", "3c4a494930", "0171090503",
  "3649494936", "064949291e", "0036360000", "0056360000", "0814224100", "1414141414", "0041221408", "0201510906",
  "324979413e", "7e1111117e", "7f49494936", "3e41414122", "7f4141221c", "7f49494941", "7f09090901", "3e4149497a",
  "7f0808087f", "00417f4100", "2040413f01", "7f08142241", "7f40404040", "7f020c027f", "7f0408107f", "3e4141413e",
  "7f09090906", "3e4151215e", "7f09192946", "4649494931", "01017f0101", "3f4040403f", "1f2040201f", "3f4038403f",
  "6314081463", "0708700807", "6151494543", "007f414100", "0204081020", "0041417f00", "0402010204", "4040404040",
  "0001020400", "2054545478", "7f48444438", "3844444420", "384444487f", "3854545418", "087e090102", "081454543c",
  "7f08040478", "00447d4000", "2040443d00", "007f102844", "00417f4000", "7c04180478", "7c08040478", "3844444438",
  "7c14141408", "081414187c", "7c08040408", "4854545420", "043f444020", "3c4040207c", "1c2040201c", "3c4030403c",
  "4428102844", "0c5050503c", "4464544c44", "0008364100", "00007f0000", "0041360800", "1008081008",
  "2055545578", "3845444538", "3c4140217c",
];

export const FONT = Object.freeze(ROWS.map(row => Uint8Array.from(row.match(/../g), pair => parseInt(pair, 16))));
