//! Korg's System Updater 2.02 for the Patcher page, after the user accepted Korg's licence there: the zip comes straight
//! from Korg's server to this computer and goes to the page as bytes. Korg's server sends no CORS header, so the page
//! itself cannot fetch it; the browser version only links it. Nothing is stored and nothing goes through a server of ours.
//! The page takes SYSTEM.VSB out of the zip and checks its SHA-256 (src/zip.mjs, src/patcher.mjs).

use std::io::Read;
use std::time::Duration;

use tauri::{ipc::Response, WebviewWindow};

use crate::midi::trusted_origin;

/// The zip of Korg's System Updater 2.02 per Electribe, on Korg's download server (the same files as Korg's support pages).
pub fn url(device: &str) -> Option<&'static str> {
    match device {
        "red" => Some("https://cdn.korg.com/us/support/download/files/0b87bcd3112fbb8c0ad7b0f55e618837.zip?response-content-disposition=attachment%3Bfilename%2A%3DUTF-8%27%27electribe_sampler_system_v202.zip&response-content-type=application%2Foctet-stream%3B"),
        "blue" => Some("https://cdn.korg.com/us/support/download/files/89f5b5eb14071e3456ceedd534618d8a.zip?response-content-disposition=attachment%3Bfilename%2A%3DUTF-8%27%27electribe_system_v202.zip&response-content-type=application%2Foctet-stream%3B"),
        _ => None,
    }
}

/// The zips are under a megabyte; anything far larger is not Korg's updater.
const LIMIT: u64 = 8 << 20;

fn fetch(url: &str) -> Result<Vec<u8>, String> {
    let response = ureq::AgentBuilder::new()
        .user_agent("kuhlers-gelumpe")
        .timeout_connect(Duration::from_secs(15))
        .timeout_read(Duration::from_secs(30))
        .build()
        .get(url)
        .call()
        .map_err(|e| format!("Korgs Server antwortet nicht: {e}"))?;
    let mut bytes = Vec::new();
    response
        .into_reader()
        .take(LIMIT + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| format!("Der Download brach ab: {e}"))?;
    if bytes.len() as u64 > LIMIT {
        return Err("Die Datei von Korg ist größer als erwartet.".into());
    }
    Ok(bytes)
}

/// The zip of Korg's 2.02 for `device` ("red" or "blue"). Only the local main window may ask.
#[tauri::command]
pub async fn korg_firmware(window: WebviewWindow, device: String) -> Result<Response, String> {
    let address = window.url().map_err(|e| e.to_string())?;
    if !trusted_origin(window.label(), address.as_str()) {
        return Err("Nur das lokale Hauptfenster darf Korgs Firmware laden.".into());
    }
    let url = url(&device).ok_or("Unbekannte Electribe.")?;
    let bytes = tauri::async_runtime::spawn_blocking(move || fetch(url))
        .await
        .map_err(|e| e.to_string())??;
    Ok(Response::new(bytes))
}

#[cfg(test)]
mod tests {
    use super::url;

    #[test]
    fn only_the_two_electribes_have_a_download_on_korgs_server() {
        for device in ["red", "blue"] {
            assert!(url(device).unwrap().starts_with("https://cdn.korg.com/"));
        }
        assert!(url("other").is_none());
    }
}
