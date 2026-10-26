import { test } from "node:test";
import assert from "node:assert/strict";
import { BASE_BRANCH, RELEASE_COMMIT, VERSION_FILES, checkFiles, checkNotes, classifyFile, downloadBlock, parseNotes, releaseBody, compareVersions, latestVersion, nextVersion, planRelease } from "../tools/release-lib.mjs";

const set = v => [
  `Kuhlers GELUMPE_${v}_aarch64.dmg`,
  `Kuhlers GELUMPE_${v}_x64.dmg`,
  `Kuhlers GELUMPE_${v}_x64-setup.exe`,
  `Kuhlers GELUMPE_${v}_amd64.AppImage`,
  `Kuhlers GELUMPE_${v}_amd64.deb`,
];

test("the first release is 1.0.0, later ones raise patch, minor or major", () => {
  assert.equal(nextVersion(null), "1.0.0");
  assert.equal(nextVersion(null, "major"), "1.0.0");
  assert.equal(nextVersion("1.0.0"), "1.0.1");
  assert.equal(nextVersion("1.4.9", "minor"), "1.5.0");
  assert.equal(nextVersion("1.4.9", "major"), "2.0.0");
  assert.throws(() => nextVersion("1.0.0", "huge"));
});

test("the latest tag is found numerically and odd tags are ignored", () => {
  assert.equal(latestVersion([]), null);
  assert.equal(latestVersion(["v1.9.0", "v1.10.0", "v1.2.0"]), "1.10.0");
  assert.equal(latestVersion(["nightly", "v1.0", "v2.0.0-rc1", "1.5.0"]), null);
  assert.ok(compareVersions("1.10.0", "1.9.9") > 0);
});

test("Tauri file names map to one target each", () => {
  const ids = set("1.0.0").map(n => classifyFile(n).target.id);
  assert.deepEqual(ids, ["macos-arm64", "macos-x64", "windows-x64", "linux-appimage", "linux-deb"]);
  assert.equal(classifyFile("Kuhlers GELUMPE_1.0.0_x64-setup.exe").version, "1.0.0");
});

test("files that are not a release bundle are not classified", () => {
  assert.equal(classifyFile("notes.txt"), null);
  assert.equal(classifyFile("Kuhlers GELUMPE_1.0.0_x64.exe"), null);
  assert.equal(classifyFile("Kuhlers GELUMPE_1.0_amd64.deb"), null);
  assert.equal(classifyFile("Kuhlers GELUMPE_1.0.0_arm64.dmg"), null);
});

test("a complete folder of the due version has no problems", () => {
  const { files, ignored, problems } = checkFiles([...set("1.0.1"), ".DS_Store"], "1.0.1");
  assert.deepEqual(problems, []);
  assert.equal(files.length, 5);
  assert.deepEqual(ignored, [".DS_Store"]);
});

test("every missing target is named", () => {
  const names = set("1.0.0").filter(n => !n.endsWith(".deb") && !n.endsWith("x64-setup.exe"));
  const { problems } = checkFiles(names, "1.0.0");
  assert.equal(problems.length, 2);
  assert.match(problems.join("\n"), /Windows/);
  assert.match(problems.join("\n"), /\.deb/);
});

test("BLECH.patch and BLECH.bsdiff are optional assets: listed when present, no problem when absent, never ignored", () => {
  const none = checkFiles(set("1.0.0"), "1.0.0");
  assert.deepEqual(none.optional, []);
  assert.deepEqual(none.problems, []);
  const both = checkFiles([...set("1.0.0"), "BLECH-for-7cb4825c.bsdiff", "BLECH.patch", "BLECH.bsdiff", "BLECH.txt"], "1.0.0");
  assert.deepEqual(both.problems, []);
  assert.deepEqual(both.optional.map(a => a.name), ["BLECH-for-7cb4825c.bsdiff", "BLECH.patch"]);
  assert.deepEqual(both.ignored, ["BLECH.bsdiff", "BLECH.txt"], "a bsdiff without the hash of its input in the name does not go up");
  assert.equal(both.files.length, 5);
});

test("a stale version is reported against the due one and against its neighbours", () => {
  const names = set("1.0.1");
  names[2] = "Kuhlers GELUMPE_1.0.0_x64-setup.exe";
  const { problems } = checkFiles(names, "1.0.1");
  assert.match(problems.join("\n"), /x64-setup\.exe: Version 1\.0\.0, fällig ist 1\.0\.1/);
  assert.match(problems.join("\n"), /verschiedenen Versionen: 1\.0\.0, 1\.0\.1/);
});

test("all files of an older version fail against the version that is due", () => {
  const { problems } = checkFiles(set("1.0.0"), "1.0.1");
  assert.equal(problems.length, 5);
});

test("two files for one target are refused", () => {
  const { problems } = checkFiles([...set("1.0.0"), "Kuhlers GELUMPE_0.9.0_amd64.deb"], "1.0.0");
  assert.equal(problems.length, 1);
  assert.match(problems[0], /mehrere Dateien/);
});

test("a bump puts set-version, the commit and the push before the release, and tags the bump commit", () => {
  const steps = planRelease({ tag: "v1.0.1", sha: "abcdef1234567", repo: "o/r", assets: ["/d/a.dmg"], older: ["v1.0.0"], bump: true });
  assert.deepEqual(steps.map(s => `${s.cmd} ${s.args[0]}`), ["node tools/set-version.mjs", "git commit", "git push", "gh release", "gh release"]);
  assert.deepEqual(steps[1].args.slice(0, 4), ["commit", "-m", "Release v1.0.1", "--"]);
  assert.deepEqual(steps[1].args.slice(4), VERSION_FILES);
  assert.equal(BASE_BRANCH, "develop");
  assert.deepEqual(steps[2].args, ["push", "origin", "HEAD:develop"], "main is protected: the bump goes to develop and reaches main with the release pull request");
  const create = steps[3].args;
  assert.equal(create[create.indexOf("--target") + 1], RELEASE_COMMIT);
  assert.ok(!create.includes("abcdef1234567"));
});

test("without a bump nothing is committed or pushed and the tag goes on HEAD", () => {
  const steps = planRelease({ tag: "v1.0.1", sha: "abcdef1234567", repo: "o/r", assets: ["/d/a.dmg"], older: [] });
  assert.equal(steps.length, 1);
  assert.equal(steps[0].args[steps[0].args.indexOf("--target") + 1], "abcdef1234567");
});

test("the plan creates the latest release first and deletes the others without touching tags", () => {
  const steps = planRelease({
    tag: "v1.0.1", sha: "abcdef1234567", repo: "o/r",
    assets: ["/d/a.dmg", "/d/b.deb"],
    older: ["v1.0.1", "v1.0.0", "v0.9.0"],
  });
  assert.equal(steps.length, 3);
  assert.deepEqual(steps[0].args.slice(0, 5), ["release", "create", "v1.0.1", "/d/a.dmg", "/d/b.deb"]);
  assert.ok(steps[0].args.includes("--latest"));
  assert.equal(steps[0].args[steps[0].args.indexOf("--discussion-category") + 1], "Announcements");
  assert.equal(steps[0].args[steps[0].args.indexOf("--target") + 1], "abcdef1234567");
  assert.deepEqual(steps.slice(1).map(s => s.args[2]), ["v1.0.0", "v0.9.0"]);
  assert.ok(steps.slice(1).every(s => s.args[1] === "delete" && !s.args.includes("--cleanup-tag")));
});

test("release notes from a file replace GitHub's generated list", () => {
  const generated = planRelease({ tag: "v1.0.1", sha: "abcdef1234567", repo: "o/r", assets: [], older: [] })[0].args;
  assert.ok(generated.includes("--generate-notes") && !generated.includes("--notes-file"));
  const own = planRelease({ tag: "v1.0.1", sha: "abcdef1234567", repo: "o/r", assets: [], older: [], notes: "/d/notes.md" })[0].args;
  assert.equal(own[own.indexOf("--notes-file") + 1], "/d/notes.md");
  assert.ok(!own.includes("--generate-notes"));
});

const U = "https://github.com/KuhlerBuhler/kuhlers-gelumpe/releases/download/v1.3.5";

test("the download block links every system with GitHub's dotted file names", () => {
  const de = downloadBlock("1.3.5", [...set("1.3.5"), "BLECH.patch"], "de");
  for (const name of ["Kuhlers.GELUMPE_1.3.5_x64-setup.exe", "Kuhlers.GELUMPE_1.3.5_aarch64.dmg", "Kuhlers.GELUMPE_1.3.5_x64.dmg", "Kuhlers.GELUMPE_1.3.5_amd64.AppImage", "Kuhlers.GELUMPE_1.3.5_amd64.deb"])
    assert.ok(de.includes(`(${U}/${name})`), name);
  assert.ok(!de.includes("Kuhlers GELUMPE_"), "no space in a link");
  assert.match(de, /^\*\*Herunterladen/);
  assert.ok(de.includes("SmartScreen") && de.includes("Apple M") && de.includes("xattr -dr com.apple.quarantine"));
  assert.ok(de.includes("brauchst du nicht"));
  assert.match(de, /\*\*Ohne App patchen\*\*\n- `BLECH\.patch`$/);
  const en = downloadBlock("1.3.5", [...set("1.3.5"), "BLECH.patch"], "en");
  assert.match(en, /^\*\*Download/);
  assert.ok(en.includes("Apple chip") && en.includes("Run anyway") && en.includes(`(${U}/Kuhlers.GELUMPE_1.3.5_amd64.deb)`));
  assert.match(en, /\*\*Patch without the app\*\*/);
});

test("a platform that is not uploaded gets no link and no dead one", () => {
  const names = set("1.3.5").filter(n => !n.endsWith("_x64.dmg") && !n.endsWith(".deb") && !n.endsWith("-setup.exe"));
  const de = downloadBlock("1.3.5", names, "de");
  assert.ok(!de.includes("Intel") && !de.includes(".deb") && !de.includes("Windows") && !de.includes("SmartScreen"));
  assert.ok(de.includes("aarch64.dmg") && de.includes("AppImage") && !de.includes(" oder "));
  const noMac = downloadBlock("1.3.5", set("1.3.5").filter(n => !n.endsWith(".dmg")), "en");
  assert.ok(!noMac.includes("xattr") && !noMac.includes("Mac"));
  assert.equal(downloadBlock("1.3.5", [], "de"), "");
  assert.ok(!downloadBlock("1.3.5", set("1.3.5"), "de").includes("BLECH"), "no patch line without the file");
});

test("the patch line names the bsdiff only when it goes up, and the version comes from the argument", () => {
  const both = downloadBlock("2.0.0", ["BLECH.patch", "BLECH-for-7cb4825c.bsdiff", "Kuhlers GELUMPE_2.0.0_x64.dmg"], "de");
  assert.ok(both.includes(".bsdiff") && both.includes("/download/v2.0.0/Kuhlers.GELUMPE_2.0.0_x64.dmg"));
  assert.ok(!downloadBlock("2.0.0", ["BLECH.patch"], "de").includes("bsdiff"));
  assert.throws(() => downloadBlock("1.0.0", [], "fr"));
});

const notes = "BLECH 1.3.5.\n\n**Neu**\n- Eins\n\n## English\n\nBLECH 1.3.5.\n\n**New**\n- One\n";

test("the notes file splits at the English heading", () => {
  assert.deepEqual(parseNotes(notes), { de: "BLECH 1.3.5.\n\n**Neu**\n- Eins", en: "BLECH 1.3.5.\n\n**New**\n- One" });
  assert.deepEqual(parseNotes("nur deutsch"), { de: "nur deutsch", en: null });
  assert.equal(parseNotes("a\r\n## English\r\nb").en, "b");
  assert.equal(parseNotes("a\n### English\nb").en, null, "only a level 2 heading counts");
});

test("the body is German block and notes, then the English heading with the English block and notes", () => {
  const body = releaseBody(notes, "1.3.5", [...set("1.3.5"), "BLECH.patch"]);
  const at = body.indexOf("\n## English\n");
  assert.ok(at > 0);
  const [de, en] = [body.slice(0, at), body.slice(at)];
  assert.match(de, /^\*\*Herunterladen[^]*\*\*Neu\*\*\n- Eins\n$/);
  assert.match(en, /^\n## English\n\n\*\*Download[^]*\*\*New\*\*\n- One\n$/);
  assert.ok(!de.includes("Download:") && !en.includes("Herunterladen"));
  assert.ok(body.indexOf("BLECH 1.3.5.") > body.indexOf("**Herunterladen"), "the block comes first");
  assert.equal(parseNotes(body).en.startsWith("**Download"), true);
});

test("a German-only file gives a German-only body", () => {
  assert.ok(!releaseBody("Nur deutsch.", "1.3.5", set("1.3.5")).includes("English"));
});

test("the due check wants both languages", () => {
  assert.deepEqual(checkNotes(notes), []);
  assert.equal(checkNotes("Nur deutsch.\n").length, 1);
  assert.match(checkNotes("Nur deutsch.\n")[0], /englische Teil fehlt/);
  assert.match(checkNotes("Deutsch\n\n## English\n\n  \n")[0], /leer/);
  assert.match(checkNotes("## English\n\nOnly English")[0], /deutsche Teil ist leer/);
  assert.equal(checkNotes("").length, 2);
});
