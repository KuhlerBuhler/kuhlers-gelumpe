/** Icons drawn for this page, 24 x 24, in the colour of the text around them. */
const NS = "http://www.w3.org/2000/svg";

/** Transport symbols are filled shapes, as printed on the device. */
const SOLID = new Set(["rec", "stop", "play", "pause"]);

const PATHS = {
  chevronDown: ["m6 9 6 6 6-6"],
  x: ["M18 6 6 18", "m6 6 12 12"],
  slidersHorizontal: ["M21 4h-7", "M10 4H3", "M21 12h-9", "M8 12H3", "M21 20h-5", "M12 20H3", "M14 2v4", "M8 10v4", "M16 18v4"],
  grid: ["M3 3h7v7H3Z", "M14 3h7v7h-7Z", "M3 14h7v7H3Z", "M14 14h7v7h-7Z"],
  code: ["m16 18 6-6-6-6", "m8 6-6 6 6 6"],
  terminal: ["m4 17 6-6-6-6", "M12 19h8"],
  book: ["M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5Z", "M4 19.5V21h16v-4"],
  eye: ["M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z", "M9 12a3 3 0 1 0 6 0 3 3 0 1 0-6 0"],
  download: ["M12 3v12", "m7 10 5 5 5-5", "M5 21h14"],
  popout: ["M14 4h6v6", "M20 4l-9 9", "M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"],
  usb: ["M12 2v14", "m9 5 3-3 3 3", "M8 9v3l4 3", "M16 7v4l-4 3", "M10 19a2 2 0 1 0 4 0 2 2 0 1 0-4 0"],
  power: ["M12 3v8", "M6.3 6.3a8 8 0 1 0 11.4 0"],
  rec: ["M12 5a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z"],
  stop: ["M7 7h10v10H7Z"],
  play: ["M8 5v14l11-7Z"],
  pause: ["M6 5h4v14H6Z", "M14 5h4v14h-4Z"],
  trash: ["M3 6h18", "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6", "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"],
  grip: ["M9 5h.01", "M9 12h.01", "M9 19h.01", "M15 5h.01", "M15 12h.01", "M15 19h.01"],
  folder: ["M3 6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"],
  pencil: ["M21.2 6.8a1 1 0 0 0-4-4L3.8 16.2a2 2 0 0 0-.5.8l-1.3 4.4a.5.5 0 0 0 .6.6l4.4-1.3a2 2 0 0 0 .8-.5Z", "m15 5 4 4"],
  swap: ["m8 3-4 4 4 4", "M4 7h16", "m16 21 4-4-4-4", "M20 17H4"],
  image: ["M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z", "M9 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z", "m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"],
  film: ["M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z", "M7 3v18", "M17 3v18", "M3 7.5h4", "M3 12h18", "M3 16.5h4", "M17 7.5h4", "M17 16.5h4"],
  plus: ["M12 5v14", "M5 12h14"],
  chevronLeft: ["m15 18-6-6 6-6"],
  chevronRight: ["m9 18 6-6-6-6"],
  eraser: ["m7 21-4.3-4.3a1 1 0 0 1 0-1.4l10-10a1 1 0 0 1 1.4 0l5.6 5.6a1 1 0 0 1 0 1.4L13 21", "M22 21H7", "m5 11 9 9"],
  sliders: ["M4 21v-7", "M4 10V3", "M12 21v-9", "M12 8V3", "M20 21v-5", "M20 12V3", "M2 14h4", "M10 8h4", "M18 16h4"],
};

export function icon(name) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", `cee-icon lucide lucide-${name.replace(/[A-Z]/g, c => `-${c.toLowerCase()}`)}${SOLID.has(name) ? " cee-icon-solid" : ""}`);
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const d of PATHS[name]) {
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}
