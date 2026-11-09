// The Android app: the page in one window, without the emulator service and without MIDI. Patching, the pattern tools
// and the editor work on files; the page learns from `window.__GELUMPE_MOBILE` that it runs here (site/app/midi.mjs,
// site/app/save-file.mjs).
use std::io::Write;
use std::sync::Arc;

use tauri::ipc::{InvokeBody, Request};
use tauri::{AppHandle, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_fs::{FsExt, OpenOptions};

use crate::midi::{self, trusted_origin, Config as MidiConfig, MidiService, NativeDriver};

/// `%XX` back to bytes; the page sends the file name URI-encoded because a header carries ASCII only.
fn decode(text: &str) -> String {
    let raw = text.as_bytes();
    let mut out = Vec::with_capacity(raw.len());
    let mut i = 0;
    while i < raw.len() {
        let hex = |b: u8| (b as char).to_digit(16).map(|d| d as u8);
        match (
            raw[i],
            raw.get(i + 1).copied().and_then(hex),
            raw.get(i + 2).copied().and_then(hex),
        ) {
            (b'%', Some(hi), Some(lo)) => {
                out.push(hi << 4 | lo);
                i += 3;
            }
            (b, _, _) => {
                out.push(b);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// Every download of the page: the system's save dialog picks the place (a content URI of the Storage Access
/// Framework), the fs plugin writes it. False when the person cancels.
#[tauri::command]
async fn file_save(
    window: WebviewWindow,
    app: AppHandle,
    request: Request<'_>,
) -> Result<bool, String> {
    let address = window.url().map_err(|e| e.to_string())?;
    if !trusted_origin(window.label(), address.as_str()) {
        return Err("Nur das lokale Hauptfenster darf speichern.".into());
    }
    // A raw body where the WebView passes one; Android's IPC bridge may hand it over as a JSON array of bytes.
    let bytes: Vec<u8> = match request.body() {
        InvokeBody::Raw(bytes) => bytes.clone(),
        InvokeBody::Json(value) => serde_json::from_value(value.clone())
            .map_err(|_| "Es kam keine Datei an.".to_string())?,
    };
    let name = request
        .headers()
        .get("x-file-name")
        .and_then(|v| v.to_str().ok())
        .map(decode)
        .filter(|n| !n.is_empty() && !n.contains('/'))
        .unwrap_or_else(|| "download".into());
    tauri::async_runtime::spawn_blocking(move || {
        let Some(path) = app
            .dialog()
            .file()
            .set_file_name(&name)
            .blocking_save_file()
        else {
            return Ok(false);
        };
        let mut options = OpenOptions::new();
        options.read(false).write(true).create(true).truncate(true);
        let mut file = app
            .fs()
            .open(path, options)
            .map_err(|e| format!("{name} ließ sich nicht anlegen: {e}"))?;
        file.write_all(&bytes)
            .map_err(|e| format!("{name} ließ sich nicht schreiben: {e}"))?;
        Ok(true)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::mobile_entry_point]
pub fn run() {
    tauri::Builder::default()
        .manage(MidiService::new(
            Arc::new(NativeDriver),
            MidiConfig::default(),
        ))
        .manage(crate::card::CardRoot::default())
        .invoke_handler(tauri::generate_handler![
            midi::midi_list,
            midi::midi_open,
            midi::midi_send,
            midi::midi_ack,
            midi::midi_read,
            midi::midi_close,
            crate::korg::korg_firmware,
            crate::card::card_pick,
            crate::card::card_list,
            crate::card::card_read,
            crate::card::card_exists,
            crate::card::card_move,
            file_save
        ])
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            let version = app.package_info().version.to_string();
            WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .initialization_script(format!(
                    "window.__GELUMPE_MOBILE = {{ version: \"{version}\", platform: \"android\" }};"
                ))
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Die App ließ sich nicht starten.");
}
