import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const json = path => JSON.parse(readFileSync(path, "utf8"));
const save = (path, data) => writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`);
const digest = path => createHash("sha256").update(readFileSync(path)).digest("hex");
const taskKey = task => JSON.stringify(task);

function metrics(wrapper) {
  assert.equal(wrapper.format, "gelumpe-verification-shard");
  assert.equal(wrapper.version, 1);
  const part = wrapper.report;
  assert.equal(part.format, "gelumpe-check-shard");
  assert.equal(part.version, 1);
  assert.match(part.identity, /^[a-f0-9]{64}$/);
  assert.equal(part.passed, true);
  assert.ok(Array.isArray(part.tasks) && part.tasks.length > 0);
  const rows = part.metrics.filter(row => row.kind === "task");
  const pools = part.metrics.filter(row => row.kind === "pool");
  assert.equal(pools.length, 1);
  assert.equal(rows.length, part.tasks.length);
  assert.ok(rows.every(row => typeof row.cached === "boolean"));
  const expected = part.tasks.map(row => taskKey(row.task)).sort();
  const observed = rows.map(row => taskKey(row.task)).sort();
  assert.equal(new Set(expected).size, expected.length);
  assert.deepEqual(observed, expected);
  const hits = rows.filter(row => row.cached).length;
  assert.equal(pools[0].tasks, rows.length);
  assert.equal(pools[0].cache_hits, hits);
  return { tasks: rows.length, cacheHits: hits, executed: rows.length - hits,
    workers: pools[0].workers, cpus: pools[0].cpus };
}

export function compareShards(cold, warm) {
  const first = metrics(cold), second = metrics(warm);
  const withoutMetrics = value => {
    const result = structuredClone(value);
    delete result.report.metrics;
    return result;
  };
  assert.deepEqual(withoutMetrics(cold), withoutMetrics(warm), "cold and warm reports differ");
  assert.equal(first.cacheHits, 0, "cold reference reused task results");
  assert.ok(second.cacheHits > 0, "warm pass reused no task results");
  return { tasks: first.tasks, cold: first, warm: second, sameResults: true };
}

export function tapSummary(text) {
  const result = {};
  for (const name of ["tests", "pass", "fail", "cancelled", "skipped"]) {
    const rows = [...text.matchAll(new RegExp(`^# ${name} (\\d+)$`, "gm"))];
    assert.equal(rows.length, 1, `missing or ambiguous TAP ${name}`);
    result[name] = Number(rows[0][1]);
  }
  assert.equal(result.fail, 0);
  assert.equal(result.cancelled, 0);
  assert.ok(result.pass > 0, "smoke pass executed no tests");
  assert.equal(result.tests, result.pass + result.skipped);
  return result;
}

export function compareSmoke(cold, warm) {
  const first = tapSummary(cold), second = tapSummary(warm);
  assert.deepEqual(first, second, "smoke counts differ");
  const signature = text => text.split("\n").filter(line => /^\s*(# Subtest:|(?:not )?ok \d+\b)/.test(line));
  assert.deepEqual(signature(cold), signature(warm), "smoke test selection differs");
  return { ...first, signatureSha256: createHash("sha256").update(JSON.stringify(signature(cold))).digest("hex") };
}

function checkedSource() {
  const clean = spawnSync("git", ["diff", "--quiet", "HEAD", "--"]);
  assert.equal(clean.status, 0, "measurement source changed");
  const head = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" });
  assert.equal(head.status, 0);
  return head.stdout.trim();
}

function run(args, env = process.env) {
  const start = performance.now(), startedAt = new Date().toISOString();
  const result = spawnSync(process.execPath, args, { env, encoding: "utf8", maxBuffer: 128 * 1024 * 1024,
    timeout: 3_600_000 });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  assert.ifError(result.error);
  assert.equal(result.signal, null, `child ended with ${result.signal}`);
  assert.equal(result.status, 0, `child ended with ${result.status}`);
  return { seconds: (performance.now() - start) / 1000, startedAt, completedAt: new Date().toISOString(), stdout: result.stdout };
}

function pair(folder, command, env) {
  mkdirSync(folder, { recursive: true });
  const cache = mkdtempSync(join(process.env.RUNNER_TEMP, "cache-reference-"));
  const variables = { ...env, GELUMPE_CACHE_DIR: cache, GELUMPE_CACHE: "on" };
  const timings = {};
  for (const phase of ["cold", "warm"]) {
    console.log(`cache reference: ${phase}`);
    timings[phase] = run(command(phase), variables);
  }
  return timings;
}

function shardReference(folder, part, input) {
  const source = checkedSource();
  const verified = digest("data/patches/verified.json"), original = digest(input);
  const timings = pair(folder, phase => ["tools/verify-patches.mjs", "--cases", "all", "--shard", part,
    "--output", join(folder, `${phase}.json`), input], process.env);
  const compared = compareShards(json(join(folder, "cold.json")), json(join(folder, "warm.json")));
  assert.equal(digest("data/patches/verified.json"), verified);
  assert.equal(digest(input), original);
  assert.equal(checkedSource(), source);
  save(join(folder, "measurement.json"), { kind: "shard", source, ...compared, input: original,
    seconds: { cold: timings.cold.seconds, warm: timings.warm.seconds },
    intervals: Object.fromEntries(Object.entries(timings).map(([phase, value]) => [phase, { startedAt: value.startedAt, completedAt: value.completedAt }])) });
}

function smokeReference(folder, file, kind, input) {
  const source = checkedSource();
  const original = digest(input), verified = digest("data/patches/verified.json");
  assert.ok(["test/emulator-start-phase.test.mjs", "test/emulator-fxcard.test.mjs"].includes(file));
  const timings = pair(folder, () => ["--test", "--test-reporter=tap", "--test-timeout=3600000", file], process.env);
  const counts = compareSmoke(timings.cold.stdout, timings.warm.stdout);
  assert.equal(digest(input), original);
  assert.equal(digest("data/patches/verified.json"), verified);
  assert.equal(checkedSource(), source);
  save(join(folder, "measurement.json"), { kind, source, input: original, sameResults: true, counts,
    startTestCache: kind === "start" ? "off in both passes" : null,
    seconds: { cold: timings.cold.seconds, warm: timings.warm.seconds },
    intervals: Object.fromEntries(Object.entries(timings).map(([phase, value]) => [phase, { startedAt: value.startedAt, completedAt: value.completedAt }])) });
}

function files(folder) {
  return readdirSync(folder, { withFileTypes: true }).flatMap(entry => entry.isDirectory()
    ? files(join(folder, entry.name)) : [join(folder, entry.name)]);
}

function completeReference(downloaded, folder, input) {
  const source = checkedSource();
  const verified = digest("data/patches/verified.json"), paths = files(downloaded);
  const cold = paths.filter(path => path.endsWith("/cold.json"));
  assert.equal(cold.length, Number(process.env.REFERENCE_SHARDS));
  const measurements = [];
  for (const path of cold) {
    const warm = path.replace(/\/cold\.json$/, "/warm.json");
    measurements.push(compareShards(json(path), json(warm)));
  }
  const complete = {};
  for (const phase of ["cold", "warm"]) {
    const staged = join(folder, phase);
    mkdirSync(staged, { recursive: true });
    cold.forEach((path, index) => writeFileSync(join(staged, `${index}.json`),
      readFileSync(path.replace(/\/cold\.json$/, `/${phase}.json`))));
    const result = run(["tools/verify-patches.mjs", "--cases", "all", "--join-shards", staged, input]);
    const count = [...result.stdout.matchAll(/: (\d+) checks passed,/g)];
    assert.equal(count.length, 1);
    complete[phase] = { checks: Number(count[0][1]), seconds: result.seconds };
    assert.equal(digest("data/patches/verified.json"), verified);
  }
  assert.equal(complete.cold.checks, complete.warm.checks);
  assert.equal(checkedSource(), source);
  save(join(folder, "measurement.json"), { kind: "complete", source, sameResults: true, complete,
    tasks: measurements.reduce((sum, row) => sum + row.tasks, 0),
    coldCacheHits: measurements.reduce((sum, row) => sum + row.cold.cacheHits, 0),
    warmCacheHits: measurements.reduce((sum, row) => sum + row.warm.cacheHits, 0), verifiedUnchanged: true });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [mode, ...args] = process.argv.slice(2);
  if (mode === "--shard") {
    const [part, input, folder] = args;
    shardReference(folder, part, input);
  } else if (mode === "smoke") smokeReference(...args);
  else if (mode === "--join-shards") {
    const [downloaded, input, folder] = args;
    completeReference(downloaded, folder, input);
  } else throw new Error("expected --shard, smoke or --join-shards");
}
