import { test } from "node:test";
import assert from "node:assert/strict";
import { notConnectedKey } from "../site/app/patcher.mjs";
import DE from "../site/app/i18n-de.mjs";

test("a USB action with the cable in but no MIDI session names the missing connection, not a missing device", () => {
  assert.equal(notConnectedKey("present"), "patcher.usb.notSession");
  for (const state of ["connected", "absent", "unknown"]) assert.equal(notConnectedKey(state), "patcher.usb.notConnected");
  assert.match(DE["patcher.usb.notSession"], /angesteckt, aber nicht mit der App verbunden/);
});
