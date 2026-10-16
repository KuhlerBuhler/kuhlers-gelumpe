// The app is a window around site/ and a child process, the emulator service
// (tools/emu/server.py, frozen with PyInstaller into the binary `gelumpe-emu`).
// On launch it picks a free port and a fresh token, starts the service, waits
// until it answers, and opens the page with the link in the address
// (`#emu=port:token`), the same link the service prints in the browser setup.
// On quit it sends SIGTERM so the service writes the card and the flash back.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::{DialogExt, MessageDialogKind};

struct Service(Mutex<Option<Child>>);

fn free_port() -> std::io::Result<u16> {
    Ok(TcpListener::bind("127.0.0.1:0")?.local_addr()?.port())
}

fn token() -> Result<String, String> {
    const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut bytes = [0u8; 22];
    getrandom::fill(&mut bytes).map_err(|e| format!("Keine Zufallszahlen vom System: {e}"))?;
    Ok(bytes.iter().map(|b| ALPHABET[(*b & 63) as usize] as char).collect())
}

/// The frozen service next to the app binary; without it (cargo tauri dev) the
/// source tree's service run by the venv of `npm run setup:emu`.
fn service_command() -> Result<Command, String> {
    let exe = std::env::current_exe().map_err(|e| format!("Der Pfad der App ist unbekannt: {e}"))?;
    let dir = exe.parent().ok_or("Der Ordner der App ist unbekannt.")?;
    let name = if cfg!(windows) { "gelumpe-emu.exe" } else { "gelumpe-emu" };
    let frozen = dir.join(name);
    if frozen.exists() {
        return Ok(Command::new(frozen));
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
    let venv = root.join("tools/emu/.venv").join(if cfg!(windows) { "Scripts/python.exe" } else { "bin/python" });
    let mut cmd = Command::new(if venv.exists() { venv } else { PathBuf::from("python3") });
    cmd.arg(root.join("tools/emu/server.py"));
    Ok(cmd)
}

fn start_service(port: u16, token: &str) -> Result<Child, String> {
    let mut cmd = service_command()?;
    cmd.arg("--port").arg(port.to_string())
        .arg("--allow-origin").arg("tauri://localhost")
        .arg("--allow-origin").arg("http://tauri.localhost")
        .arg("--allow-origin").arg("https://tauri.localhost")
        .arg("--parent-pid").arg(std::process::id().to_string())
        .env("E2_EMU_TOKEN", token);
    cmd.spawn().map_err(|e| format!("Der Emulator-Dienst ließ sich nicht starten: {e}"))
}

fn wait_for(port: u16, child: &mut Child) -> Result<(), String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let deadline = Instant::now() + Duration::from_secs(60);
    while Instant::now() < deadline {
        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!("Der Emulator-Dienst ist beendet ({status}). Läuft schon eine andere Instanz auf demselben Kartenordner?"));
        }
        if TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Err("Der Emulator-Dienst antwortet nicht.".into())
}

/// Where a running service announces itself: next to the card folder's lock.
fn announce_file() -> Option<PathBuf> {
    let root = match std::env::var_os("GELUMPE_SD_DIR") {
        Some(dir) if !dir.is_empty() => PathBuf::from(dir),
        _ => PathBuf::from(std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })?).join(".gelumpe").join("sd"),
    };
    Some(root.join("service.json"))
}

/// Port and token of a service somebody else started (`npm start`, `npm run
/// emu`), only when it is alive: the file names a living pid and /status
/// answers with that token. A stale file (the service crashed) finds nothing.
fn running_service() -> Option<(u16, String)> {
    let info: serde_json::Value = serde_json::from_slice(&std::fs::read(announce_file()?).ok()?).ok()?;
    let port = u16::try_from(info.get("port")?.as_u64()?).ok()?;
    let token = info.get("token")?.as_str()?.to_string();
    if !token.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_') {
        return None;
    }
    let mut stream = TcpStream::connect_timeout(&SocketAddr::from(([127, 0, 0, 1], port)), Duration::from_millis(500)).ok()?;
    stream.set_read_timeout(Some(Duration::from_secs(2))).ok()?;
    let request = format!("GET /status HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nX-Emu-Token: {token}\r\n\r\n");
    stream.write_all(request.as_bytes()).ok()?;
    let mut answer = String::new();
    stream.read_to_string(&mut answer).ok()?;
    (answer.starts_with("HTTP/1.0 200") || answer.starts_with("HTTP/1.1 200")).then_some((port, token))
}

/// Ask the service to stop (it saves the card and the flash on SIGTERM), kill
/// it only when it does not leave in time.
fn stop_service(mut child: Child) {
    #[cfg(unix)]
    unsafe {
        libc::kill(child.id() as i32, libc::SIGTERM);
    }
    #[cfg(not(unix))]
    let _ = child.kill();
    let deadline = Instant::now() + Duration::from_secs(15);
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    let _ = child.kill();
    let _ = child.wait();
}

fn open_in_browser(url: &str) {
    let _ = if cfg!(target_os = "macos") {
        Command::new("open").arg(url).spawn()
    } else if cfg!(windows) {
        Command::new("rundll32").args(["url.dll,FileProtocolHandler", url]).spawn()
    } else {
        Command::new("xdg-open").arg(url).spawn()
    };
}

/// Start (or find) the service and open the window. Any failure comes back
/// as text for a dialog; nothing in here panics.
fn open_app(app: &tauri::App) -> Result<(), String> {
    let (port, token) = match running_service() {
        // Somebody else's service: show it, and never stop it.
        Some(found) => found,
        None => {
            let port = free_port().map_err(|e| format!("Kein freier Port: {e}"))?;
            let token = token()?;
            let mut child = start_service(port, &token)?;
            if let Err(message) = wait_for(port, &mut child) {
                stop_service(child);
                return Err(message);
            }
            app.manage(Service(Mutex::new(Some(child))));
            (port, token)
        }
    };
    let version = app.package_info().version.to_string();
    WebviewWindowBuilder::new(app, "main", WebviewUrl::App(format!("index.html#emu={port}:{token}").into()))
        // The page shows "Neue Version verfügbar" only when it knows its version.
        .initialization_script(format!("window.__GELUMPE_APP = {{ version: \"{version}\" }};"))
        // A link to the release page or the donate page opens in the browser, not in this window.
        .on_navigation(|url| {
            if url.scheme() == "https" && matches!(url.host_str(), Some("github.com") | Some("www.paypal.me")) {
                open_in_browser(url.as_str());
                return false;
            }
            true
        })
        .title("Kuhler's GELUMPE")
        .inner_size(1280.0, 860.0)
        .min_inner_size(900.0, 600.0)
        .build()
        .map_err(|e| format!("Das Fenster ließ sich nicht öffnen: {e}"))?;
    Ok(())
}

fn main() {
    let built = tauri::Builder::default()
        // A second launch focuses the window of the first and leaves.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            if let Err(message) = open_app(app) {
                let handle = app.handle().clone();
                app.dialog()
                    .message(message)
                    .title("Kuhler's GELUMPE")
                    .kind(MessageDialogKind::Error)
                    .show(move |_| handle.exit(1));
            }
            Ok(())
        })
        .build(tauri::generate_context!());
    let app = match built {
        Ok(app) => app,
        Err(error) => {
            eprintln!("Die App ließ sich nicht aufbauen: {error}");
            std::process::exit(1);
        }
    };

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            // Only a service this app started itself is stopped.
            if let Some(service) = handle.try_state::<Service>() {
                let child = service.0.lock().ok().and_then(|mut slot| slot.take());
                if let Some(child) = child {
                    stop_service(child);
                }
            }
        }
    });
}
