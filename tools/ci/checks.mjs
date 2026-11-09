const PASSED = new Set(["success", "skipped", "neutral"]);

export function newest(items, key) {
  const out = new Map();
  for (const item of items) if (!out.has(key(item)) || out.get(key(item)).id < item.id) out.set(key(item), item);
  return [...out.values()];
}

export function checkProblems(runs, checks, { self, required }) {
  const problems = [];
  const own = new Set(runs.filter(r => r.name === self).map(r => r.check_suite_id));
  const current = newest(runs.filter(r => r.name !== self), r => `${r.workflow_id} ${r.event}`);
  const active = new Set(current.map(r => r.check_suite_id));
  const obsolete = new Set(runs.filter(r => r.check_suite_id != null && !active.has(r.check_suite_id)).map(r => r.check_suite_id));
  for (const r of current) {
    if (r.status !== "completed") problems.push(`workflow "${r.name}" (${r.event}) is ${r.status}`);
    else if (!PASSED.has(r.conclusion)) problems.push(`workflow "${r.name}" (${r.event}) ended ${r.conclusion}`);
  }
  const latest = newest(checks.filter(c => !own.has(c.check_suite?.id) && !obsolete.has(c.check_suite?.id)), c => c.name);
  for (const c of latest) {
    if (c.status !== "completed") problems.push(`check "${c.name}" is ${c.status}`);
    else if (!PASSED.has(c.conclusion)) problems.push(`check "${c.name}" ended ${c.conclusion}`);
  }
  for (const name of required) {
    const c = latest.find(c => c.name === name);
    if (!c) problems.push(`required check "${name}" has not run`);
    else if (c.status === "completed" && c.conclusion !== "success") problems.push(`required check "${name}" did not pass`);
  }
  return problems;
}
