import { test } from "node:test";
import assert from "node:assert/strict";
import { SampleStore, SampleStoreError } from "../src/sample-transaction.mjs";
import { HEADER, entryFromWav, parseSampleFile } from "../src/sample-file.mjs";
import { wav, file } from "./support/sample-file.mjs";

class Card {
  files = new Map();
  durable = new Map();
  events = [];
  cut = Infinity;
  fault = null;
  owner = Promise.resolve();

  constructor(bytes = file({ 500: "Old", 501: "Other" })) {
    if (bytes) this.files.set("library", bytes.slice());
    this.persist();
  }
  persist() { this.durable = new Map([...this.files].map(([k, v]) => [k, v.slice()])); }
  powerCycle() {
    this.files = new Map([...this.durable].map(([k, v]) => [k, v.slice()]));
    this.cut = Infinity;
  }
  checkpoint(event) {
    this.events.push(event);
    if (this.events.length === this.cut) throw new Error("power cut");
  }
  async exclusive(work) {
    const previous = this.owner;
    let release;
    this.owner = new Promise(resolve => { release = resolve; });
    await previous;
    try { return await work(); } finally { release(); }
  }
  async size(role) { return this.files.get(role)?.length ?? null; }
  async read(role, at, length) { return this.files.get(role)?.slice(at, at + length) ?? new Uint8Array(); }
  async write(role, at, bytes) {
    const before = this.files.get(role) ?? new Uint8Array();
    const next = new Uint8Array(Math.max(before.length, at + bytes.length));
    next.set(before); next.set(bytes, at);
    this.files.set(role, next);
    this.fault?.(role, at, bytes, next);
    this.checkpoint({ op: "write", role, at, length: bytes.length });
    return bytes.length;
  }
  async flush(role) {
    this.durable.set(role, this.files.get(role).slice());
    this.checkpoint({ op: "flush", role });
  }
  async remove(role) {
    this.files.delete(role); this.durable.delete(role);
    this.checkpoint({ op: "remove", role });
  }
}

const source = bytes => ({ size: bytes.length, read: async (at, length) => bytes.slice(at, at + length) });
const entry = () => entryFromWav(wav({ frames: 80000 }), 500, "Replacement");
const names = card => parseSampleFile(card.files.get("library")).samples.map(s => [s.slot, s.name]);

test("saving an unchanged canonical entry writes neither sample nor journal nor index", async () => {
  const card = new Card();
  const store = new SampleStore(card);
  const record = entry();
  await store.put(500, source(record));
  const before = card.files.get("library").slice();
  card.events.length = 0;
  await store.put(500, source(record));
  assert.equal(card.files.get("library").length, before.length);
  assert.deepEqual(card.files.get("library"), before);
  assert.deepEqual(card.events, []);
  assert.equal(card.files.has("journal"), false);
});

test("an equal-sized entry with a late PCM or metadata change still appends", async () => {
  for (const at of [44 + 159999, 44 + 160000 + 16 + 2]) {
    const card = new Card();
    const store = new SampleStore(card);
    const record = entry();
    await store.put(500, source(record));
    const size = card.files.get("library").length;
    record[at] ^= 1;
    await store.put(500, source(record));
    assert.equal(card.files.get("library").length, size + record.length);
    assert.deepEqual(card.files.get("library").subarray(size), record);
  }
});

test("a failed equality read leaves the saved slot and index untouched", async () => {
  const card = new Card();
  const store = new SampleStore(card);
  const record = entry();
  await store.put(500, source(record));
  const before = card.files.get("library").slice();
  card.events.length = 0;
  const read = card.read.bind(card);
  card.read = async (role, at, length) => {
    if (role === "library" && at >= before.length - record.length) throw new Error("card read failed");
    return read(role, at, length);
  };
  await assert.rejects(store.put(500, source(record)), /card read failed/);
  assert.equal(card.files.get("library").length, before.length);
  assert.deepEqual(card.files.get("library"), before);
  assert.deepEqual(card.events, []);
});

test("replacing one slot appends only that sample and updates its index without copying other samples", async () => {
  const card = new Card();
  const original = card.files.get("library").slice();
  const record = entry();
  await new SampleStore(card).put(500, source(record));
  assert.deepEqual(names(card), [[500, "Replacement"], [501, "Other"]]);
  assert.equal(card.files.get("library").length, original.length + record.length);
  assert.deepEqual(card.files.get("library").slice(HEADER, original.length), original.slice(HEADER));
  assert.equal(card.files.has("journal"), false);
  const writes = card.events.filter(e => e.op === "write" && e.role === "library");
  assert.equal(writes.reduce((n, e) => n + e.length, 0), record.length + 4);
  assert.ok(writes.every(e => e.length <= 65536));
});

test("a cut after each write or flush recovers the old or complete new slot and preserves all other slots", async () => {
  const baseline = new Card();
  await new SampleStore(baseline).put(500, source(entry()));
  for (let cut = 1; cut <= baseline.events.length; cut++) {
    const card = new Card();
    card.cut = cut;
    await assert.rejects(new SampleStore(card).put(500, source(entry())), /power cut/);
    card.powerCycle();
    await new SampleStore(card).recover();
    assert.ok(["Old", "Replacement"].includes(names(card)[0][1]));
    assert.deepEqual(names(card)[1], [501, "Other"]);
    assert.equal(card.files.has("journal"), false);
    if (names(card)[0][1] === "Replacement") {
      const parsed = parseSampleFile(card.files.get("library"));
      const first = parsed.samples[0];
      assert.deepEqual(card.files.get("library").slice(first.offset, first.offset + first.length), entry());
    }
  }
});

test("a torn index sector is recovered from the saved header after the payload was verified", async () => {
  const card = new Card();
  card.fault = (role, at, bytes, next) => {
    if (role === "library" && at < HEADER && card.files.has("journal")) {
      next.fill(0xA5, Math.floor(at / 512) * 512, Math.floor(at / 512) * 512 + 512);
      card.durable.set(role, next.slice());
      throw new Error("torn sector");
    }
  };
  await assert.rejects(new SampleStore(card).put(500, source(entry())), /torn sector/);
  card.fault = null;
  card.powerCycle();
  await new SampleStore(card).recover();
  assert.deepEqual(names(card), [[500, "Replacement"], [501, "Other"]]);
});

test("damaged appended data rolls back the index, while an unreadable card keeps the journal", async () => {
  const card = new Card();
  card.fault = (role, at) => {
    if (role === "library" && at < HEADER && card.files.has("journal")) throw new Error("before index");
  };
  await assert.rejects(new SampleStore(card).put(500, source(entry())), /before index/);
  card.fault = null;
  card.powerCycle();
  const originalRead = card.read.bind(card);
  card.read = async (role, at, length) => {
    if (role === "library" && at >= HEADER) throw new Error("card unreadable");
    return originalRead(role, at, length);
  };
  await assert.rejects(new SampleStore(card).recover(), /card unreadable/);
  assert.equal(card.files.has("journal"), true);
  card.read = originalRead;
  card.files.get("library")[card.files.get("library").length - 1] ^= 1;
  await new SampleStore(card).recover();
  assert.deepEqual(names(card), [[500, "Old"], [501, "Other"]]);
});

test("deleting a slot changes only its index and a new import can reuse that slot", async () => {
  const card = new Card();
  const size = await card.size("library");
  const store = new SampleStore(card);
  await store.delete(500);
  assert.deepEqual(names(card), [[501, "Other"]]);
  assert.equal(await card.size("library"), size);
  assert.equal(card.events.filter(e => e.op === "write" && e.role === "library").reduce((n, e) => n + e.length, 0), 4);
  await store.put(500, source(entry()));
  assert.deepEqual(names(card), [[500, "Replacement"], [501, "Other"]]);
});

test("a first import creates a valid library; invalid slots and incomplete RIFF sources change nothing", async () => {
  const card = new Card(null);
  const store = new SampleStore(card);
  await assert.rejects(store.put(499, source(entry())), SampleStoreError);
  await assert.rejects(store.put(500, source(new Uint8Array(100))), SampleStoreError);
  assert.equal(card.files.size, 0);
  await store.put(500, source(entry()));
  assert.deepEqual(names(card), [[500, "Replacement"]]);
});

test("concurrent imports serialize and recover the previous journal before another slot is committed", async () => {
  const card = new Card();
  const other = entryFromWav(wav(), 502, "Third");
  await Promise.all([new SampleStore(card).put(500, source(entry())), new SampleStore(card).put(502, source(other))]);
  assert.deepEqual(names(card), [[500, "Replacement"], [501, "Other"], [502, "Third"]]);
});

test("an invalid journal or unrelated header changes are refused without overwriting the library", async () => {
  const card = new Card();
  card.files.set("journal", new Uint8Array(4160));
  const original = card.files.get("library").slice();
  await assert.rejects(new SampleStore(card).recover(), SampleStoreError);
  assert.deepEqual(card.files.get("library"), original);
  assert.equal(card.events.length, 0);
});

test("put never turns a missing source into a deletion", async () => {
  const card = new Card();
  await assert.rejects(new SampleStore(card).put(500, null), SampleStoreError);
  assert.equal(card.events.length, 0);
  assert.deepEqual(names(card), [[500, "Old"], [501, "Other"]]);
});

test("a source for a different slot is refused before any card write", async () => {
  const card = new Card();
  const other = entryFromWav(wav(), 502, "Wrong slot");
  await assert.rejects(new SampleStore(card).put(500, source(other)), SampleStoreError);
  assert.equal(card.events.length, 0);
});

test("unsupported PCM formats are rejected before any card write", async () => {
  for (const [at, value] of [[20, 3], [22, 3], [34, 8]]) {
    const card = new Card();
    const record = entry();
    record[at] = value;
    await assert.rejects(new SampleStore(card).put(500, source(record)), SampleStoreError);
    assert.equal(card.events.length, 0);
  }
});

test("payload and journal readback corruption never publishes a new index", async () => {
  for (const damaged of ["library", "journal"]) {
    const card = new Card();
    const original = card.files.get("library").slice(0, HEADER);
    card.fault = (role, at, bytes, next) => {
      if (role === damaged && (role === "journal" || at >= HEADER)) next[next.length - 1] ^= 1;
    };
    await assert.rejects(new SampleStore(card).put(500, source(entry())), SampleStoreError);
    assert.deepEqual(card.files.get("library").slice(0, HEADER), original);
  }
});

test("a short card write stops before publishing the index", async () => {
  const card = new Card();
  const original = card.files.get("library").slice(0, HEADER);
  const write = card.write.bind(card);
  card.write = async (role, at, bytes) => {
    await write(role, at, bytes.subarray(0, bytes.length - 1));
    return bytes.length - 1;
  };
  await assert.rejects(new SampleStore(card).put(500, source(entry())), SampleStoreError);
  assert.deepEqual(card.files.get("library").slice(0, HEADER), original);
  assert.equal(card.files.has("journal"), false);
});

test("recovery refuses a different header sector without writing a saved index over it", async () => {
  const card = new Card();
  card.fault = (role, at) => {
    if (role === "library" && at < HEADER) throw new Error("before index");
  };
  await assert.rejects(new SampleStore(card).put(500, source(entry())), /before index/);
  card.fault = null;
  card.powerCycle();
  card.files.get("library")[16] = 1;
  const before = card.files.get("library").slice();
  await assert.rejects(new SampleStore(card).recover(), SampleStoreError);
  assert.deepEqual(card.files.get("library"), before);
  assert.equal(card.files.has("journal"), true);
});

test("an overflow of the format's file size is refused before appending sample data", async () => {
  const card = new Card();
  const size = card.size.bind(card);
  card.size = async role => role === "library" ? 0xFFFFFFFF - 100 : size(role);
  await assert.rejects(new SampleStore(card).put(500, source(entry())), SampleStoreError);
  assert.equal(card.events.length, 0);
});

test("slot writes use full unsigned offsets beyond the old USB limits", async () => {
  const record = entryFromWav(wav(), 500, "At the end");
  for (const size of [0x10000000, 0x40000000, 0x80000000, 0xFFFFFFFF - record.length]) {
    const ranges = new Map([["library", [{ at: 0, bytes: file({ 500: "Old", 501: "Other" }) }]]]);
    const sizes = new Map([["library", size]]);
    const io = {
      exclusive: work => work(),
      size: async role => sizes.get(role) ?? null,
      read: async (role, at, length) => {
        const bytes = new Uint8Array(Math.max(0, Math.min(length, (sizes.get(role) ?? 0) - at)));
        for (const range of ranges.get(role) ?? []) {
          const start = Math.max(at, range.at);
          const end = Math.min(at + bytes.length, range.at + range.bytes.length);
          if (end > start) bytes.set(range.bytes.subarray(start - range.at, end - range.at), start - at);
        }
        return bytes;
      },
      write: async (role, at, bytes) => {
        assert.ok(bytes.length <= 65536);
        if (!ranges.has(role)) ranges.set(role, []);
        ranges.get(role).push({ at, bytes: bytes.slice() });
        sizes.set(role, Math.max(sizes.get(role) ?? 0, at + bytes.length));
        return bytes.length;
      },
      flush: async () => {},
      remove: async role => { ranges.delete(role); sizes.delete(role); },
    };
    await new SampleStore(io).put(500, source(record));
    const head = await io.read("library", 0, HEADER);
    assert.equal(new DataView(head.buffer).getUint32(16 + 500 * 4, true), size);
    assert.equal(await io.size("library"), size + record.length);
    assert.deepEqual(await io.read("library", size, record.length), record);
    const writes = ranges.get("library").length;
    await new SampleStore(io).put(500, source(record));
    assert.equal(await io.size("library"), size + record.length);
    assert.equal(ranges.get("library").length, writes);
  }
});
