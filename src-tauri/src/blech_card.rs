//! The Electribe's SD card put straight into the computer, as a target next to the device over USB (site/app/target.mjs).
//! The app looks for a KORG folder on every mounted volume (the same volumes save.rs looks at) and writes only into a
//! folder BLECHTRIBE reads below KORG/blechtribe/. The page names the folder and the file name, never a path of its own:
//! the folder is one of FOLDERS, the name a plain one with that folder's ending.

use std::ffi::OsStr;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::Serialize;
use tauri::WebviewWindow;

use crate::card::child;
use crate::midi::trusted_origin;
use crate::save::mounted;

/// The folders below KORG/blechtribe/ a file may go to, each with the ending its files have. Plugin: the plugin files
/// MANAGE PLUGINS lists (ARCHIVE.folder in data/script/contract.mjs).
const FOLDERS: [(&str, &str); 1] = [("Plugin", ".blech")];
/// The longest file name without its ending (BLECH.NAME_MAX in src/protocol.mjs).
const NAME_MAX: usize = 16;
/// A plugin file is a few KiB; nothing far larger is written.
const LIMIT: usize = 1 << 20;

/// A mounted volume with a KORG folder: its top folder (given back to blech_card_write) and the name to show.
#[derive(Serialize, Debug, PartialEq)]
pub struct Card {
    pub root: String,
    pub volume: String,
}

fn volume_name(root: &Path) -> String {
    root.file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| root.display().to_string())
}

/// The volumes in `roots` that have a KORG folder (any letters, no links).
pub fn cards(roots: &[PathBuf]) -> Vec<Card> {
    roots
        .iter()
        .filter(|root| child(root, "KORG").is_some())
        .map(|root| Card {
            root: root.display().to_string(),
            volume: volume_name(root),
        })
        .collect()
}

/// The ending files in `folder` must have; an error for a folder not in FOLDERS.
fn ending_of(folder: &str) -> Result<&'static str, String> {
    FOLDERS
        .iter()
        .find(|(f, _)| *f == folder)
        .map(|(_, e)| *e)
        .ok_or(format!("{folder} ist kein Ordner von BLECHTRIBE."))
}

/// Whether `name` is a file name BLECHTRIBE takes in a folder with `ending`: 1 to 16 letters, digits, "_" or "-", then the ending.
fn plain_name(name: &str, ending: &str) -> bool {
    name.strip_suffix(ending).is_some_and(|stem| {
        !stem.is_empty()
            && stem.len() <= NAME_MAX
            && stem
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
    })
}

/// The folder in `dir` named `name`, made when it is missing; it has to stay inside `dir`.
fn folder_in(dir: &Path, name: &str) -> Result<PathBuf, String> {
    let found = match child(dir, name) {
        Some(found) => found,
        None => {
            let made = dir.join(name);
            fs::create_dir(&made)
                .map_err(|e| format!("Den Ordner {name} konnte ich nicht anlegen: {e}"))?;
            made
        }
    };
    let real_dir = dir.canonicalize().map_err(|e| e.to_string())?;
    let real = found.canonicalize().map_err(|e| e.to_string())?;
    if real.parent() != Some(real_dir.as_path()) {
        return Err(format!("{name} liegt nicht auf der Karte."));
    }
    Ok(found)
}

/// Writes `bytes` as `name` into KORG/blechtribe/`folder` on the card `root`, one of `roots`; blechtribe and `folder`
/// are made when they are missing, a file of that name there is replaced. Gives the full path written.
pub fn write(
    roots: &[PathBuf],
    root: &str,
    folder: &str,
    name: &str,
    bytes: &[u8],
) -> Result<String, String> {
    let ending = ending_of(folder)?;
    if !plain_name(name, ending) {
        return Err(format!("{name} ist kein Dateiname für {folder}."));
    }
    if bytes.is_empty() || bytes.len() > LIMIT {
        return Err(format!("{name} ist zu groß oder leer."));
    }
    let root = roots
        .iter()
        .find(|r| r.as_os_str() == OsStr::new(root))
        .ok_or("Diese Karte ist nicht mehr da.")?;
    let korg = child(root, "KORG").ok_or("Auf der Karte fehlt der Ordner KORG.")?;
    let dir = folder_in(&folder_in(&korg, "blechtribe")?, folder)?;
    let file = dir.join(name);
    if fs::symlink_metadata(&file).is_ok_and(|m| !m.is_file()) {
        return Err(format!("{} ist keine Datei.", file.display()));
    }
    let mut out = fs::File::create(&file)
        .map_err(|e| format!("{} ließ sich nicht schreiben: {e}", file.display()))?;
    out.write_all(bytes)
        .and_then(|_| out.sync_all())
        .map_err(|e| format!("{} ließ sich nicht schreiben: {e}", file.display()))?;
    Ok(file.display().to_string())
}

fn allow(window: &WebviewWindow) -> Result<(), String> {
    let address = window.url().map_err(|e| e.to_string())?;
    if !trusted_origin(window.label(), address.as_str()) {
        return Err("Nur das lokale Hauptfenster darf auf die Karte schreiben.".into());
    }
    Ok(())
}

/// The mounted volumes with a KORG folder. Reads only.
#[tauri::command]
pub async fn blech_cards(window: WebviewWindow) -> Result<Vec<Card>, String> {
    allow(&window)?;
    tauri::async_runtime::spawn_blocking(|| cards(&mounted()))
        .await
        .map_err(|e| e.to_string())
}

/// Writes one file into KORG/blechtribe/`folder` on the card `root` (one blech_cards named); the full path written.
#[tauri::command]
pub async fn blech_card_write(
    window: WebviewWindow,
    root: String,
    folder: String,
    name: String,
    bytes: Vec<u8>,
) -> Result<String, String> {
    allow(&window)?;
    tauri::async_runtime::spawn_blocking(move || write(&mounted(), &root, &folder, &name, &bytes))
        .await
        .map_err(|e| e.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn volume(name: &str) -> PathBuf {
        static N: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir()
            .join(format!(
                "gelumpe-blech-card-{}-{}",
                std::process::id(),
                N.fetch_add(1, Ordering::SeqCst)
            ))
            .join(name);
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn only_volumes_with_a_korg_folder_are_cards() {
        let card = volume("E2 CARD");
        fs::create_dir_all(card.join("korg/hacktribe")).unwrap();
        let stick = volume("STICK");
        let found = cards(&[card.clone(), stick]);
        assert_eq!(
            found,
            [Card {
                root: card.display().to_string(),
                volume: "E2 CARD".into()
            }]
        );
    }

    #[test]
    fn a_plugin_goes_into_the_plugin_folder_made_on_the_way() {
        let card = volume("CARD");
        fs::create_dir_all(card.join("KORG/hacktribe")).unwrap();
        let roots = [card.clone()];
        let root = card.display().to_string();
        let path = write(&roots, &root, "Plugin", "Echo_1.blech", b"one").unwrap();
        let file = card
            .join("KORG")
            .join("blechtribe")
            .join("Plugin")
            .join("Echo_1.blech");
        assert_eq!(path, file.display().to_string());
        assert_eq!(fs::read(&file).unwrap(), b"one");
        // the folder in other letters is used, and the file replaced
        fs::rename(
            card.join("KORG/blechtribe/Plugin"),
            card.join("KORG/blechtribe/plugin"),
        )
        .unwrap();
        write(&roots, &root, "Plugin", "Echo_1.blech", b"two").unwrap();
        assert_eq!(
            fs::read(card.join("KORG/blechtribe/plugin/Echo_1.blech")).unwrap(),
            b"two"
        );
    }

    #[test]
    fn nothing_outside_the_allowed_folders_and_names() {
        let card = volume("CARD");
        fs::create_dir_all(card.join("KORG")).unwrap();
        let roots = [card.clone()];
        let root = card.display().to_string();
        for (folder, name) in [
            ("System", "SYSTEM.VSB"),
            ("../x", "a.blech"),
            ("Plugin", "../a.blech"),
            ("Plugin", "a.blech/b.blech"),
            ("Plugin", "a.txt"),
            ("Plugin", ".blech"),
            ("Plugin", "seventeen_chars_x.blech"),
            ("Plugin", "a b.blech"),
        ] {
            assert!(
                write(&roots, &root, folder, name, b"x").is_err(),
                "{folder}/{name}"
            );
        }
        assert!(write(&roots, &root, "Plugin", "a.blech", b"").is_err());
        assert!(write(&roots, "/elsewhere", "Plugin", "a.blech", b"x").is_err());
        let bare = volume("BARE");
        assert!(write(
            std::slice::from_ref(&bare),
            &bare.display().to_string(),
            "Plugin",
            "a.blech",
            b"x"
        )
        .is_err());
        assert!(!bare.join("KORG").exists());
    }
}
