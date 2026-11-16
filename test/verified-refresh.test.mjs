import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const workflow = readFileSync(new URL("../.github/workflows/verify-patches.yml", import.meta.url), "utf8");
const script = workflow.match(/- id: own\n[\s\S]*?run: \|\n([\s\S]*?)(?=\n      (?:#|-))/)[1].replace(/^          /gm, "");
const available = ["git", "bash"].every(command => spawnSync(command, ["--version"]).status === 0);
const options = { skip: !available && !process.env.CI ? "git and bash are required" : false };

function fixture(t) {
  const dir = mkdtempSync(join(tmpdir(), "verified-refresh-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("GIT_")));
  const git = (...args) => execFileSync("git", args, { cwd: dir, env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  git("init", "--quiet", "--initial-branch=base");
  git("config", "user.name", "Fixture");
  git("config", "user.email", "fixture@example.invalid");
  git("config", "commit.gpgsign", "false");
  git("config", "core.hooksPath", join(dir, ".git", "no-hooks"));
  git("config", "core.autocrlf", "false");
  mkdirSync(join(dir, "data", "patches"), { recursive: true });
  writeFileSync(join(dir, "data", "patches", "verified.json"), "{}\n");
  writeFileSync(join(dir, "code.txt"), "initial\n");
  git("add", ".");
  git("commit", "--quiet", "--message=initial");
  return { dir, git, env };
}

function skip(repo, cwd = repo.dir) {
  const output = join(repo.dir, "output");
  writeFileSync(output, "");
  execFileSync("bash", ["--noprofile", "--norc", "-eo", "pipefail", "-c", script], {
    cwd, env: { ...repo.env, GITHUB_OUTPUT: output }, stdio: ["ignore", "pipe", "pipe"],
  });
  return readFileSync(output, "utf8").includes("run=false");
}

function metadataMerge(repo) {
  repo.git("branch", "feature");
  writeFileSync(join(repo.dir, "data", "patches", "verified.json"), '{"proof":1}\n');
  repo.git("commit", "--quiet", "--all", "--message=base-proof");
  repo.git("checkout", "--quiet", "feature");
  writeFileSync(join(repo.dir, "code.txt"), "unchecked feature\n");
  repo.git("commit", "--quiet", "--all", "--message=feature");
  repo.git("merge", "--quiet", "--no-edit", "base");
  assert.equal(repo.git("diff", "--name-only", "HEAD^", "HEAD"), "data/patches/verified.json");
  assert.equal(repo.git("show", "--no-patch", "--format=%P", "HEAD").split(" ").length, 2);
}

test("a linear verified refresh can reuse the preceding verification", options, t => {
  const repo = fixture(t);
  writeFileSync(join(repo.dir, "data", "patches", "verified.json"), '{"proof":1}\n');
  repo.git("commit", "--quiet", "--all", "--message=proof");
  assert.equal(skip(repo), true);
});

test("a code change needs verification", options, t => {
  const repo = fixture(t);
  writeFileSync(join(repo.dir, "code.txt"), "changed\n");
  repo.git("commit", "--quiet", "--all", "--message=feature");
  assert.equal(skip(repo), false);
});

test("a base merge of only verified.json cannot waive an unchecked feature", options, t => {
  const repo = fixture(t);
  metadataMerge(repo);
  assert.equal(skip(repo), false);
});

test("a depth-two CI checkout still recognizes a metadata-only base merge", options, t => {
  const repo = fixture(t);
  metadataMerge(repo);
  const checkout = join(repo.dir, "checkout");
  repo.git("clone", "--quiet", "--depth=2", "--branch=feature", `file://${repo.dir}`, checkout);
  assert.equal(skip(repo, checkout), false);
});
