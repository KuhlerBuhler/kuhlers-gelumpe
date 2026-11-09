//! Where the Patcher puts the new SYSTEM.VSB in the app (site/app/save-target.mjs). The page names the folder the firmware
//! on the device reads ("KORG/electribe sampler/System/"); the app looks for that KORG folder on every mounted card and
//! writes the file only into its System folder, or where the person points in the save dialog. The page never names a
//! path of its own: a card is one the app found itself, the folder one of the four a firmware reads.

use std::ffi::OsStr;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::Serialize;
use tauri::{AppHandle, WebviewWindow};
use tauri_plugin_dialog::DialogExt;

use crate::card::child;
use crate::midi::trusted_origin;

/// The folders below KORG/ a firmware reads SYSTEM.VSB from (FOLDER and BLECH_FOLDER in src/patcher.mjs).
const FOLDERS: [&str; 4] = ["electribe sampler", "electribe", "hacktribe", "blechtribe"];
const FILE: &str = "SYSTEM.VSB";
/// A SYSTEM.VSB has 2,097,408 bytes; nothing far larger is written.
const LIMIT: usize = 4 << 20;

/// A mounted card with the KORG folder of the goal: the card's top folder (given back to save_card), the name to show,
/// the full place of the new file, and whether its System folder and a SYSTEM.VSB are there already.
#[derive(Serialize, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Candidate {
    pub root: String,
    pub volume: String,
    pub path: String,
    pub system_exists: bool,
    pub vsb_exists: bool,
}

/// The folder below KORG/ in the page's "KORG/<folder>/System/"; an error for any other.
pub fn folder_of(target: &str) -> Result<&'static str, String> {
    let name = target
        .strip_prefix("KORG/")
        .and_then(|rest| rest.strip_suffix("/System/"));
    name.and_then(|name| FOLDERS.iter().find(|f| **f == name).copied())
        .ok_or(format!("{target} ist kein Ordner einer Firmware."))
}

/// The folders below `dir` that are not links and not hidden.
#[cfg(unix)]
fn folders_in(dir: &Path) -> Vec<PathBuf> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    entries
        .flatten()
        .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
        .filter(|e| !e.file_name().to_string_lossy().starts_with('.'))
        .map(|e| e.path())
        .collect()
}

/// The mounted volumes a card can be: /Volumes on macOS (the start volume there is a link and left out), the drive
/// letters on Windows, the folders below /media/$USER and /run/media/$USER on Linux.
pub fn mounted() -> Vec<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        folders_in(Path::new("/Volumes"))
    }
    #[cfg(windows)]
    {
        // A: and B: are the old floppy letters; asking them can stall
        (b'C'..=b'Z')
            .map(|c| PathBuf::from(format!("{}:\\", c as char)))
            .filter(|p| p.is_dir())
            .collect()
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let user = std::env::var("USER").unwrap_or_default();
        if user.is_empty() {
            return Vec::new();
        }
        let mut out = folders_in(&Path::new("/media").join(&user));
        out.extend(folders_in(&Path::new("/run/media").join(&user)));
        out
    }
}

fn taken(path: &Path) -> bool {
    fs::symlink_metadata(path).is_ok()
}

fn volume_name(root: &Path) -> String {
    root.file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| root.display().to_string())
}

/// The cards in `roots` that have KORG/`folder` (any letters, no links).
pub fn candidates(roots: &[PathBuf], folder: &str) -> Vec<Candidate> {
    roots
        .iter()
        .filter_map(|root| {
            let dir = child(&child(root, "KORG")?, folder)?;
            let system = child(&dir, "System");
            let vsb_exists = system.as_ref().is_some_and(|s| taken(&s.join(FILE)));
            Some(Candidate {
                root: root.display().to_string(),
                volume: volume_name(root),
                path: system
                    .clone()
                    .unwrap_or_else(|| dir.join("System"))
                    .join(FILE)
                    .display()
                    .to_string(),
                system_exists: system.is_some(),
                vsb_exists,
            })
        })
        .collect()
}

fn write_file(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let mut file = fs::File::create(path)
        .map_err(|e| format!("{} ließ sich nicht schreiben: {e}", path.display()))?;
    file.write_all(bytes)
        .and_then(|_| file.sync_all())
        .map_err(|e| format!("{} ließ sich nicht schreiben: {e}", path.display()))
}

/// Writes `bytes` as SYSTEM.VSB into KORG/`folder`/System on the card `root`, one of `roots`. The System folder is made
/// when it is missing; a SYSTEM.VSB there is replaced. Nothing is written outside KORG/`folder`.
pub fn write(roots: &[PathBuf], root: &str, folder: &str, bytes: &[u8]) -> Result<String, String> {
    if !FOLDERS.contains(&folder) {
        return Err(format!("KORG/{folder} ist kein Ordner einer Firmware."));
    }
    let root = roots
        .iter()
        .find(|r| r.as_os_str() == OsStr::new(root))
        .ok_or("Diese Karte ist nicht mehr da.")?;
    let korg = child(root, "KORG").ok_or("Auf der Karte fehlt der Ordner KORG.")?;
    let dir = child(&korg, folder).ok_or(format!("Auf der Karte fehlt KORG/{folder}."))?;
    let system = match child(&dir, "System") {
        Some(found) => found,
        None => {
            let made = dir.join("System");
            fs::create_dir(&made)
                .map_err(|e| format!("Den Ordner System konnte ich nicht anlegen: {e}"))?;
            made
        }
    };
    let real_dir = dir.canonicalize().map_err(|e| e.to_string())?;
    let real_system = system.canonicalize().map_err(|e| e.to_string())?;
    if real_system.parent() != Some(real_dir.as_path()) {
        return Err(format!("KORG/{folder}/System liegt nicht auf der Karte."));
    }
    let file = system.join(FILE);
    if fs::symlink_metadata(&file).is_ok_and(|m| !m.is_file()) {
        return Err(format!("{} ist keine Datei.", file.display()));
    }
    write_file(&file, bytes)?;
    Ok(file.display().to_string())
}

fn allow(window: &WebviewWindow) -> Result<(), String> {
    let address = window.url().map_err(|e| e.to_string())?;
    if !trusted_origin(window.label(), address.as_str()) {
        return Err("Nur das lokale Hauptfenster darf Dateien speichern.".into());
    }
    Ok(())
}

fn sized(bytes: &[u8]) -> Result<(), String> {
    if bytes.is_empty() || bytes.len() > LIMIT {
        return Err("Das ist keine SYSTEM.VSB.".into());
    }
    Ok(())
}

/// The mounted cards with the KORG folder of `target` ("KORG/<folder>/System/"). Reads only.
#[tauri::command]
pub async fn save_cards(window: WebviewWindow, target: String) -> Result<Vec<Candidate>, String> {
    allow(&window)?;
    let folder = folder_of(&target)?;
    tauri::async_runtime::spawn_blocking(move || candidates(&mounted(), folder))
        .await
        .map_err(|e| e.to_string())
}

/// Writes the file onto the card `root` (one save_cards named) into `target`; the full path written.
#[tauri::command]
pub async fn save_card(
    window: WebviewWindow,
    root: String,
    target: String,
    bytes: Vec<u8>,
) -> Result<String, String> {
    allow(&window)?;
    sized(&bytes)?;
    let folder = folder_of(&target)?;
    tauri::async_runtime::spawn_blocking(move || write(&mounted(), &root, folder, &bytes))
        .await
        .map_err(|e| e.to_string())?
}

/// Opens the save dialog with `name` filled in and writes the file where the person points; the full path, or None
/// when the person cancels.
#[tauri::command]
pub async fn save_pick(
    window: WebviewWindow,
    app: AppHandle,
    name: String,
    bytes: Vec<u8>,
) -> Result<Option<String>, String> {
    allow(&window)?;
    sized(&bytes)?;
    if name.is_empty() || name.contains(['/', '\\', ':', '\0']) {
        return Err(format!("{name} ist kein Dateiname."));
    }
    tauri::async_runtime::spawn_blocking(move || {
        let Some(picked) = app
            .dialog()
            .file()
            .set_file_name(&name)
            .blocking_save_file()
        else {
            return Ok(None);
        };
        let path = picked.into_path().map_err(|e| e.to_string())?;
        write_file(&path, &bytes)?;
        Ok(Some(path.display().to_string()))
    })
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
                "gelumpe-save-{}-{}",
                std::process::id(),
                N.fetch_add(1, Ordering::SeqCst)
            ))
            .join(name);
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn put(root: &Path, rel: &str, bytes: &[u8]) {
        let path = root.join(rel);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, bytes).unwrap();
    }

    #[test]
    fn only_the_folders_of_a_firmware() {
        assert_eq!(
            folder_of("KORG/electribe sampler/System/").unwrap(),
            "electribe sampler"
        );
        assert_eq!(folder_of("KORG/blechtribe/System/").unwrap(), "blechtribe");
        for bad in [
            "KORG/../System/",
            "KORG/other/System/",
            "KORG/electribe/",
            "/etc/System/",
            "",
        ] {
            assert!(folder_of(bad).is_err(), "{bad}");
        }
        let card = volume("CARD");
        fs::create_dir_all(card.join("KORG/other")).unwrap();
        assert!(write(
            std::slice::from_ref(&card),
            &card.display().to_string(),
            "other",
            b"x"
        )
        .is_err());
        assert!(!card.join("KORG/other/System").exists());
    }

    #[test]
    fn finds_the_card_with_its_system_folder_and_file() {
        let card = volume("E2 CARD");
        put(&card, "KORG/hacktribe/System/SYSTEM.VSB", b"old");
        let found = candidates(std::slice::from_ref(&card), "hacktribe");
        assert_eq!(
            found,
            [Candidate {
                root: card.display().to_string(),
                volume: "E2 CARD".into(),
                path: card
                    .join("KORG")
                    .join("hacktribe")
                    .join("System")
                    .join(FILE)
                    .display()
                    .to_string(),
                system_exists: true,
                vsb_exists: true,
            }]
        );
        assert!(candidates(&[card], "blechtribe").is_empty());
    }

    #[test]
    fn a_missing_system_folder_is_made_when_saving() {
        let card = volume("CARD");
        fs::create_dir_all(card.join("korg/Electribe Sampler")).unwrap();
        let found = candidates(std::slice::from_ref(&card), "electribe sampler");
        assert_eq!(found.len(), 1);
        assert!(!found[0].system_exists && !found[0].vsb_exists);
        let written = write(
            std::slice::from_ref(&card),
            &found[0].root,
            "electribe sampler",
            b"new",
        )
        .unwrap();
        assert_eq!(written, found[0].path);
        assert_eq!(
            fs::read(card.join("korg/Electribe Sampler/System/SYSTEM.VSB")).unwrap(),
            b"new"
        );
    }

    #[test]
    fn an_existing_file_is_replaced() {
        let card = volume("CARD");
        put(&card, "KORG/electribe/System/SYSTEM.VSB", b"old");
        let root = card.display().to_string();
        write(std::slice::from_ref(&card), &root, "electribe", b"new").unwrap();
        assert_eq!(
            fs::read(card.join("KORG/electribe/System/SYSTEM.VSB")).unwrap(),
            b"new"
        );
    }

    #[test]
    fn no_card_means_no_candidate_and_no_write() {
        let stick = volume("STICK");
        put(&stick, "photos/a.jpg", b"x");
        let empty = volume("EMPTY");
        assert!(candidates(&[stick.clone(), empty], "blechtribe").is_empty());
        assert!(candidates(&[], "blechtribe").is_empty());
        let root = stick.display().to_string();
        assert!(write(std::slice::from_ref(&stick), &root, "blechtribe", b"x").is_err());
        assert!(!stick.join("KORG").exists());
        let other = volume("OTHER");
        fs::create_dir_all(other.join("KORG/blechtribe")).unwrap();
        assert!(
            write(&[stick], &other.display().to_string(), "blechtribe", b"x").is_err(),
            "only a card the app found itself"
        );
        assert!(!other.join("KORG/blechtribe/System").exists());
    }

    #[test]
    fn several_cards_are_all_offered() {
        let a = volume("A");
        let b = volume("B");
        let c = volume("C");
        fs::create_dir_all(a.join("KORG/blechtribe/System")).unwrap();
        fs::create_dir_all(b.join("KORG/blechtribe")).unwrap();
        fs::create_dir_all(c.join("KORG/hacktribe")).unwrap();
        let found = candidates(&[a, b.clone(), c], "blechtribe");
        assert_eq!(
            found.iter().map(|f| f.volume.as_str()).collect::<Vec<_>>(),
            ["A", "B"]
        );
        write(
            std::slice::from_ref(&b),
            &b.display().to_string(),
            "blechtribe",
            b"new",
        )
        .unwrap();
        assert!(b.join("KORG/blechtribe/System/SYSTEM.VSB").is_file());
    }

    #[cfg(unix)]
    #[test]
    fn links_out_of_the_korg_folder_are_not_followed() {
        let card = volume("CARD");
        let outside = volume("OUTSIDE");
        fs::create_dir_all(card.join("KORG/blechtribe")).unwrap();
        std::os::unix::fs::symlink(&outside, card.join("KORG/blechtribe/System")).unwrap();
        let root = card.display().to_string();
        assert!(write(std::slice::from_ref(&card), &root, "blechtribe", b"x").is_err());
        assert!(!outside.join(FILE).exists());
        let linked = volume("LINKED");
        fs::create_dir_all(&linked).unwrap();
        std::os::unix::fs::symlink(card.join("KORG"), linked.join("KORG")).unwrap();
        assert!(candidates(&[linked], "blechtribe").is_empty());
    }
}
