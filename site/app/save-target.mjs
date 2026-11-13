/**
 * Where the Patcher's new SYSTEM.VSB goes. In the app the file goes straight onto an Electribe card the app found
 * mounted, or where the person points in the save dialog (src-tauri/src/save.rs: the page never names a path of its
 * own). In Chrome and Edge the browser's save dialog (showSaveFilePicker), elsewhere the download as before.
 */

/** "app", "picker" or "download": how `scope` (the window) can save a file. */
export function saveWay(scope = globalThis) {
  // The Android app has no card paths: saveFile takes the system's save dialog there (src-tauri/src/mobile.rs).
  if (scope.__GELUMPE_MOBILE) return "download";
  if (scope.__TAURI__?.core?.invoke) return "app";
  if (typeof scope.showSaveFilePicker === "function") return "picker";
  return "download";
}

/**
 * Saves `bytes` as `name` the best way `scope` has; `download(bytes, name)` is the plain download. Gives
 * `{ saved, way, where }`: saved false when the person cancelled the dialog, where the full path when the app knows it.
 */
export async function saveAs(bytes, name, { scope = globalThis, download }) {
  const way = saveWay(scope);
  if (way === "app") {
    const where = await scope.__TAURI__.core.invoke("save_pick", { name, bytes: Array.from(bytes) });
    return { saved: !!where, way, where: where ?? null };
  }
  if (way === "picker") {
    let handle;
    try {
      handle = await scope.showSaveFilePicker({ suggestedName: name });
    } catch (e) {
      if (e?.name === "AbortError") return { saved: false, way, where: null };
      // the dialog is refused (a frame, a policy): the download still works
      download(bytes, name);
      return { saved: true, way: "download", where: null };
    }
    const out = await handle.createWritable();
    await out.write(bytes);
    await out.close();
    return { saved: true, way, where: null };
  }
  download(bytes, name);
  return { saved: true, way, where: null };
}

/** The mounted cards with the KORG folder of `target` ("KORG/<folder>/System/"), only in the app. */
export async function findCards(target, scope = globalThis) {
  const invoke = scope.__GELUMPE_MOBILE ? null : scope.__TAURI__?.core?.invoke;
  return invoke ? invoke("save_cards", { target }) : [];
}

/** Writes the file onto `card` (one findCards gave) into `target`; the full path written. */
export function saveToCard(card, target, bytes, scope = globalThis) {
  return scope.__TAURI__.core.invoke("save_card", { root: card.root, target, bytes: Array.from(bytes) });
}

/** Whether two lists of cards say the same, so a poll only redraws on a change. */
export const sameCards = (a, b) => JSON.stringify(a) === JSON.stringify(b);
