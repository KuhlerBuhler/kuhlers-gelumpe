// Renders every slide of index.html to out/slide-N.png (1080 x 1080) and out/slide-N.mp4, where Blechy
// switches between his two poses, with the system Chrome and ffmpeg.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const dir = fileURLToPath(new URL(".", import.meta.url));
const out = `${dir}out`;
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1080, height: 1080 } });
await page.goto(pathToFileURL(`${dir}index.html`).href);
await page.evaluate(() => document.fonts.ready);
for (const slide of await page.locator(".slide").all()) {
  const n = (await slide.getAttribute("id")).slice(1);
  await slide.screenshot({ path: `${out}/slide-${n}.png` });
  await slide.evaluate(s => s.classList.add("alt"));
  await slide.screenshot({ path: `${out}/slide-${n}-b.png` });
  await slide.evaluate(s => s.classList.remove("alt"));
  // two poses at 2.5 per second, 6 s
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-loop", "1", "-t", "0.4", "-i", `${out}/slide-${n}.png`,
    "-loop", "1", "-t", "0.4", "-i", `${out}/slide-${n}-b.png`, "-filter_complex", "[0][1]concat=n=2,loop=14:16,format=yuv420p",
    "-r", "30", `${out}/slide-${n}.mp4`]);
}
await browser.close();
