import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { SampleStore } from "../src/sample-transaction.mjs";
import { HEADER, entryFromWav } from "../src/sample-file.mjs";
import { emuPython } from "./support/emu.mjs";
import { file, wav } from "./support/sample-file.mjs";
import { crc32 } from "../src/script/blob.mjs";

test("native store commits, recovers and propagates file errors with generated samples", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/patch", "-p", "test_sample_store.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});

test("the actual journal written by the shared store is recovered by the ARM routine", async () => {
  const original = file({ 500: "Before", 501: "Other" });
  const files = new Map([["library", original]]);
  const io = {
    exclusive: work => work(),
    size: async role => files.get(role)?.length ?? null,
    read: async (role, at, length) => files.get(role)?.slice(at, at + length) ?? new Uint8Array(),
    write: async (role, at, bytes) => {
      if (role === "library" && at < HEADER && files.has("journal")) throw new Error("cut before index");
      const before = files.get(role) ?? new Uint8Array();
      const next = new Uint8Array(Math.max(before.length, at + bytes.length));
      next.set(before); next.set(bytes, at); files.set(role, next);
      return bytes.length;
    },
    flush: async () => {},
    remove: async role => { files.delete(role); },
  };
  const entry = entryFromWav(wav({ frames: 80000 }), 500, "After");
  await assert.rejects(new SampleStore(io).put(500, { size: entry.length, read: async (at, length) => entry.slice(at, at + length) }), /cut before index/);
  const expected = files.get("library").slice(0, HEADER);
  new DataView(expected.buffer).setUint32(16 + 500 * 4, original.length, true);
  const script = `
import sys,json,binascii
sys.path.insert(0,'tools/patch')
from test_sample_store import Machine,LIBRARY,JOURNAL
data=json.load(sys.stdin)
machine=Machine(bytes.fromhex(data['library']),bytes.fromhex(data['journal']))
status=machine.recover()
print(json.dumps(dict(status=status,header_crc=binascii.crc32(machine.files[LIBRARY][:4096]),journal_remains=JOURNAL in machine.files)))
`;
  const result = spawnSync(emuPython(), ["-c", script], {
    input: JSON.stringify(Object.fromEntries([...files].map(([role, bytes]) => [role, Buffer.from(bytes).toString("hex")]))),
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), { status: 0, header_crc: crc32(expected), journal_remains: false });
});
