#!/usr/bin/env node
/**
 * Publish the apps built by hand on each system as the one current release.
 *
 *   npm run release -- prepare [--minor|--major]
 *       Work out the next version and put it into the version files
 *       (tools/set-version.mjs). Run it on every build machine before building;
 *       HEAD must be origin/main. Nothing is committed yet.
 *   npm run release -- next [--minor|--major]
 *       Print the next version only.
 *   npm run release -- [folder] [--minor|--major] [--yes]
 *       Check the folder (default dist-release/) and publish. Without --yes
 *       nothing is changed, the steps are only printed. With --yes: commit the
 *       version files as "Release vX.Y.Z", push that commit, create the tag on
 *       it and the release on GitHub (gh) with a discussion under Announcements,
 *       then delete every older release.
 *       Tags stay.
 *
 * BLECH.patch and BLECH-for-<sha8>.bsdiff in the folder (npm run build:blech-patch) go up
 * as well; BLECH.patch has to be built for the version that is due.
 *
 * The next version is the highest vX.Y.Z tag (local and on origin) with the
 * patch number raised by one, 1.0.0 when there is none.
 */
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parsePatchFile } from "../src/patchfile.mjs";
import { RELEASE_COMMIT, checkFiles, latestVersion, nextVersion, planRelease } from "./release-lib.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const fail = message => {
  console.error(message);
  process.exit(1);
};

const args = process.argv.slice(2);
const flags = new Set(args.filter(a => a.startsWith("--")));
const positional = args.filter(a => !a.startsWith("--"));
const known = ["--minor", "--major", "--yes", "--dry-run"];
const unknown = [...flags].filter(f => !known.includes(f));
if (unknown.length) fail(`Unbekannte Option: ${unknown.join(", ")}`);
if (flags.has("--minor") && flags.has("--major")) fail("--minor und --major schließen sich aus.");
const bump = flags.has("--major") ? "major" : flags.has("--minor") ? "minor" : "patch";
const command = ["prepare", "next"].includes(positional[0]) ? positional.shift() : "release";
const dry = flags.has("--dry-run") || !flags.has("--yes");

const read = (cmd, cmdArgs) => {
  const r = spawnSync(cmd, cmdArgs, { cwd: root, encoding: "utf8" });
  if (r.error || r.status !== 0) throw new Error(`${cmd} ${cmdArgs.join(" ")}: ${(r.stderr || r.error?.message || "").trim()}`);
  return r.stdout.trim();
};
const lines = text => text.split("\n").map(l => l.trim()).filter(Boolean);

function allTags() {
  const tags = lines(read("git", ["tag", "--list", "v*"]));
  try {
    for (const line of lines(read("git", ["ls-remote", "--tags", "--refs", "origin"]))) tags.push(line.split("refs/tags/")[1]);
  } catch (error) {
    if (command === "release" && !dry) fail(`origin nicht erreichbar, die nächste Version bliebe unsicher.\n${error.message}`);
    console.error(`Warnung: origin nicht erreichbar, nur lokale Tags gezählt.\n${error.message}`);
  }
  return tags;
}

/** A sentence when HEAD is not what origin/main points at, else null. */
function headProblem() {
  try {
    const head = read("git", ["rev-parse", "HEAD"]);
    const remoteMain = lines(read("git", ["ls-remote", "origin", "refs/heads/main"]))[0]?.split(/\s/)[0];
    return remoteMain === head ? null : `HEAD (${head.slice(0, 7)}) ist nicht der Stand von origin/main (${remoteMain?.slice(0, 7) ?? "unbekannt"}), erst pullen oder pushen`;
  } catch (error) {
    return `origin/main nicht lesbar: ${error.message}`;
  }
}

const latest = latestVersion(allTags());
const version = nextVersion(latest, bump);

if (command === "next") {
  console.log(version);
  process.exit(0);
}
if (command === "prepare") {
  const problem = headProblem();
  if (problem) fail(problem);
  const r = spawnSync("node", [resolve(root, "tools/set-version.mjs"), version], { stdio: "inherit" });
  if (r.status !== 0) process.exit(1);
  console.log(`Jetzt auf jedem System bauen. Letzter Tag: ${latest ? `v${latest}` : "keiner"}.`);
  process.exit(0);
}

const dir = resolve(root, positional[0] || "dist-release");
const tag = `v${version}`;
console.log(`${dry ? "TROCKENLAUF (nichts wird geändert, ohne --yes bleibt es dabei)" : "RELEASE"}`);
console.log(`Letzter Tag: ${latest ? `v${latest}` : "keiner"}, neu: ${tag} (${latest ? bump : "erstes Release"})`);
console.log(`Ordner: ${dir}`);

let names;
try {
  names = readdirSync(dir);
} catch {
  fail(`Ordner nicht lesbar: ${dir}`);
}
const { files, optional, ignored, problems } = checkFiles(names, version);
for (const f of files) console.log(`  ok  ${f.name}  (${f.target.label})`);
for (const f of optional) console.log(`  ok  ${f.name}  (${f.label})`);
if (optional.some(f => f.name === "BLECH.patch")) {
  try {
    const built = (await parsePatchFile(new Uint8Array(readFileSync(resolve(dir, "BLECH.patch"))))).version;
    if (built !== version) problems.push(`BLECH.patch ist für ${built} gebaut, fällig ist ${version}: npm run build:blech-patch -- --version ${version}`);
  } catch (error) {
    problems.push(`BLECH.patch: ${error.message}`);
  }
}
for (const name of ignored) console.log(`  --  ${name}  (wird nicht hochgeladen)`);

// Everything below only reads from GitHub; changes happen further down, and only with --yes.
let repo = "";
let older = [];
const sha = read("git", ["rev-parse", "HEAD"]);
try {
  repo = read("gh", ["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]);
  older = lines(read("gh", ["release", "list", "--limit", "1000", "--json", "tagName", "--jq", ".[].tagName"]));
  if (older.includes(tag)) problems.push(`Das Release ${tag} gibt es schon`);
} catch (error) {
  problems.push(`gh nicht benutzbar (installiert, mit "gh auth login" angemeldet?): ${error.message}`);
}
const headIssue = headProblem();
if (headIssue) problems.push(headIssue);
let needsBump = false;
try {
  needsBump = JSON.parse(read("git", ["show", "HEAD:package.json"])).version !== version;
} catch (error) {
  problems.push(`package.json in HEAD nicht lesbar: ${error.message}`);
}

if (problems.length) {
  console.error("\nProbleme:");
  for (const p of problems) console.error(`  - ${p}`);
}
const steps = planRelease({ tag, sha, assets: [...files, ...optional].map(f => resolve(dir, f.name)), older, repo, bump: needsBump });
console.log("\nSchritte:");
steps.forEach((s, i) => console.log(`  ${i + 1}. ${s.what}\n     ${s.cmd} ${s.args.map(a => (/\s/.test(a) ? JSON.stringify(a) : a)).join(" ")}`));

if (problems.length) process.exit(1);
if (dry) {
  console.log("\nNichts geändert. Zum Ausführen: npm run release -- --yes");
  process.exit(0);
}
for (const s of steps) {
  console.log(`\n${s.what}`);
  const args = s.args.map(a => (a === RELEASE_COMMIT ? read("git", ["rev-parse", "HEAD"]) : a));
  const r = spawnSync(s.cmd, args, { cwd: root, stdio: "inherit" });
  if (r.status !== 0) fail(`Abgebrochen bei: ${s.what}. Spätere Schritte (auch das Löschen alter Releases) sind nicht gelaufen.`);
}
console.log(`\nFertig: ${tag}`);
