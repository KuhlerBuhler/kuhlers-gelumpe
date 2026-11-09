import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { checkProblems } from "./ci/checks.mjs";

export const SELF = "Automerge";
export const REQUIRED = ["unit", "browser", "guard", "patches"];
const FIELDS = "number,baseRefName,headRefName,headRefOid,isDraft,isCrossRepository,labels";

function eligibility(pr) {
  const problems = [];
  if (pr.baseRefName !== "develop") problems.push("not a pull request into develop");
  if (pr.isCrossRepository) problems.push("it is from a fork");
  if (pr.isDraft) problems.push("it is a draft");
  if (!pr.labels.some(label => label.name === "automerge")) problems.push("the automerge label is absent");
  return problems;
}

export function mergeProblems(pr, { runs, checks }) {
  return [...eligibility(pr), ...checkProblems(runs, checks, { self: SELF, required: REQUIRED })];
}

function gh(...args) {
  return execFileSync("gh", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "inherit"] });
}

export function runAutomerge({ repo, dryRun = false, gh: command = gh, log = console.log }) {
  if (!repo) throw new Error("GITHUB_REPOSITORY is required");
  const pages = path => JSON.parse(command("api", "--paginate", "--slurp", path));
  const prs = JSON.parse(command("pr", "list", "-R", repo, "--base", "develop", "--state", "open", "--limit", "100", "--json", FIELDS));
  for (const pr of prs) {
    if (eligibility(pr).length) continue;
    const sha = pr.headRefOid;
    const problems = mergeProblems(pr, {
      runs: pages(`repos/${repo}/actions/runs?head_sha=${sha}&per_page=100`).flatMap(page => page.workflow_runs),
      checks: pages(`repos/${repo}/commits/${sha}/check-runs?per_page=100`).flatMap(page => page.check_runs),
    });
    if (problems.length) {
      log(`#${pr.number} waits:\n  ${problems.join("\n  ")}`);
      continue;
    }
    const current = JSON.parse(command("pr", "view", String(pr.number), "-R", repo, "--json", FIELDS));
    if (current.headRefOid !== sha || eligibility(current).length) {
      log(`#${pr.number} changed during the check, not merged`);
      continue;
    }
    if (dryRun) {
      log(`#${pr.number} is ready, --dry-run: not merged`);
      continue;
    }
    try {
      command("pr", "merge", String(pr.number), "-R", repo, "--merge", "--admin", "--match-head-commit", sha);
      log(`#${pr.number} merged into develop`);
    } catch (error) {
      log(`#${pr.number} not merged: ${error.message}`);
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runAutomerge({ repo: process.env.GITHUB_REPOSITORY, dryRun: process.argv.includes("--dry-run") });
}
