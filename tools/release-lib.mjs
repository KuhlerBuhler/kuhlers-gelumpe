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

/**
 * The steps of a release, in order. Each step is a description and a command;
 * the CLI prints them or runs them. Older releases are deleted without
 * --cleanup-tag, so their tags stay. With `bump` the version files are
 * committed as "Release vX.Y.Z" and pushed first, and the tag goes on that
 * commit, which does not exist yet: its place is RELEASE_COMMIT, filled in by
 * the CLI after the commit.
 */
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
      what: "Den Commit nach origin/main pushen",
      cmd: "git",
      args: ["push", "origin", "HEAD:main"],
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
