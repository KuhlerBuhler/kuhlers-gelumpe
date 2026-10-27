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
    test(`${count} online on a ${label}: everyone on the floor as a solid Blechy, every name readable in the list`, async () => {
      const page = await open(count, viewport);
      const floorWidth = await page.locator(".cee-discord-floor").evaluate(n => n.clientWidth);
      const mainWidth = await page.locator("#cee-discord").evaluate(n => n.clientWidth - parseFloat(getComputedStyle(n).paddingLeft) - parseFloat(getComputedStyle(n).paddingRight));
      assert.ok(floorWidth >= mainWidth - 1, `the floor spans the main area: ${floorWidth} of ${mainWidth} px`);
      assert.equal(await page.locator(".cee-discord-blechy:visible").count(), count, "everyone online is on the floor");
      // Solid: inside his outline every Blechy is filled with the dark page colour, so he covers whoever is behind him.
      await page.waitForFunction(() => {
        const c = document.querySelector(".cee-discord-blechy-art");
        const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
        let dark = 0;
        for (let i = 0; i < d.length; i += 4) if (d[i + 3] === 255 && d[i] < 40) dark++;
        return dark > 1000;
      });
      assert.deepEqual(await page.locator(".cee-discord-blechy .cee-discord-tag").evaluateAll(tags => tags.filter(t => getComputedStyle(t).visibility !== "hidden").length), 0, "no name stands on the floor until the pointer is there");

      const listed = Math.min(count, 24);
      assert.equal(await page.locator(".cee-discord-people li:visible").count(), listed);
      assert.deepEqual(await overlaps(page, ".cee-discord-people li:visible"), []);
      if (count > 24) {
        await page.locator(".cee-discord-more", { hasText: `+${count - 24} weitere` }).click();
        assert.equal(await page.locator(".cee-discord-people li:visible").count(), count);
        assert.equal(await page.locator(".cee-discord-more:visible").count(), 0);
        assert.deepEqual(await overlaps(page, ".cee-discord-people li"), [], "all names, none on another");
      } else {
        assert.equal(await page.locator(".cee-discord-more:visible").count(), 0);
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "no sideways scrolling");
      assert.equal(await page.locator("#cee-discord", { hasText: "Lounge" }).count(), 0, "no list of voice channels");

      const { count: drawn, gap } = await frames(page);
      assert.ok(drawn >= 30 && gap < 200, `${drawn} frames in a second, longest gap ${Math.round(gap)} ms`);
      assert.deepEqual(page.errors, []);
      await page.context().close();
    });
  }
}

test("the head is solid too: across the eyes, every pixel from one side of the head to the other is filled", async () => {
  const page = await open(5, { width: 1280, height: 800 });
  // The third and fourth member stand still (away and busy), so their pictures do not change while we look.
  for (const index of [3, 4]) {
    await page.waitForFunction(i => {
      const c = document.querySelectorAll(".cee-discord-blechy-art")[i];
      return c.getContext("2d").getImageData(0, 0, c.width, c.height).data.some((v, j) => j % 4 === 3 && v);
    }, index);
    const holes = await page.locator(".cee-discord-blechy-art").nth(index).evaluate(c => {
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
      const opaque = (x, y) => d[(y * c.width + x) * 4 + 3] === 255;
      let top = 0;
      while (![...Array(c.width).keys()].some(x => opaque(x, top))) top++;
      // Rows 10 to 14 of the sprite, two canvas pixels each: the eyes, well inside the head.
      const gaps = [];
      for (let y = top + 20; y < top + 30; y++) {
        const xs = [...Array(c.width).keys()].filter(x => opaque(x, y));
        for (let x = xs[0]; x <= xs.at(-1); x++) if (!opaque(x, y)) gaps.push(`${x},${y}`);
      }
      return gaps;
    });
    assert.deepEqual(holes, [], `Blechy ${index}`);
  }
  assert.deepEqual(page.errors, []);
  await page.context().close();
});

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

test("not everyone dances at once: each Blechy keeps his own time", async () => {
  const page = await open(150, { width: 1280, height: 800 });
  await page.locator(".cee-discord-blechy[data-move=dance]").first().waitFor({ timeout: 30_000 });
  const most = await page.evaluate(() => new Promise(resolve => {
    let top = 0;
    const end = performance.now() + 3000;
    const look = () => {
      top = Math.max(top, document.querySelectorAll(".cee-discord-blechy[data-move=dance]").length);
      if (performance.now() < end) requestAnimationFrame(look); else resolve(top);
    };
    look();
  }));
  assert.ok(most < 150 * 0.3, `at most ${most} of the 90 who walk danced at the same time`);
  assert.deepEqual(page.errors, []);
  await page.context().close();
});

test("the open page asks again every minute: those who stay keep their place, newcomers walk in, those gone walk out", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1280, height: 800 });
  // The clock stands still between the steps below, so the floor moves only as far as the test lets it.
  const now = Date.now();
  await page.clock.install({ time: now });
  await page.clock.pauseAt(now + 1000);
  let answers = 0;
  const people = ids => ({ ...server(0), presence_count: ids.length, members: ids.map(i => ({ id: String(i), username: `member${i}`, status: "online", avatar_url: null })) });
  await page.route("https://discord.com/**", route => {
    answers++;
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(people(answers === 1 ? [0, 1, 2, 3, 4, 5] : [2, 3, 4, 5, 6, 7])) });
  });
  await page.goto(`${h.url}#discord`);
  await page.locator(".cee-discord-people li", { hasText: "member0" }).waitFor();
  await page.clock.runFor(2000);
  await page.locator(".cee-discord-blechy[data-id='3']").evaluate(n => { n.dataset.marked = "yes"; });
  const before = await page.locator(".cee-discord-blechy[data-id='3']").evaluate(n => n.style.transform);

  await page.clock.runFor(60_000);
  await page.locator(".cee-discord-people li", { hasText: "member7" }).waitFor();
  assert.equal(answers, 2);
  assert.equal(await page.locator(".cee-discord-head p").first().textContent(), "6 online. Hier kommen auch die Ankündigungen neuer Versionen an.");
  assert.equal(await page.locator(".cee-discord-blechy[data-id='3']").getAttribute("data-marked"), "yes", "the same Blechy, not a new floor");
  assert.notEqual(await page.locator(".cee-discord-blechy[data-id='3']").evaluate(n => n.style.transform), "", `he was at ${before} and walks on from there`);
  const at = id => page.locator(`.cee-discord-blechy[data-id='${id}']`).evaluate(n => [n.dataset.move, new DOMMatrix(getComputedStyle(n).transform).m41]);
  const room = await page.locator(".cee-discord-floor").evaluate(n => n.clientWidth);
  for (const id of [6, 7]) {
    const [move, x] = await at(id);
    assert.equal(move, "enter");
    assert.ok(x < 0 || x > room - 112, `newcomer ${id} starts beside the floor, at ${x}`);
  }
  for (const id of [0, 1]) assert.equal((await at(id))[0], "leave");

  await page.clock.runFor(40_000);
  assert.equal(await page.locator(".cee-discord-blechy[data-id='0'], .cee-discord-blechy[data-id='1']").count(), 0, "those gone have walked off");
  for (const id of [6, 7]) {
    const [move, x] = await at(id);
    assert.notEqual(move, "enter");
    assert.ok(x >= 0 && x <= room - 112, `newcomer ${id} is on the floor, at ${x}`);
  }
  assert.equal(await page.locator(".cee-discord-people li").count(), 6);
  assert.deepEqual(page.errors, []);
  await page.context().close();
});

test("an answer that comes while another page is open still spreads everyone across the floor once it is shown", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1280, height: 800 });
  let answer;
  const asked = new Promise(resolve => { answer = resolve; });
  await page.route("https://discord.com/**", async route => {
    await asked;
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(server(12)) });
  });
  await page.goto(`${h.url}#discord`);
  await page.locator("#cee-tab-start").click();
  answer();
  await page.locator(".cee-discord-people li").first().waitFor({ state: "attached" });
  await page.waitForTimeout(500);
  await page.locator("#cee-tab-discord").click();
  await page.waitForTimeout(300);
  const xs = await page.locator(".cee-discord-blechy").evaluateAll(nodes => nodes.map(n => new DOMMatrix(getComputedStyle(n).transform).m41));
  const room = await page.locator(".cee-discord-floor").evaluate(n => n.clientWidth);
  assert.ok(Math.max(...xs) - Math.min(...xs) > room / 2, `spread across ${room} px, not piled up: ${xs.map(Math.round).join(" ")}`);
  assert.deepEqual(page.errors, []);
  await page.context().close();
});
