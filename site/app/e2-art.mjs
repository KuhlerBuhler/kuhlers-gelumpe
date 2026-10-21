/** A small Electribe 2 drawn from above (SVG), its body in the colour `body`: the cards of the Rettung page. */
const NS = "http://www.w3.org/2000/svg";

export function e2Art(body, label) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 160 80");
  svg.setAttribute("class", "cee-e2-art");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label);
  const pads = Array.from({ length: 16 }, (_, i) => `<rect x="${10 + (i % 8) * 13}" y="${i < 8 ? 50 : 62}" width="10" height="10" rx="1.5" class="cee-e2-art-pad"/>`).join("");
  const knobs = [0, 1, 2, 3, 4].map(i => `<circle cx="${62 + i * 12}" cy="17" r="4" class="cee-e2-art-knob"/>`).join("");
  svg.innerHTML = `<rect x="1" y="1" width="158" height="78" rx="6" fill="${body}"/>`
    + `<rect x="10" y="9" width="40" height="18" rx="1.5" class="cee-e2-art-lcd"/>`
    + knobs
    + `<rect x="124" y="9" width="26" height="22" rx="2" class="cee-e2-art-pad"/>`
    + `<rect x="124" y="50" width="26" height="22" rx="2" class="cee-e2-art-touch"/>`
    + pads;
  return svg;
}
