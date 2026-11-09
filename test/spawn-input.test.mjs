import { test } from "node:test";
import assert from "node:assert/strict";
import { run } from "./support/spawn.mjs";

const echoJSON = `
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => { input += chunk; });
process.stdin.on("end", () => process.stdout.write(JSON.stringify(JSON.parse(input))));
`;
const json = JSON.stringify({ label: "Grüße 🥁", value: "x".repeat(256 * 1024) });

for (const [kind, input] of [["string", json], ["Buffer", Buffer.from(json)]]) {
  test(`a large JSON ${kind} reaches the child completely and ends its input`, async () => {
    const result = await run(process.execPath, ["-e", echoJSON], { input, timeout: 5_000 });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, json);
  });
}

test("without input a child still receives an empty closed stream", async () => {
  const result = await run(process.execPath, ["-e", `
    let size = 0;
    process.stdin.on("data", chunk => { size += chunk.length; });
    process.stdin.on("end", () => console.log(size));
  `], { timeout: 5_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), "0");
});

test("a child that exits before reading its input keeps its exit status", async () => {
  const result = await run(process.execPath, ["-e", "process.exit(7)"], {
    input: Buffer.alloc(1024 * 1024), timeout: 5_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 7);
  assert.equal(result.signal, null);
});

test("an input-consuming child that outlives its timeout is reaped", async () => {
  const result = await run(process.execPath, ["-e", `
    process.stdin.resume();
    process.stdin.on("end", () => {
      console.log(process.pid);
      setInterval(() => {}, 60_000);
    });
  `], { input: "{}", timeout: 500 });
  assert.equal(result.error?.code, "ETIMEDOUT");
  assert.equal(result.status, null);
  const pid = Number(result.stdout.trim());
  assert.ok(Number.isSafeInteger(pid) && pid > 0);
  assert.throws(() => process.kill(pid, 0), { code: "ESRCH" });
});

test("an input-consuming child retains the output limit", async () => {
  const result = await run(process.execPath, ["-e", echoJSON], {
    input: json, timeout: 5_000, maxBuffer: 1024,
  });
  assert.equal(result.error?.code, "ENOBUFS");
});

test("unsupported input is rejected before starting a child", async () => {
  await assert.rejects(run(process.execPath, ["-e", "process.exit(0)"], { input: {} }), TypeError);
});
