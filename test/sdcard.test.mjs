import { test } from "node:test";
import assert from "node:assert/strict";
import { cardView } from "../site/app/sdcard.mjs";

// The page's SD card panel needs a browser; what can be checked without one is here.

test("without the service the card cannot be touched", () => {
  const v = cardView({ available: false });
  assert.equal(v.available, false);
  assert.equal(v.canOpen, false);
  assert.equal(cardView(undefined).available, false);
});

test("a card that is out can be put in, and the folder is open to the user", () => {
  const v = cardView({ available: true, inserted: false, running: false, folder: "/home/x/.gelumpe/sd/card", korg: "blechtribe" });
  assert.deepEqual([v.checked, v.canOpen, v.line], [false, true, "Nicht eingelegt"]);
});

test("an inserted card write-protects the folder, also while the Electribe runs", () => {
  for (const running of [false, true]) {
    const v = cardView({ available: true, inserted: true, running, folder: "/f" });
    assert.equal(v.checked, true);
    assert.equal(v.line, "Eingelegt, schreibgeschützt");
    assert.equal("locked" in v, false, "nothing keeps the card from being changed");
  }
});

test("a write of the firmware and a sync error are passed on", () => {
  const v = cardView({ available: true, folder: "/f", error: "kaputt", busy: true });
  assert.deepEqual([v.error, v.busy, v.line], ["kaputt", true, "Schreibt"]);
});

test("the view carries no folder path, no firmware folder and no copy offer", () => {
  const v = cardView({ available: true, inserted: false, folder: "/f", korg: "blechtribe", migrate: { from: "hacktribe", to: "blechtribe" } });
  assert.deepEqual(Object.keys(v).sort(), ["available", "busy", "canOpen", "checked", "error", "line"]);
});
