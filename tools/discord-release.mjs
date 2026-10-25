#!/usr/bin/env node
/**
 * Post a GitHub release to the Discord webhook (.github/workflows/discord-release.yml).
 *
 *   DISCORD_WEBHOOK=<url> node tools/discord-release.mjs <release.json>
 *
 * release.json is the release as GitHub's API gives it (tag_name, html_url, body). The notes go
 * out as embeds of at most 4000 characters, one message each, cut at line ends; nobody is pinged.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/** Discord allows 4096 characters in an embed's description; the rest is margin. */
export const PART = 4000;

/** The notes in parts of at most `max` characters, cut at line ends; a longer line is cut where it must. */
export function split(text, max = PART) {
  const parts = [];
  let part = "";
  for (let line of String(text ?? "").replace(/\r\n/g, "\n").trim().split("\n")) {
    while (line.length > max) {
      if (part) { parts.push(part); part = ""; }
      parts.push(line.slice(0, max));
      line = line.slice(max);
    }
    const next = part ? `${part}\n${line}` : line;
    if (next.length > max) { parts.push(part); part = line; }
    else part = next;
  }
  if (part.trim()) parts.push(part);
  return parts;
}

/** The messages for one release: the first carries the title and the link. */
export function messages(release) {
  const version = String(release.tag_name).replace(/^v/, "");
  const parts = split(release.body);
  if (!parts.length) parts.push("");
  return parts.map((description, i) => ({
    allowed_mentions: { parse: [] },
    embeds: [{
      ...(i === 0 ? { title: `BLECHTRIBE ${version} ist da`, url: release.html_url } : {}),
      description,
      color: 0xd8232a,
    }],
  }));
}

async function main() {
  const hook = process.env.DISCORD_WEBHOOK;
  if (!hook) {
    console.log("DISCORD_WEBHOOK fehlt, nichts gepostet.");
    return;
  }
  const release = JSON.parse(readFileSync(process.argv[2], "utf8"));
  for (const body of messages(release)) {
    const r = await fetch(`${hook}?wait=true`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`Discord antwortet ${r.status}: ${await r.text()}`);
  }
  console.log(`${release.tag_name} gepostet.`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
