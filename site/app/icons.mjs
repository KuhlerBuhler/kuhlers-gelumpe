/** Icons drawn for this page, 24 x 24, in the colour of the text around them. */
const NS = "http://www.w3.org/2000/svg";

/** Transport symbols are filled shapes, as printed on the device. */
const SOLID = new Set(["rec", "stop", "play"]);

const PATHS = {
  chevronDown: ["m6 9 6 6 6-6"],
  x: ["M18 6 6 18", "m6 6 12 12"],
  settings: ["M20 7h-9", "M14 17H5", "M14 17a3 3 0 1 0 6 0 3 3 0 1 0-6 0", "M4 7a3 3 0 1 0 6 0 3 3 0 1 0-6 0"],
  power: ["M12 3v8", "M6.3 6.3a8 8 0 1 0 11.4 0"],
  rec: ["M12 5a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z"],
  stop: ["M7 7h10v10H7Z"],
  play: ["M8 5v14l11-7Z"],
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
