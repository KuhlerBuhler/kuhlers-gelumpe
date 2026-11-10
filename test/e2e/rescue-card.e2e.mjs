// Blechy's look at the SD card on the Rettung page (src/card-check.mjs, site/app/card-access.mjs), with the card as a
// folder handle in memory: no real card, no firmware bytes beyond the head.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { setUp } from "./harness.mjs";
import * as rescue from "../../data/rescue.mjs";
import { t } from "../../site/app/i18n.mjs";

const CASES = rescue.CASES.map(c => ({ ...c, label: t(c.label) }));
const FOLDERS = rescue.FOLDERS;

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const settle = page => page.locator("#cee-rescue-answers:not([data-waiting])").waitFor({ state: "attached" });
/** The first question is typed, the cases come up above the field; every later one is a button. */
async function answer(page, text) {
  if (await page.locator("#cee-rescue-search").count()) {
    await page.fill("#cee-rescue-search", text);
    return page.locator("#cee-rescue-suggest [role=option]", { hasText: text }).first().click();
  }
  return page.locator("#cee-rescue-answers button", { hasText: text }).first().click();
}
const said = async page => { await settle(page); return page.locator("#cee-rescue-chat .cee-rescue-say").last().textContent(); };

/**
 * The SD card as a folder handle in the page (showDirectoryPicker), kept in memory: `files` maps a path to "sampler",
 * "synth" (a file of the right size with that head, no firmware bytes) or "junk". Without `move` the handles can only
 * copy, like older Chromium. `window.__card()` gives back every file with its head.
 */
async function withCard(files, { move = true } = {}) {
  const page = await h.page();
  await page.addInitScript(([files, canMove]) => {
    const bytesOf = kind => {
      if (kind === "junk") return new Uint8Array(1000);
      const b = new Uint8Array(0x200100);
      b[0x10] = 0x45; b[0x11] = 0x32;
      [b[0x12], b[0x2e]] = kind === "sampler" ? [0x53, 0x24] : [0x00, 0x23];
      return b;
    };
    const missing = () => new DOMException("missing", "NotFoundError");
    class FileH {
      constructor(parent, name, bytes) { Object.assign(this, { kind: "file", parent, name, bytes }); if (canMove) this.move = this.moveTo; }
      async getFile() { return new File([this.bytes], this.name, { lastModified: 1 }); }
      async createWritable() {
        const parts = [];
        return { write: async d => { parts.push(new Uint8Array(d)); }, close: async () => { this.bytes = new Uint8Array(await new Blob(parts).arrayBuffer()); } };
      }
      async moveTo(dir, name) { this.parent.children.delete(this.name); Object.assign(this, { parent: dir, name }); dir.children.set(name, this); }
    }
    class DirH {
      constructor(name) { Object.assign(this, { kind: "directory", name, children: new Map() }); }
      async *entries() { yield* [...this.children]; }
      async getDirectoryHandle(name, { create = false } = {}) {
        const d = this.children.get(name);
        if (d?.kind === "directory") return d;
        if (d || !create) throw missing();
        const made = new DirH(name);
        this.children.set(name, made);
        return made;
      }
      async getFileHandle(name, { create = false } = {}) {
        const f = this.children.get(name);
        if (f?.kind === "file") return f;
        if (f || !create) throw missing();
        const made = new FileH(this, name, new Uint8Array(0));
        this.children.set(name, made);
        return made;
      }
    }
    const root = new DirH("ELECTRIBE");
    for (const [path, kind] of Object.entries(files)) {
      const names = path.split("/");
      let dir = root;
      for (const n of names.slice(0, -1)) dir = dir.children.get(n) ?? (dir.children.set(n, new DirH(n)), dir.children.get(n));
      dir.children.set(names.at(-1), new FileH(dir, names.at(-1), bytesOf(kind)));
    }
    window.showDirectoryPicker = async () => root;
    window.__card = () => {
      const out = {};
      const walk = (dir, prefix) => {
        for (const [n, x] of dir.children) {
          if (x.kind === "directory") walk(x, `${prefix}${n}/`);
          else out[`${prefix}${n}`] = x.bytes.length !== 0x200100 ? "junk" : x.bytes[0x12] === 0x53 ? "sampler" : "synth";
        }
      };
      walk(root, "");
      return out;
    };
  }, [files, move]);
  await page.goto(`${h.url}#rescue`);
  await page.locator("#cee-rescue .cee-rescue").waitFor();
  return page;
}

/** No File in the menu for the colour, Korg's file as the one put on last, the running firmware by its answer, then "show me your card" and the pick. */
async function lookAtCard(page, colour, firmware) {
  await answer(page, CASES.find(c => c.id === "nofile").label);
  await answer(page, colour);
  await answer(page, "Im Menü bei SOFTWARE UPDATE");
  await settle(page);
  await answer(page, t("rescue.last.korg"));
  await settle(page);
  await answer(page, firmware);
  await answer(page, "Zeig mir deine SD-Karte");
  assert.match(await said(page), /löschen tu ich nie etwas/);
  await page.click("#cee-rescue-case-card-pick");
  await settle(page);
  return page.locator("#cee-rescue-chat").textContent();
}

const RED = FOLDERS[0].path;

test("the card: a wrong name in the right folder becomes SYSTEM.VSB after one click, then the talk goes on", async () => {
  const page = await withCard({ "KORG/electribe sampler/System/SYSTEM (1).VSB": "sampler" });
  const chat = await lookAtCard(page, "Rot", "Korgs Original");
  assert.match(chat, /Der Name stimmt nicht/);
  assert.match(chat, /So bring ich das in Ordnung/);
  await page.click("#cee-rescue-case-card-fix");
  await settle(page);
  assert.deepEqual(await page.evaluate(() => window.__card()), { [RED]: "sampler" });
  const paths = await page.locator("#cee-rescue-chat .cee-rescue-path").allTextContents();
  assert.equal(paths.at(-1), RED);
  assert.match(await page.locator("#cee-rescue-chat").textContent(), /Erledigt\..*sicher aus/s);
  assert.equal(await page.locator("#cee-rescue-answers button", { hasText: "Das Update ist durchgelaufen" }).count(), 1, "the talk goes on at the update");
  assert.deepEqual(page.errors, []);
});

test("the card: the right file in the wrong folder goes over, the other Electribe's file at the place goes aside as .old", async () => {
  const page = await withCard({ "SYSTEM.VSB.VSB": "sampler", [RED]: "synth", "Downloads/notes.vsb": "junk" });
  const chat = await lookAtCard(page, "Rot", "Korgs Original");
  for (const words of [/für die andere Electribe/, /falschen Ordner/, /Bytes groß/, /leg ich beiseite/]) assert.match(chat, words);
  await page.click("#cee-rescue-case-card-fix");
  await settle(page);
  assert.deepEqual(await page.evaluate(() => window.__card()), { [RED]: "sampler", [`${RED}.old`]: "synth", "Downloads/notes.vsb": "junk" });
  assert.match(await page.locator("#cee-rescue-chat").textContent(), /heißt jetzt KORG\/electribe sampler\/System\/SYSTEM\.VSB\.old\. Gelöscht hab ich nichts/);
  assert.deepEqual(page.errors, []);
});

test("the card: only the other Electribe's file, so Blechy moves nothing and says why", async () => {
  const page = await withCard({ "KORG/electribe/System/SYSTEM.VSB": "sampler" });
  const chat = await lookAtCard(page, "Blau", "Korgs Original");
  assert.match(chat, /für die andere Electribe/);
  assert.match(chat, /Keine davon passt/);
  assert.equal(await page.locator("#cee-rescue-case-card-fix").count(), 0);
  assert.deepEqual(await page.evaluate(() => window.__card()), { "KORG/electribe/System/SYSTEM.VSB": "sampler" });
  assert.deepEqual(page.errors, []);
});

test("the card: where the browser can only copy, the copy goes to the place and Blechy says the original stays", async () => {
  const page = await withCard({ "SYSTEM (1).VSB": "sampler" }, { move: false });
  await lookAtCard(page, "Rot", "Korgs Original");
  await page.click("#cee-rescue-case-card-fix");
  await settle(page);
  assert.deepEqual(await page.evaluate(() => window.__card()), { [RED]: "sampler", "SYSTEM (1).VSB": "sampler" });
  assert.match(await page.locator("#cee-rescue-chat").textContent(), /nur kopieren/);
  assert.deepEqual(page.errors, []);
});

test("the card in a browser without write access: Blechy reads the folder and says the moves to do by hand", async () => {
  const dir = join(h.dir, "card-readonly", "ELECTRIBE");
  const sampler = new Uint8Array(0x200100);
  [sampler[0x10], sampler[0x11], sampler[0x12], sampler[0x2e]] = [0x45, 0x32, 0x53, 0x24];
  for (const [path, bytes] of [["KORG/electribe sampler/System/system.vsb.vsb", sampler], ["KORG/electribe sampler/System/readme.txt", new Uint8Array(3)]]) {
    mkdirSync(dirname(join(dir, path)), { recursive: true });
    writeFileSync(join(dir, path), bytes);
  }
  const page = await h.page();
  await page.addInitScript(() => { delete window.showDirectoryPicker; delete Window.prototype.showDirectoryPicker; });
  await page.goto(`${h.url}#rescue`);
  await answer(page, CASES.find(c => c.id === "nofile").label);
  await answer(page, "Rot");
  await answer(page, "Im Menü bei SOFTWARE UPDATE");
  await settle(page);
  await answer(page, t("rescue.last.korg"));
  await settle(page);
  await answer(page, "Korgs Original");
  await answer(page, "Zeig mir deine SD-Karte");
  await settle(page);
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.click("#cee-rescue-case-card-pick")]);
  await chooser.setFiles(dir);
  await settle(page);
  const chat = await page.locator("#cee-rescue-chat").textContent();
  assert.match(chat, /KORG\/electribe sampler\/System\/system\.vsb\.vsb/);
  assert.match(chat, /nur schauen/);
  assert.match(chat, /system\.vsb\.vsb kommt nach KORG\/electribe sampler\/System\/SYSTEM\.VSB/);
  assert.equal(await page.locator("#cee-rescue-case-card-fix").count(), 0);
  assert.equal(await page.locator("#cee-rescue-answers button", { hasText: "Nochmal nachsehen" }).count(), 1);
  assert.deepEqual(page.errors, []);
});
