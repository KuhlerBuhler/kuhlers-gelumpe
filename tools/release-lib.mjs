/**
 * The logic behind tools/release.mjs, free of git, gh and the file system so
 * node --test can pin it down: version arithmetic, recognising the built
 * files, and the list of steps a release consists of.
 */

/** Tauri names its bundles `<productName>_<version>_<arch>[-setup].<ext>`. */
export const TARGETS = [
  { id: "macos-arm64", label: "macOS Apple Silicon (.dmg)", ext: "dmg", arch: "aarch64", setup: false },
  { id: "macos-x64", label: "macOS Intel (.dmg)", ext: "dmg", arch: "x64", setup: false },
  { id: "windows-x64", label: "Windows x64 (Setup .exe)", ext: "exe", arch: "x64", setup: true },
  { id: "linux-appimage", label: "Linux (.AppImage)", ext: "AppImage", arch: "amd64", setup: false },
  { id: "linux-deb", label: "Linux (.deb)", ext: "deb", arch: "amd64", setup: false },
];

/** Built from the user's own SYSTEM.VSB by tools/build-blech-patch.mjs; they go up when they are in the folder and are no problem when not. */
export const OPTIONAL_ASSETS = [
  { match: /^BLECH\.patch$/, label: "BLECH patch file" },
  { match: /^BLECH-for-[0-9a-f]{8}\.bsdiff$/, label: "BLECH bsdiff (bspatch), fits one exact SYSTEM.VSB" },
];

const FILE = /^.+_(\d+\.\d+\.\d+)_(aarch64|x64|amd64)(-setup)?\.(dmg|exe|AppImage|deb)$/;
const TAG = /^v?(\d+)\.(\d+)\.(\d+)$/;

/** "v1.2.3" or "1.2.3" to [1, 2, 3], anything else to null. */
export function parseVersion(text) {
  const m = TAG.exec(String(text).trim());
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

export function compareVersions(a, b) {
  const [x, y] = [parseVersion(a), parseVersion(b)];
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i];
  return 0;
}

/** The highest plain vX.Y.Z of a list of tag names, without the v, or null. */
export function latestVersion(tags) {
  const versions = tags.filter(t => /^v\d+\.\d+\.\d+$/.test(t)).map(t => t.slice(1));
  versions.sort(compareVersions);
  return versions.at(-1) ?? null;
}

/** The first release is 1.0.0 whatever the flag; after that patch, minor or major. */
export function nextVersion(latest, bump = "patch") {
  if (!latest) return "1.0.0";
  const [major, minor, patch] = parseVersion(latest);
  if (bump === "major") return `${major + 1}.0.0`;
  if (bump === "minor") return `${major}.${minor + 1}.0`;
  if (bump === "patch") return `${major}.${minor}.${patch + 1}`;
  throw new Error(`Unbekannter Sprung: ${bump}`);
}

/** Which target and version a file name stands for, or null when it is neither. */
export function classifyFile(name) {
  const m = FILE.exec(name);
  if (!m) return null;
  const [, version, arch, setup, ext] = m;
  const target = TARGETS.find(t => t.ext === ext && t.arch === arch && t.setup === Boolean(setup));
  return target ? { target, version } : null;
}

/**
 * Check a folder listing against the version that is due. `files` holds the
 * one file per target that goes up, `optional` the extra assets that are
 * present; `problems` says in words what is missing
 * or wrong, empty when the folder is ready.
 */
export function checkFiles(names, expectedVersion) {
  const byTarget = new Map(TARGETS.map(t => [t.id, []]));
  const ignored = [];
  const optional = [];
  for (const name of names) {
    const extra = OPTIONAL_ASSETS.find(a => a.match.test(name));
    if (extra) {
      optional.push({ name, label: extra.label });
      continue;
    }
    const hit = classifyFile(name);
    if (hit) byTarget.get(hit.target.id).push({ name, version: hit.version });
    else ignored.push(name);
  }

  const problems = [];
  const files = [];
  for (const target of TARGETS) {
    const hits = byTarget.get(target.id);
    if (hits.length === 0) problems.push(`Fehlt: ${target.label}`);
    else if (hits.length > 1) problems.push(`${target.label}: mehrere Dateien (${hits.map(h => h.name).join(", ")}), nur eine darf im Ordner liegen`);
    else {
      files.push({ target, name: hits[0].name, version: hits[0].version });
      if (hits[0].version !== expectedVersion) problems.push(`${hits[0].name}: Version ${hits[0].version}, fällig ist ${expectedVersion}`);
    }
  }
  const versions = new Set(files.map(f => f.version));
  if (versions.size > 1) problems.push(`Die Dateien gehören zu verschiedenen Versionen: ${[...versions].sort(compareVersions).join(", ")}`);
  return { files, optional, ignored, problems };
}

/** The heading that starts the English part of release-notes/<version>.md. */
export const ENGLISH_HEADING = "## English";
const ENGLISH_LINE = /^## English[ \t]*$/m;

/** The notes file in its two parts: the German text and the English text under "## English" (without the heading). `en` is null when there is no such heading. */
export function parseNotes(text) {
  const source = String(text ?? "").replace(/\r\n/g, "\n");
  const m = ENGLISH_LINE.exec(source);
  if (!m) return { de: source.trim(), en: null };
  return { de: source.slice(0, m.index).trim(), en: source.slice(m.index + m[0].length).trim() };
}

// The sections of a release that still hold once its downloads are gone; the app shows only these.
const KEPT = /^\*\*(Neu|Geändert|Behoben|New|Changed|Fixed)\*\*$/;

/**
 * One language part of a notes file for the app's Changelogs: the first line and the sections under KEPT. Downloads,
 * install hints and donation links go, their release may be gone from GitHub.
 */
export function appNotes(part) {
  const blocks = String(part ?? "").trim().split(/\n[ \t]*\n/);
  return [blocks[0], ...blocks.slice(1).filter(b => KEPT.test(b.split("\n")[0].trim()))].filter(Boolean).join("\n\n");
}

/** What is wrong with a notes file, in words; empty when both languages are there. */
export function checkNotes(text) {
  const { de, en } = parseNotes(text);
  const problems = [];
  if (!de) problems.push("der deutsche Teil ist leer");
  if (en === null) problems.push(`der englische Teil fehlt: eine Zeile "${ENGLISH_HEADING}" und darunter die englischen Notizen`);
  else if (!en) problems.push(`der englische Teil unter "${ENGLISH_HEADING}" ist leer`);
  return problems;
}

const DOWNLOAD_URL = "https://github.com/KuhlerBuhler/kuhlers-gelumpe/releases/download";

const BLOCK_TEXT = {
  de: {
    head: "**Herunterladen: nimm den Link für dein System, mehr brauchst du nicht**",
    windows: "Kuhlers GELUMPE für Windows",
    windowsHint: " Warnt SmartScreen: \"Weitere Informationen\", dann \"Trotzdem ausführen\".",
    macArm: "**Mac mit Apple-Chip** (Apfel-Menü -> Über diesen Mac zeigt \"Apple M…\")",
    macArmLink: "Kuhlers GELUMPE für Mac (Apple-Chip)",
    macIntel: "**Mac mit Intel**",
    macIntelLink: "Kuhlers GELUMPE für Mac (Intel)",
    or: "oder",
    xattr: "Auf dem Mac nach dem Reinziehen in Programme einmal im Terminal",
    xattrNote: "(die App ist nicht signiert)",
    assets: "Die vielen Dateien weiter unten unter \"Assets\" brauchst du nicht, die Links oben zeigen schon auf die richtige.",
    patch: "**Ohne App patchen**",
    patchFile: "`BLECH.patch`",
    patchBoth: "`BLECH.patch`, oder die `.bsdiff` passend zur Prüfsumme deiner `SYSTEM.VSB` (unten unter Assets)",
  },
  en: {
    head: "**Download: take the link for your system, that is all you need**",
    windows: "Kuhlers GELUMPE for Windows",
    windowsHint: " If SmartScreen warns you: \"More info\", then \"Run anyway\".",
    macArm: "**Mac with Apple chip** (Apple menu -> About This Mac shows \"Apple M…\")",
    macArmLink: "Kuhlers GELUMPE for Mac (Apple chip)",
    macIntel: "**Mac with Intel**",
    macIntelLink: "Kuhlers GELUMPE for Mac (Intel)",
    or: "or",
    xattr: "On the Mac, after dragging the app into Applications, run this once in Terminal",
    xattrNote: "(the app is not signed)",
    assets: "You do not need the many files further down under \"Assets\", the links above already point to the right one.",
    patch: "**Patch without the app**",
    patchFile: "`BLECH.patch`",
    patchBoth: "`BLECH.patch`, or the `.bsdiff` that matches the checksum of your `SYSTEM.VSB` (below under Assets)",
  },
};

/**
 * The download block at the top of a release in one language ("de" or "en"): one link per system, built from the
 * asset names that are really uploaded, so a system without a file gets no link. GitHub turns the spaces of a
 * file name into dots, so the links do too.
 */
export function downloadBlock(version, names, lang = "de") {
  const t = BLOCK_TEXT[lang];
  if (!t) throw new Error(`Unbekannte Sprache: ${lang}`);
  const link = (label, name) => `[${label}](${DOWNLOAD_URL}/v${version}/${name.replaceAll(" ", ".")})`;
  const byTarget = new Map();
  for (const name of names) {
    const hit = classifyFile(name);
    if (hit && !byTarget.has(hit.target.id)) byTarget.set(hit.target.id, name);
  }
  const windows = byTarget.get("windows-x64");
  const macArm = byTarget.get("macos-arm64");
  const macIntel = byTarget.get("macos-x64");
  const appImage = byTarget.get("linux-appimage");
  const deb = byTarget.get("linux-deb");

  const items = [];
  if (windows) items.push(`- **Windows:** ${link(t.windows, windows)}.${t.windowsHint}`);
  if (macArm) items.push(`- ${t.macArm}: ${link(t.macArmLink, macArm)}`);
  if (macIntel) items.push(`- ${t.macIntel}: ${link(t.macIntelLink, macIntel)}`);
  const linux = [appImage && link("AppImage", appImage), deb && link(".deb", deb)].filter(Boolean);
  if (linux.length) items.push(`- **Linux:** ${linux.join(` ${t.or} `)}`);

  const out = [];
  if (items.length) {
    out.push(t.head, items.join("\n"));
    if (macArm || macIntel) out.push(`${t.xattr}: \`xattr -dr com.apple.quarantine "/Applications/Kuhlers GELUMPE.app"\` ${t.xattrNote}.`);
    out.push(t.assets);
  }
  const patch = names.includes("BLECH.patch");
  const bsdiff = names.some(n => /^BLECH-for-[0-9a-f]{8}\.bsdiff$/.test(n));
  if (patch) out.push(`${t.patch}\n- ${bsdiff ? t.patchBoth : t.patchFile}`);
  return out.join("\n\n");
}

/**
 * The body of the published release: the German block and notes, then "## English" with the English block and
 * notes. The notes file carries the notes only, no download section.
 */
export function releaseBody(notesText, version, names) {
  const { de, en } = parseNotes(notesText);
  const part = (block, text) => [block, text].filter(Boolean).join("\n\n");
  const german = part(downloadBlock(version, names, "de"), de);
  if (en === null) return `${german}\n`;
  return `${german}\n\n${ENGLISH_HEADING}\n\n${part(downloadBlock(version, names, "en"), en)}\n`;
}

/**
 * The steps of a release, in order. Each step is a description and a command;
 * the CLI prints them or runs them. Older releases are deleted without
 * --cleanup-tag, so their tags stay. With `bump` the version files are
 * committed as "Release vX.Y.Z" and pushed to develop first (main is protected,
 * it gets the commit with the one develop -> main pull request), and the tag
 * goes on that commit, which does not exist yet: its place is RELEASE_COMMIT, filled in by
 * the CLI after the commit.
 */
export const BASE_BRANCH = "develop";
export const RELEASE_COMMIT = "@release-commit";
export const VERSION_FILES = ["package.json", "src-tauri/tauri.conf.json", "src-tauri/Cargo.toml", "src-tauri/Cargo.lock"];

export function planRelease({ tag, sha, assets, older, repo, bump = false, notes = null }) {
  const steps = [];
  if (bump) {
    steps.push({
      what: `Version ${tag.slice(1)} in die Dateien schreiben (package.json, tauri.conf.json, Cargo.toml, Cargo.lock)`,
      cmd: "node",
      args: ["tools/set-version.mjs", tag],
    }, {
      what: `Commit "Release ${tag}"`,
      cmd: "git",
      args: ["commit", "-m", `Release ${tag}`, "--", ...VERSION_FILES],
    }, {
      what: `Den Commit nach origin/${BASE_BRANCH} pushen`,
      cmd: "git",
      args: ["push", "origin", `HEAD:${BASE_BRANCH}`],
    });
  }
  steps.push({
    what: `Release ${tag} anlegen (Tag auf ${bump ? "den Bump-Commit" : sha.slice(0, 7)}), ${assets.length} Dateien hochladen, als neuestes markieren, unter Announcements als Discussion ankündigen`,
    cmd: "gh",
    args: ["release", "create", tag, ...assets, "--repo", repo, "--target", bump ? RELEASE_COMMIT : sha, "--title", tag, ...(notes ? ["--notes-file", notes] : ["--generate-notes"]), "--latest", "--discussion-category", "Announcements"],
  });
  for (const old of older.filter(t => t !== tag)) {
    steps.push({
      what: `Altes Release ${old} löschen (der Tag bleibt)`,
      cmd: "gh",
      args: ["release", "delete", old, "--repo", repo, "--yes"],
    });
  }
  return steps;
}
