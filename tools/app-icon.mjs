// Blechy's canonical head as SVG and the icon formats bundled by Tauri.
// node tools/app-icon.mjs --png
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { resizedHead, pixelPath } from "./blechy-head.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const out = join(root, "assets/app-icon");
const icons = join(root, "src-tauri/icons");
const head = resizedHead(50);
const x = Math.floor((64 - head[0].length) / 2);
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="512" height="512" role="img" aria-label="Blechy, Kuhler's GELUMPE">
<title>Blechy, Kuhler's GELUMPE</title>
<rect width="64" height="64" rx="14" fill="#0a0a0b"/>
<path transform="translate(${x} 7)" fill="#fafafa" shape-rendering="crispEdges" d="${pixelPath(head)}"/>
</svg>\n`;
mkdirSync(out, { recursive: true });
writeFileSync(join(out, "blechy.svg"), svg);
if (process.argv.includes("--png")) {
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage();
  const images = new Map();
  try {
    for (const size of [16, 24, 32, 48, 64, 128, 256, 512, 1024]) {
      await page.setViewportSize({ width: size, height: size });
      await page.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:100vw;height:100vh}</style>${svg}`);
      images.set(size, await page.screenshot({ omitBackground: true }));
    }
  } finally { await browser.close(); }
  for (const [name, size] of [["32x32.png",32],["128x128.png",128],["128x128@2x.png",256],["icon.png",512]]) {
    writeFileSync(join(icons, name), images.get(size));
  }
  writeFileSync(join(out, "preview.png"), images.get(512));
  const sizes = [16, 24, 32, 48, 64, 128, 256];
  const header = Buffer.alloc(6 + 16 * sizes.length);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(sizes.length, 4);
  let offset = header.length;
  sizes.forEach((size, index) => {
    const at = 6 + index * 16, image = images.get(size);
    header[at] = header[at + 1] = size % 256;
    header.writeUInt16LE(1, at + 4);
    header.writeUInt16LE(32, at + 6);
    header.writeUInt32LE(image.length, at + 8);
    header.writeUInt32LE(offset, at + 12);
    offset += image.length;
  });
  writeFileSync(join(icons, "icon.ico"), Buffer.concat([header, ...sizes.map(size => images.get(size))]));
  const chunks = [["icp4",16],["icp5",32],["icp6",64],["ic07",128],["ic08",256],["ic09",512],["ic10",1024],
    ["ic11",32],["ic12",64],["ic13",256],["ic14",512]].map(([type,size]) => {
      const image = images.get(size), chunk = Buffer.alloc(8);
      chunk.write(type); chunk.writeUInt32BE(8 + image.length, 4);
      return Buffer.concat([chunk, image]);
    });
  const icns = Buffer.alloc(8); icns.write("icns");
  icns.writeUInt32BE(8 + chunks.reduce((n, chunk) => n + chunk.length, 0), 4);
  writeFileSync(join(icons, "icon.icns"), Buffer.concat([icns, ...chunks]));
  console.log("wrote PNG, ICO and ICNS icons");
}
