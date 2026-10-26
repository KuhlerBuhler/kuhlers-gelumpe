import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const STATUSES = ["online", "online", "online", "idle", "dnd"];
/** A server with `count` people online, long names and games among them, as the widget API answers. */
const server = count => ({
  name: "Kuhlers Gelumpe",
  instant_invite: null,
  presence_count: count,
  channels: [{ id: "1", name: "Lounge", position: 0 }],
  members: Array.from({ length: count }, (_, i) => ({
    id: String(i),
    username: i % 7 ? `member${i}` : `a_rather_long_name_${i}_xx`,
    status: STATUSES[i % STATUSES.length],
    avatar_url: null,
    ...(i % 4 ? {} : { game: { name: "Ableton Live" } }),
  })),
});

async function open(count, viewport) {
  const page = await h.page();
  await page.setViewportSize(viewport);
  await page.route("https://discord.com/**", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(server(count)) }));
  await page.goto(`${h.url}#discord`);
  await page.locator(".cee-discord-people").waitFor();
  return page;
}

/** Pairs of visible boxes that overlap, by their names. */
const overlaps = (page, selector) => page.locator(selector).evaluateAll(nodes => {
  const boxes = nodes.map(n => [n.textContent, n.getBoundingClientRect()]).filter(([, r]) => r.width && r.height);
  const hits = [];
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const [a, ra] = boxes[i];
      const [b, rb] = boxes[j];
      if (ra.left < rb.right - 0.5 && rb.left < ra.right - 0.5 && ra.top < rb.bottom - 0.5 && rb.top < ra.bottom - 0.5) hits.push(`${a} / ${b}`);
    }
  }
  return hits;
});

/** Frames the page draws in one second and the longest gap between two of them. */
const frames = page => page.evaluate(() => new Promise(resolve => {
  const times = [];
  const end = performance.now() + 1000;
  const tick = now => { times.push(now); if (now < end) requestAnimationFrame(tick); else resolve({ count: times.length, gap: Math.max(...times.slice(1).map((t, i) => t - times[i])) }); };
  requestAnimationFrame(tick);
}));

for (const [label, viewport] of [["desktop", { width: 1280, height: 800 }], ["wide screen", { width: 1920, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  for (const count of [5, 40, 150]) {
    test(`${count} online on a ${label}: a few Blechys on the floor, every name readable in the list`, async () => {
      const page = await open(count, viewport);
      const floorWidth = await page.locator(".cee-discord-floor").evaluate(n => n.clientWidth);
      const mainWidth = await page.locator("#cee-discord").evaluate(n => n.clientWidth - parseFloat(getComputedStyle(n).paddingLeft) - parseFloat(getComputedStyle(n).paddingRight));
      assert.ok(floorWidth >= mainWidth - 1, `the floor spans the main area: ${floorWidth} of ${mainWidth} px`);
      const walkers = await page.locator(".cee-discord-blechy:visible").count();
      assert.ok(walkers >= 1 && walkers <= Math.min(count, 12, Math.floor(floorWidth / 96)), `${walkers} Blechys on a floor ${floorWidth} px wide`);
      assert.deepEqual(await page.locator(".cee-discord-blechy .cee-discord-tag").evaluateAll(tags => tags.filter(t => getComputedStyle(t).visibility !== "hidden").length), 0, "no name stands on the floor until the pointer is there");

      const listed = Math.min(count, 24);
      assert.equal(await page.locator(".cee-discord-people li:visible").count(), listed);
      assert.deepEqual(await overlaps(page, ".cee-discord-people li:visible"), []);
      if (count > 24) {
        await page.locator(".cee-discord-more", { hasText: `+${count - 24} weitere` }).click();
        assert.equal(await page.locator(".cee-discord-people li:visible").count(), count);
        assert.equal(await page.locator(".cee-discord-more").count(), 0);
        assert.deepEqual(await overlaps(page, ".cee-discord-people li"), [], "all names, none on another");
      } else {
        assert.equal(await page.locator(".cee-discord-more").count(), 0);
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "no sideways scrolling");

      const { count: drawn, gap } = await frames(page);
      assert.ok(drawn >= 30 && gap < 200, `${drawn} frames in a second, longest gap ${Math.round(gap)} ms`);
      assert.deepEqual(page.errors, []);
      await page.context().close();
    });
  }
}

test("a Blechy shows his name while the pointer is on him, and now and then stops for his dance", async () => {
  const page = await open(40, { width: 1280, height: 800 });
  await page.locator(".cee-discord-blechy[data-move=dance]").first().waitFor({ timeout: 20_000 });
  const index = await page.locator(".cee-discord-blechy").evaluateAll(nodes => nodes.findIndex(n => n.dataset.move === "dance"));
  const dancer = page.locator(".cee-discord-blechy").nth(index);
  const at = await dancer.evaluate(n => n.style.transform);
  await page.waitForTimeout(500);
  assert.equal(await dancer.evaluate(n => n.dataset.move === "dance" ? n.style.transform : null), at, "he stands still while he dances");
  await dancer.locator("canvas").hover({ force: true });
  const shown = await page.locator(".cee-discord-blechy .cee-discord-tag").evaluateAll(tags => tags.filter(t => getComputedStyle(t).visibility === "visible").length);
  assert.equal(shown, 1, "the name of the Blechy under the pointer, no other");
  assert.deepEqual(page.errors, []);
  await page.context().close();
});
