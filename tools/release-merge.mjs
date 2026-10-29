/**
 * Merges an open release pull request (release/X.Y.Z -> main) once it is ready (.github/workflows/release-merge.yml,
 * docs/development.md, "Release"). Ready means all of:
 *   - not a draft, not from a fork;
 *   - a person with write access approved it, and since the approved commit only verified.json changed (the commit
 *     of the workflow Verify patches); no such person's last review asks for changes;
 *   - every workflow run on the head commit is finished, the newest run of each workflow passed, and so did every
 *     check of the head, with the required checks among them. A run that is still queued or running (a Verify
 *     patches that may still push a new verified.json) means: wait, the next finished run decides again.
 * The merge names the head it checked (--match-head-commit), so a head that moved in between is not merged.
 *
 *   node tools/release-merge.mjs [--dry-run]
 * Needs GH_TOKEN (a token of an admin: its merge has to start the Release workflow) and GITHUB_REPOSITORY.
 */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

/** This workflow's own name: its own run on the head is always still running. */
export const SELF = "Release merge";
export const REQUIRED = ["unit", "browser", "guard"];
/** The one file a commit after the approval may change. */
export const REFRESHED = "data/patches/verified.json";
const PASSED = new Set(["success", "skipped", "neutral"]);
const WRITERS = new Set(["admin", "maintain", "write"]);

export const isRelease = pr => pr.baseRefName === "main" && /^release\/\d+\.\d+\.\d+$/.test(pr.headRefName) && !pr.isCrossRepository;

/** The newest entry per key: a re-run gets a new, higher id. */
function newest(items, key) {
  const out = new Map();
  for (const it of items) if (!out.has(key(it)) || out.get(key(it)).id < it.id) out.set(key(it), it);
  return [...out.values()];
}

/** Why the checks of the head do not allow a merge yet; empty when they do. */
export function checkProblems(runs, checks) {
  const problems = [];
  const own = new Set(runs.filter(r => r.name === SELF).map(r => r.check_suite_id));
  for (const r of newest(runs.filter(r => r.name !== SELF), r => `${r.workflow_id} ${r.event}`)) {
    if (r.status !== "completed") problems.push(`workflow "${r.name}" (${r.event}) is ${r.status}`);
    else if (!PASSED.has(r.conclusion)) problems.push(`workflow "${r.name}" (${r.event}) ended ${r.conclusion}`);
  }
  const latest = newest(checks.filter(c => !own.has(c.check_suite?.id)), c => c.name);
  for (const c of latest) {
    if (c.status !== "completed") problems.push(`check "${c.name}" is ${c.status}`);
    else if (!PASSED.has(c.conclusion)) problems.push(`check "${c.name}" ended ${c.conclusion}`);
  }
  for (const name of REQUIRED) {
    const c = latest.find(c => c.name === name);
    if (!c) problems.push(`required check "${name}" has not run`);
    else if (c.status === "completed" && c.conclusion !== "success") problems.push(`required check "${name}" did not pass`);
  }
  return problems;
}

/**
 * Who approved, as far as it counts: the last review of each person with write access; `current(commit)` says
 * whether the head differs from that commit at most by verified.json. Empty `approvers` means no merge.
 */
export function approval(reviews, permission, current) {
  const last = newest(reviews.filter(r => r.state !== "COMMENTED" && r.state !== "PENDING"), r => r.user.login);
  const writers = last.filter(r => WRITERS.has(permission(r.user.login)));
  return {
    approvers: writers.filter(r => r.state === "APPROVED" && current(r.commit_id)).map(r => r.user.login),
    against: writers.filter(r => r.state === "CHANGES_REQUESTED").map(r => r.user.login),
  };
}

/** Why the pull request is not merged now; empty when it is. */
export function mergeProblems(pr, { runs, checks, reviews, permission, current }) {
  if (pr.isDraft) return ["it is a draft"];
  const { approvers, against } = approval(reviews, permission, current);
  const problems = [];
  if (against.length) problems.push(`changes requested by ${against.join(", ")}`);
  if (!approvers.length) problems.push("no approval of the current state by a person with write access");
  return [...problems, ...checkProblems(runs, checks)];
}

function gh(...args) {
  return execFileSync("gh", args, { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] });
}
const api = path => JSON.parse(gh("api", path));

function main() {
  const repo = process.env.GITHUB_REPOSITORY;
  const dry = process.argv.includes("--dry-run");
  const prs = JSON.parse(gh("pr", "list", "-R", repo, "--base", "main", "--state", "open", "--limit", "100",
    "--json", "number,baseRefName,headRefName,headRefOid,isDraft,isCrossRepository")).filter(isRelease);
  if (!prs.length) console.log("no open release pull request into main");
  for (const pr of prs) {
    const sha = pr.headRefOid;
    const permissions = new Map();
    const permission = login => {
      if (!permissions.has(login)) permissions.set(login, api(`repos/${repo}/collaborators/${login}/permission`).permission);
      return permissions.get(login);
    };
    const current = commit => commit === sha || api(`repos/${repo}/compare/${commit}...${sha}`).files.every(f => f.filename === REFRESHED);
    const problems = mergeProblems(pr, {
      runs: api(`repos/${repo}/actions/runs?head_sha=${sha}&per_page=100`).workflow_runs,
      checks: api(`repos/${repo}/commits/${sha}/check-runs?per_page=100`).check_runs,
      reviews: api(`repos/${repo}/pulls/${pr.number}/reviews?per_page=100`),
      permission,
      current,
    });
    if (problems.length) {
      console.log(`#${pr.number} (${pr.headRefName} at ${sha.slice(0, 7)}) waits:\n  ${problems.join("\n  ")}`);
      continue;
    }
    if (dry) {
      console.log(`#${pr.number} (${pr.headRefName} at ${sha.slice(0, 7)}) is ready, --dry-run: not merged`);
      continue;
    }
    gh("pr", "merge", String(pr.number), "-R", repo, "--merge", "--admin", "--match-head-commit", sha);
    console.log(`#${pr.number} (${pr.headRefName} at ${sha.slice(0, 7)}) merged into main`);
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
