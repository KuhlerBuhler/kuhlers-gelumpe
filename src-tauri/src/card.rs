//! The SD card for Blechy's look on the Rettung page (src/card-check.mjs, site/app/card-access.mjs). The person picks the
//! card's top folder in the app's own dialog; the app keeps that folder and the page only names paths inside it ("KORG/
//! electribe sampler/System/SYSTEM.VSB"). Every path is checked to stay inside the folder: plain names only, no "..", no
//! links followed. The page can list the .VSB files, read one, ask whether a name is taken and move a file to a free name.
//! Nothing here deletes or writes over a file.

use std::fs;
use std::path::{Component, Path, PathBuf};
use std::sync::Mutex;
use std::time::UNIX_EPOCH;

use serde::Serialize;
use tauri::{ipc::Response, AppHandle, State, WebviewWindow};
#[cfg(desktop)]
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_dialog::FilePath;

use crate::midi::trusted_origin;

/// The card folder the person picked last, if any.
#[derive(Default)]
pub struct CardRoot(Mutex<Option<PathBuf>>);

/// How deep below the card the look goes (DEPTH in src/card-check.mjs).
const DEPTH: usize = 6;
/// A SYSTEM.VSB has 2,097,408 bytes; nothing far larger is read.
const LIMIT: u64 = 4 << 20;

/// One .VSB file: its path below the card with "/", its size, its last change in milliseconds.
#[derive(Serialize, Debug, PartialEq)]
pub struct Entry {
    pub path: String,
    pub size: u64,
    pub modified: u64,
}

fn is_vsb(name: &str) -> bool {
    name.to_lowercase().ends_with(".vsb") && !name.starts_with("._")
}

fn skip_dir(name: &str) -> bool {
    name.starts_with('.') || name.eq_ignore_ascii_case("System Volume Information")
}

/// The names of a path below the card; an error for anything but plain names.
fn names(rel: &str) -> Result<Vec<&str>, String> {
    let parts: Vec<&str> = rel.split('/').collect();
    let plain = |p: &&str| {
        !p.is_empty()
            && !p.contains(['\\', ':', '\0'])
            && matches!(
                Path::new(p).components().collect::<Vec<_>>().as_slice(),
                [Component::Normal(_)]
            )
    };
    if parts.is_empty() || !parts.iter().all(plain) {
        return Err(format!("Der Pfad {rel} liegt nicht auf der Karte."));
    }
    Ok(parts)
}

/// The folder in `dir` named `name`: the exact name first, else the same name in other letters (FAT does not tell them
/// apart). Links are not followed.
fn child(dir: &Path, name: &str) -> Option<PathBuf> {
    let mut near = None;
    for entry in fs::read_dir(dir).ok()?.flatten() {
        if !entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
            continue;
        }
        let key = entry.file_name().to_string_lossy().into_owned();
        if key == name {
            return Some(entry.path());
        }
        if near.is_none() && key.to_lowercase() == name.to_lowercase() {
            near = Some(entry.path());
        }
    }
    near
}

/// The place of `rel` below `root`: its folders found in any letters (and made with `create`), the file name as given.
/// None when a folder is missing.
pub fn resolve(root: &Path, rel: &str, create: bool) -> Result<Option<PathBuf>, String> {
    let parts = names(rel)?;
    let (file, dirs) = parts.split_last().ok_or("Leerer Pfad.")?;
    let mut dir = root.to_path_buf();
    for name in dirs {
        dir = match child(&dir, name) {
            Some(found) => found,
            None if create => {
                let made = dir.join(name);
                fs::create_dir(&made)
                    .map_err(|e| format!("Den Ordner {name} konnte ich nicht anlegen: {e}"))?;
                made
            }
            None => return Ok(None),
        };
    }
    let real_root = root.canonicalize().map_err(|e| e.to_string())?;
    let real_dir = dir.canonicalize().map_err(|e| e.to_string())?;
    if !real_dir.starts_with(&real_root) {
        return Err(format!("Der Pfad {rel} liegt nicht auf der Karte."));
    }
    Ok(Some(dir.join(file)))
}

fn is_file(path: &Path) -> bool {
    fs::symlink_metadata(path)
        .map(|m| m.is_file())
        .unwrap_or(false)
}

fn taken(path: &Path) -> bool {
    fs::symlink_metadata(path).is_ok()
}

/// Every .VSB file below `root`, without system folders and without following links.
pub fn list(root: &Path) -> Vec<Entry> {
    fn walk(dir: &Path, prefix: &str, depth: usize, out: &mut Vec<Entry>) {
        let Ok(entries) = fs::read_dir(dir) else {
            return;
        };
        for entry in entries.flatten() {
            let Ok(kind) = entry.file_type() else {
                continue;
            };
            let name = entry.file_name().to_string_lossy().into_owned();
            if kind.is_dir() {
                if depth < DEPTH && !skip_dir(&name) {
                    walk(&entry.path(), &format!("{prefix}{name}/"), depth + 1, out);
                }
            } else if kind.is_file() && is_vsb(&name) {
                let Ok(meta) = entry.metadata() else { continue };
                let modified = meta
                    .modified()
                    .ok()
                    .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                    .map(|d| d.as_millis() as u64)
                    .unwrap_or(0);
                out.push(Entry {
                    path: format!("{prefix}{name}"),
                    size: meta.len(),
                    modified,
                });
            }
        }
    }
    let mut out = Vec::new();
    walk(root, "", 0, &mut out);
    out
}

pub fn read(root: &Path, rel: &str) -> Result<Vec<u8>, String> {
    let path = resolve(root, rel, false)?
        .filter(|p| is_file(p))
        .ok_or(format!("{rel} gibt es nicht."))?;
    let size = fs::metadata(&path).map_err(|e| e.to_string())?.len();
    if size > LIMIT {
        return Err(format!("{rel} ist zu groß für eine SYSTEM.VSB."));
    }
    fs::read(&path).map_err(|e| format!("{rel} ließ sich nicht lesen: {e}"))
}

pub fn exists(root: &Path, rel: &str) -> Result<bool, String> {
    Ok(resolve(root, rel, false)?.is_some_and(|p| taken(&p)))
}

/// Moves the file `from` to `to`, both below `root`. A taken `to` is refused: nothing is written over.
pub fn move_file(root: &Path, from: &str, to: &str) -> Result<(), String> {
    names(to)?;
    let source = resolve(root, from, false)?
        .filter(|p| is_file(p))
        .ok_or(format!("{from} gibt es nicht."))?;
    if exists(root, to)? {
        return Err(format!("{to} gibt es schon, ich schreib nicht drüber."));
    }
    let target = resolve(root, to, true)?.ok_or(format!("{to} liegt nicht auf der Karte."))?;
    fs::rename(&source, &target).map_err(|e| format!("{from} ließ sich nicht verschieben: {e}"))
}

fn allow(window: &WebviewWindow) -> Result<(), String> {
    let address = window.url().map_err(|e| e.to_string())?;
    if !trusted_origin(window.label(), address.as_str()) {
        return Err("Nur das lokale Hauptfenster darf auf die Karte.".into());
    }
    Ok(())
}

fn root(state: &State<'_, CardRoot>) -> Result<PathBuf, String> {
    state
        .0
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .ok_or("Es ist keine Karte gewählt.".into())
}

#[cfg(desktop)]
fn pick_folder(app: AppHandle) -> Result<Option<FilePath>, String> {
    Ok(app.dialog().file().blocking_pick_folder())
}

/// Android's folder picker hands out a document tree, not a path these commands could walk.
#[cfg(mobile)]
fn pick_folder(_app: AppHandle) -> Result<Option<FilePath>, String> {
    Err("Die Android-App kann noch keinen Kartenordner öffnen.".into())
}

/// Opens the folder dialog; the name of the picked folder, or None when the person cancels.
#[tauri::command]
pub async fn card_pick(
    window: WebviewWindow,
    app: AppHandle,
    state: State<'_, CardRoot>,
) -> Result<Option<String>, String> {
    allow(&window)?;
    let picked = tauri::async_runtime::spawn_blocking(move || pick_folder(app))
        .await
        .map_err(|e| e.to_string())??;
    let Some(picked) = picked else {
        return Ok(None);
    };
    let path = picked.into_path().map_err(|e| e.to_string())?;
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| path.display().to_string());
    *state.0.lock().map_err(|e| e.to_string())? = Some(path);
    Ok(Some(name))
}

#[tauri::command]
pub async fn card_list(
    window: WebviewWindow,
    state: State<'_, CardRoot>,
) -> Result<Vec<Entry>, String> {
    allow(&window)?;
    let root = root(&state)?;
    tauri::async_runtime::spawn_blocking(move || list(&root))
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn card_read(
    window: WebviewWindow,
    state: State<'_, CardRoot>,
    path: String,
) -> Result<Response, String> {
    allow(&window)?;
    let root = root(&state)?;
    let bytes = tauri::async_runtime::spawn_blocking(move || read(&root, &path))
        .await
        .map_err(|e| e.to_string())??;
    Ok(Response::new(bytes))
}

#[tauri::command]
pub fn card_exists(
    window: WebviewWindow,
    state: State<'_, CardRoot>,
    path: String,
) -> Result<bool, String> {
    allow(&window)?;
    exists(&root(&state)?, &path)
}

#[tauri::command]
pub fn card_move(
    window: WebviewWindow,
    state: State<'_, CardRoot>,
    from: String,
    to: String,
) -> Result<(), String> {
    allow(&window)?;
    move_file(&root(&state)?, &from, &to)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn card() -> PathBuf {
        static N: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir().join(format!(
            "gelumpe-card-{}-{}",
            std::process::id(),
            N.fetch_add(1, Ordering::SeqCst)
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("KORG/electribe sampler/System")).unwrap();
        dir
    }

    fn put(root: &Path, rel: &str, bytes: &[u8]) {
        let path = root.join(rel);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, bytes).unwrap();
    }

    #[test]
    fn only_plain_names_below_the_card() {
        let root = card();
        for bad in [
            "../x.VSB",
            "KORG/../../x.VSB",
            "/etc/passwd",
            "KORG//x.VSB",
            "",
            "a\\b.VSB",
            "C:x.VSB",
            "./x.VSB",
        ] {
            assert!(resolve(&root, bad, false).is_err(), "{bad}");
            assert!(move_file(&root, "x.VSB", bad).is_err(), "{bad}");
        }
        assert!(
            resolve(&root, "KORG/electribe sampler/System/SYSTEM.VSB", false)
                .unwrap()
                .is_some()
        );
    }

    #[test]
    fn lists_vsb_files_without_system_folders_and_mac_shadows() {
        let root = card();
        put(&root, "KORG/electribe sampler/System/SYSTEM (1).VSB", b"a");
        put(&root, "KORG/electribe sampler/System/._SYSTEM.VSB", b"b");
        put(&root, "Downloads/system.vsb", b"cc");
        put(&root, ".Trashes/SYSTEM.VSB", b"d");
        put(&root, "System Volume Information/SYSTEM.VSB", b"e");
        put(&root, "notes.txt", b"f");
        let mut paths: Vec<_> = list(&root).into_iter().map(|e| (e.path, e.size)).collect();
        paths.sort();
        assert_eq!(
            paths,
            [
                ("Downloads/system.vsb".to_string(), 2),
                (
                    "KORG/electribe sampler/System/SYSTEM (1).VSB".to_string(),
                    1
                )
            ]
        );
    }

    #[test]
    fn folders_match_in_any_letters() {
        let root = card();
        put(&root, "KORG/electribe sampler/System/SYSTEM.VSB", b"x");
        assert!(exists(&root, "korg/Electribe Sampler/SYSTEM/SYSTEM.VSB").unwrap());
        assert_eq!(
            read(&root, "korg/electribe sampler/system/SYSTEM.VSB").unwrap(),
            b"x"
        );
        assert!(!exists(&root, "KORG/hacktribe/System/SYSTEM.VSB").unwrap());
    }

    #[test]
    fn moves_into_new_folders_and_never_writes_over() {
        let root = card();
        put(&root, "SYSTEM (1).VSB", b"new");
        put(&root, "KORG/electribe sampler/System/SYSTEM.VSB", b"old");
        let target = "KORG/electribe sampler/System/SYSTEM.VSB";
        assert!(move_file(&root, "SYSTEM (1).VSB", target).is_err());
        assert_eq!(fs::read(root.join(target)).unwrap(), b"old");
        move_file(
            &root,
            target,
            "KORG/electribe sampler/System/SYSTEM.VSB.old",
        )
        .unwrap();
        move_file(&root, "SYSTEM (1).VSB", target).unwrap();
        assert_eq!(fs::read(root.join(target)).unwrap(), b"new");
        assert_eq!(
            fs::read(root.join("KORG/electribe sampler/System/SYSTEM.VSB.old")).unwrap(),
            b"old"
        );
        put(&root, "x.VSB", b"x");
        move_file(&root, "x.VSB", "KORG/hacktribe/System/SYSTEM.VSB").unwrap();
        assert!(is_file(&root.join("KORG/hacktribe/System/SYSTEM.VSB")));
        assert!(move_file(&root, "missing.VSB", "KORG/y.VSB").is_err());
    }

    #[cfg(unix)]
    #[test]
    fn links_out_of_the_card_are_not_followed() {
        let root = card();
        let outside = card();
        put(&outside, "secret/SYSTEM.VSB", b"s");
        std::os::unix::fs::symlink(outside.join("secret"), root.join("link")).unwrap();
        assert!(list(&root).is_empty());
        assert!(read(&root, "link/SYSTEM.VSB").is_err());
        assert!(!exists(&root, "link/SYSTEM.VSB").unwrap());
    }
}
