import { test } from "node:test";
import assert from "node:assert/strict";
import { parseOptions, shardReport, shardText } from "../tools/verify-patches.mjs";

const expected = { input: "a".repeat(64), output: "b".repeat(64), set: "blech", hardware: "blue", source: "c".repeat(40) };
const report = { format: "gelumpe-check-shard", version: 1, identity: "d".repeat(64), shard: { index: 1, count: 4 }, tasks: [], passed: true };

test("a shard requires one input and an explicit result destination", () => {
  assert.deepEqual(parseOptions(["--shard", "1/4", "--output", "part.json", "input.vsb"]), {
    files: ["input.vsb"], cases: null, merge: false, fromResults: false, shard: "1/4", output: "part.json", joinShards: null,
  });
  for (const args of [["--shard", "1/4", "input.vsb"], ["--shard", "1/4", "--output", "p", "a", "b"],
    ["--output", "p", "a"], ["--shard", "0/4", "--output", "p", "a"], ["--shard", "5/4", "--output", "p", "a"]]) {
    assert.throws(() => parseOptions(args));
  }
});

test("joining shard reports can check a limited case set without granting full verification", () => {
  assert.deepEqual(parseOptions(["--cases", "all", "--join-shards", "parts", "input.vsb"]), {
    files: ["input.vsb"], cases: "all", merge: false, fromResults: false, shard: null, output: null, joinShards: "parts",
  });
  for (const args of [["--join-shards", "parts", "a", "b"], ["--results", "--join-shards", "parts", "a"],
    ["--cases", "all", "--results", "a"], ["--shard", "1/4", "--output", "p", "--join-shards", "parts", "a"],
    ["--wat", "a"], ["--cases", "all", "--cases", "", "a"]]) assert.throws(() => parseOptions(args));
});

test("the transport binds a shard to independently computed firmware, hardware, set and source", () => {
  assert.deepEqual(shardReport(shardText(report, expected), expected), report);
  for (const key of Object.keys(expected)) {
    assert.throws(() => shardReport(shardText(report, { ...expected, [key]: "other" }), expected), new RegExp(key));
  }
  assert.throws(() => shardReport(shardText(report, { ...expected, hardware: undefined }), expected), /hardware/);
});

test("a complete report or failed shard cannot be transported as a successful shard", () => {
  for (const bad of [{ ok: true, checks: [] }, { ...report, passed: false }, { ...report, version: 9 },
    { ...report, shard: { index: 0, count: 4 } }, { ...report, tasks: undefined }, { ...report, identity: "wrong" }]) {
    assert.throws(() => shardText(bad, expected));
  }
  assert.throws(() => shardReport(JSON.stringify({ format: "gelumpe-verified", version: 1, results: [] }), expected));
});
