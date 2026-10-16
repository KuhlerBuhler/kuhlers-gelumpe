import AxeBuilder from "@axe-core/playwright";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** Serious and critical axe violations of the page as it stands, one line each; empty is a pass. */
export async function severeViolations(page, { exclude = [] } = {}) {
  await page.waitForFunction(() => document.getAnimations().every(a => a.effect.getComputedTiming().iterations === Infinity));
  let builder = new AxeBuilder({ page }).withTags(TAGS);
  for (const selector of exclude) builder = builder.exclude(selector);
  const { violations } = await builder.analyze();
  return violations
    .filter(v => v.impact === "serious" || v.impact === "critical")
    .map(v => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map(n => `${n.target.join(" ")}: ${(n.any[0] ?? n.all[0] ?? n.none[0])?.message ?? v.help}`).join("; ")}`);
}
