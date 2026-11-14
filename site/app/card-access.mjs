/**
 * The SD card for Blechy's look (src/card-check.mjs). The person picks the card's top folder, never a single file: a
 * picked file gives the page no path. In the app the folder dialog and every read and move run in the app
 * (src-tauri/src/card.rs, only inside the picked folder); in Chrome and Edge the page gets the folder with write access
 * (showDirectoryPicker); elsewhere it can only read the folder (an input with webkitdirectory) and Blechy says what to do.
 * Writing is for the Media folder only (MEDIA_FOLDER: the start image and the loading animation the firmware reads at start).
 */
import { DEPTH, isVsb, skipDir } from "../../src/card-check.mjs";

const parts = path => path.split("/").filter(Boolean);

/** The folder on the card that BLECH reads its start image and loading animation from (tools/patch/load_bar.py, splash_editor.py). */
export const MEDIA_FOLDER = "KORG/blechtribe/Media";
const same = (a, b) => a.toLowerCase() === b.toLowerCase();

/** The card through the app: it opened the dialog and keeps the folder, the page only names paths inside it. */
function nativeCard(invoke, name) {
  return {
    name, writable: true,
    list: () => invoke("card_list"),
    read: async path => new Uint8Array(await invoke("card_read", { path })),
    exists: path => invoke("card_exists", { path }),
    async move(from, to) { await invoke("card_move", { from, to }); return "moved"; },
    write: (path, bytes) => invoke("card_write", { path, bytes: [...bytes] }),
  };
}

/** The folder below `dir` named `name`, the exact name first, else in other letters (the card does not tell them apart). */
async function child(dir, name) {
  let near = null;
  for await (const [key, handle] of dir.entries()) {
    if (handle.kind !== "directory") continue;
    if (key === name) return handle;
    if (!near && same(key, name)) near = handle;
  }
  return near;
}

async function dirAt(root, names, create) {
  let dir = root;
  for (const name of names) {
    dir = await child(dir, name) ?? (create ? await dir.getDirectoryHandle(name, { create: true }) : null);
    if (!dir) return null;
  }
  return dir;
}

async function fileAt(root, path) {
  const names = parts(path);
  const dir = await dirAt(root, names.slice(0, -1), false);
  if (!dir) return null;
  try { return await dir.getFileHandle(names.at(-1)); } catch { return null; }
}

/** The card through a folder handle with write access. Where the handle cannot move, it copies and the original stays. */
export function handleCard(root) {
  async function* walk(dir, prefix, depth) {
    for await (const [name, handle] of dir.entries()) {
      if (handle.kind === "directory") {
        if (depth < DEPTH && !skipDir(name)) yield* walk(handle, `${prefix}${name}/`, depth + 1);
      } else if (isVsb(name)) {
        const file = await handle.getFile();
        yield { path: `${prefix}${name}`, size: file.size, modified: file.lastModified };
      }
    }
  }
  const card = {
    name: root.name, writable: true,
    async list() {
      const out = [];
      for await (const entry of walk(root, "", 0)) out.push(entry);
      return out;
    },
    async read(path) {
      const handle = await fileAt(root, path);
      if (!handle) throw new Error(path);
      return new Uint8Array(await (await handle.getFile()).arrayBuffer());
    },
    exists: async path => !!await fileAt(root, path),
    async move(from, to, { replace = false } = {}) {
      const source = await fileAt(root, from);
      if (!source) throw new Error(from);
      if (!replace && await card.exists(to)) throw new Error(to);
      const names = parts(to);
      const dir = await dirAt(root, names.slice(0, -1), true);
      if (typeof source.move === "function") {
        await source.move(dir, names.at(-1));
        return "moved";
      }
      const bytes = await (await source.getFile()).arrayBuffer();
      const out = await dir.getFileHandle(names.at(-1), { create: true });
      const writer = await out.createWritable();
      await writer.write(bytes);
      await writer.close();
      return "copied";
    },
    async write(path, bytes) {
      const names = parts(path);
      const dir = await dirAt(root, names.slice(0, -1), true);
      const writer = await (await dir.getFileHandle(names.at(-1), { create: true })).createWritable();
      await writer.write(bytes);
      await writer.close();
    },
  };
  return card;
}

/** The card read through an input with webkitdirectory: Blechy can look, not change. */
export function filesCard(list) {
  const files = [...list].map(file => ({ file, names: parts(file.webkitRelativePath || file.name) }))
    // the first name is the picked folder itself
    .filter(f => f.names.length > 1 && f.names.length - 1 <= DEPTH + 1 && isVsb(f.names.at(-1)) && !f.names.slice(1, -1).some(skipDir))
    .map(f => ({ file: f.file, path: f.names.slice(1).join("/") }));
  const find = path => files.find(f => f.path === path);
  return {
    name: list[0]?.webkitRelativePath?.split("/")[0] ?? "",
    writable: false,
    list: async () => files.map(f => ({ path: f.path, size: f.file.size, modified: f.file.lastModified })),
    async read(path) {
      const f = find(path);
      if (!f) throw new Error(path);
      return new Uint8Array(await f.file.arrayBuffer());
    },
    exists: async path => files.some(f => same(f.path, path)),
    move: async () => { throw new Error("read only"); },
    write: async () => { throw new Error("read only"); },
  };
}

function pickFiles(doc) {
  return new Promise(resolve => {
    const input = doc.createElement("input");
    input.type = "file";
    input.webkitdirectory = true;
    input.hidden = true;
    input.id = "cee-rescue-card-input";
    const done = value => { input.remove(); resolve(value); };
    input.addEventListener("change", () => done(input.files?.length ? filesCard(input.files) : null));
    input.addEventListener("cancel", () => done(null));
    doc.body.append(input);
    input.click();
  });
}

/**
 * Writes `bytes` as `name` into the Media folder of a card the person picks. Call it straight from the click. Returns
 * "written", "cancelled" or "readonly" (this browser cannot write to a folder; the download is the way then).
 */
export async function writeMedia(name, bytes, scope = globalThis) {
  const card = await pickCard(scope);
  if (!card) return "cancelled";
  if (!card.writable) return "readonly";
  await card.write(`${MEDIA_FOLDER}/${name}`, bytes);
  return "written";
}

/**
 * Asks the person for the card's top folder; null when they cancel. Call it straight from the click: the browser opens
 * its dialogs only in answer to one.
 */
export async function pickCard(scope = globalThis) {
  const invoke = scope.__TAURI__?.core?.invoke;
  if (invoke) {
    const name = await invoke("card_pick");
    return name == null ? null : nativeCard(invoke, name);
  }
  if (typeof scope.showDirectoryPicker === "function") {
    try {
      return handleCard(await scope.showDirectoryPicker({ id: "gelumpe-card", mode: "readwrite" }));
    } catch (e) {
      if (e?.name === "AbortError") return null;
      throw e;
    }
  }
  return pickFiles(scope.document);
}
