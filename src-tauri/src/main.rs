// The app is a window around site/ and a child process, the emulator service
// (tools/emu/server.py, frozen with PyInstaller into the binary `Gelumpe Emulator`).
// On launch it picks a free port and a fresh token, starts the service, waits
// until it answers, and opens the page with the link in the address
// (`#emu=port:token`), the same link the service prints in the browser setup.
// On quit it sends SIGTERM so the service writes the card and the flash back.
// While the app runs, a watchdog starts the service again on the same port and
// token when it ends, so the page reconnects by itself.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use kuhlers_gelumpe::midi::{self, Config as MidiConfig, MidiService, NativeDriver};
use tauri::webview::{NewWindowResponse, PageLoadEvent};
use tauri::{
    AppHandle, Manager, RunEvent, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_dialog::{DialogExt, MessageDialogKind};

/// The service this app started, if any. `quitting` keeps the watchdog from starting it again while the app ends.
struct Service {
    child: Arc<Mutex<Option<Child>>>,
    quitting: Arc<AtomicBool>,
}

fn free_port() -> std::io::Result<u16> {
    Ok(TcpListener::bind("127.0.0.1:0")?.local_addr()?.port())
}

fn token() -> Result<String, String> {
    const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut bytes = [0u8; 22];
    getrandom::fill(&mut bytes).map_err(|e| format!("Keine Zufallszahlen vom System: {e}"))?;
    Ok(bytes
        .iter()
        .map(|b| ALPHABET[(*b & 63) as usize] as char)
        .collect())
}

/// The frozen service next to the app binary; without it (cargo tauri dev) the
/// source tree's service run by the venv of `npm run setup:emu`.
fn service_command() -> Result<Command, String> {
    let exe =
        std::env::current_exe().map_err(|e| format!("Der Pfad der App ist unbekannt: {e}"))?;
    let dir = exe.parent().ok_or("Der Ordner der App ist unbekannt.")?;
    let name = if cfg!(windows) {
        "Gelumpe Emulator.exe"
    } else {
        "Gelumpe Emulator"
    };
    let frozen = dir.join(name);
    if frozen.exists() {
        return Ok(Command::new(frozen));
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
    let venv = root.join("tools/emu/.venv").join(if cfg!(windows) {
        "Scripts/python.exe"
    } else {
        "bin/python"
    });
    let mut cmd = Command::new(if venv.exists() {
        venv
    } else {
        PathBuf::from("python3")
    });
    cmd.arg(root.join("tools/emu/server.py"));
    Ok(cmd)
}

fn start_service(port: u16, token: &str, again: bool) -> Result<Child, String> {
    let mut cmd = service_command()?;
    // The frozen service is a console program: started from a window app, Windows opens a console window
    // for it, and closing that window ends the emulator. It gets none; its output goes to the log anyway.
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.arg("--port")
        .arg(port.to_string())
        .arg("--allow-origin")
        .arg("tauri://localhost")
        .arg("--allow-origin")
        .arg("http://tauri.localhost")
        .arg("--allow-origin")
        .arg("https://tauri.localhost")
        .arg("--parent-pid")
        .arg(std::process::id().to_string())
        .env("E2_EMU_TOKEN", token);
    // What the service prints goes to ~/.gelumpe/emu.log, so a failure on a user's machine can be read afterwards.
    if let Some(log) = log_file(again) {
        if let (Ok(out), Ok(err)) = (log.try_clone(), log.try_clone()) {
            cmd.stdout(Stdio::from(out)).stderr(Stdio::from(err));
        }
    }
    cmd.spawn()
        .map_err(|e| format!("Der Emulator-Dienst ließ sich nicht starten: {e}"))
}

fn wait_for(port: u16, child: &mut Child) -> Result<(), String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let deadline = Instant::now() + Duration::from_secs(60);
    while Instant::now() < deadline {
        if let Ok(Some(status)) = child.try_wait() {
            let tail = log_tail()
                .map(|t| format!("\n\nAus ~/.gelumpe/emu.log:\n{t}"))
                .unwrap_or_default();
            return Err(format!("Der Emulator-Dienst ist beendet ({status}). Läuft schon eine andere Instanz auf demselben Kartenordner?{tail}"));
        }
        if TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Err("Der Emulator-Dienst antwortet nicht.".into())
}

fn log_path() -> Option<PathBuf> {
    Some(
        PathBuf::from(std::env::var_os(if cfg!(windows) {
            "USERPROFILE"
        } else {
            "HOME"
        })?)
        .join(".gelumpe")
        .join("emu.log"),
    )
}

/// The service's log, new at launch; a restart by the watchdog writes behind what the ended one said.
fn log_file(again: bool) -> Option<std::fs::File> {
    let path = log_path()?;
    std::fs::create_dir_all(path.parent()?).ok()?;
    std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .append(again)
        .truncate(!again)
        .open(path)
        .ok()
}

/// The last lines of the log, for the dialog when the service does not come up.
fn log_tail() -> Option<String> {
    let text = std::fs::read_to_string(log_path()?).ok()?;
    let lines: Vec<&str> = text.lines().filter(|l| !l.trim().is_empty()).collect();
    (!lines.is_empty()).then(|| lines[lines.len().saturating_sub(6)..].join("\n"))
}

/// Where a running service announces itself: next to the card folder's lock.
fn announce_file() -> Option<PathBuf> {
    let root = match std::env::var_os("GELUMPE_SD_DIR") {
        Some(dir) if !dir.is_empty() => PathBuf::from(dir),
        _ => PathBuf::from(std::env::var_os(if cfg!(windows) {
            "USERPROFILE"
        } else {
            "HOME"
        })?)
        .join(".gelumpe")
        .join("sd"),
    };
    Some(root.join("service.json"))
}

/// Port and token of a service somebody else started (`npm start`, `npm run
/// emu`), only when it is alive: the file names a living pid and /status
/// answers with that token. A stale file (the service crashed) finds nothing.
fn running_service() -> Option<(u16, String)> {
    let info: serde_json::Value =
        serde_json::from_slice(&std::fs::read(announce_file()?).ok()?).ok()?;
    let port = u16::try_from(info.get("port")?.as_u64()?).ok()?;
    let token = info.get("token")?.as_str()?.to_string();
    if !token
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return None;
    }
    answers(port, &token).then_some((port, token))
}

/// Whether a service on `port` answers /status for `token`.
fn answers(port: u16, token: &str) -> bool {
    let ask = || -> Option<bool> {
        let mut stream = TcpStream::connect_timeout(
            &SocketAddr::from(([127, 0, 0, 1], port)),
            Duration::from_millis(500),
        )
        .ok()?;
        stream.set_read_timeout(Some(Duration::from_secs(2))).ok()?;
        let request = format!(
            "GET /status HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nX-Emu-Token: {token}\r\n\r\n"
        );
        stream.write_all(request.as_bytes()).ok()?;
        let mut answer = String::new();
        stream.read_to_string(&mut answer).ok()?;
        Some(answer.starts_with("HTTP/1.0 200") || answer.starts_with("HTTP/1.1 200"))
    };
    ask().unwrap_or(false)
}

/// Keeps a service on `port` with `token` for as long as the app runs: when the one this app started ends,
/// or the one somebody else started stops answering, it starts its own there again. Waits 1 s before the
/// first try and doubles up to 30 s while starts keep failing; a service that ran for a minute resets that.
fn watchdog(port: u16, token: String, child: Arc<Mutex<Option<Child>>>, quitting: Arc<AtomicBool>) {
    std::thread::spawn(move || {
        let mut pause = Duration::from_secs(1);
        let mut since = Instant::now();
        let mut silent = 0;
        loop {
            std::thread::sleep(Duration::from_secs(1));
            if quitting.load(Ordering::SeqCst) {
                return;
            }
            let gone = {
                let Ok(mut slot) = child.lock() else { return };
                match slot.as_mut() {
                    Some(own) => match own.try_wait() {
                        Ok(Some(status)) => {
                            eprintln!("Emulator-Dienst beendet ({status}), starte neu.");
                            *slot = None;
                            true
                        }
                        _ => false,
                    },
                    // Somebody else's service: twice no answer and it is gone.
                    None => {
                        silent = if answers(port, &token) { 0 } else { silent + 1 };
                        silent >= 2
                    }
                }
            };
            if !gone {
                if since.elapsed() > Duration::from_secs(60) {
                    pause = Duration::from_secs(1);
                }
                continue;
            }
            std::thread::sleep(pause);
            if quitting.load(Ordering::SeqCst) {
                return;
            }
            match start_service(port, &token, true) {
                Ok(mut started) => {
                    let up = wait_for(port, &mut started).is_ok();
                    let Ok(mut slot) = child.lock() else { return };
                    *slot = Some(started);
                    if up {
                        silent = 0;
                    }
                }
                Err(e) => eprintln!("{e}"),
            }
            since = Instant::now();
            pause = (pause * 2).min(Duration::from_secs(30));
        }
    });
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
        Command::new("rundll32")
            .args(["url.dll,FileProtocolHandler", url])
            .spawn()
    } else {
        Command::new("xdg-open").arg(url).spawn()
    };
}

/// Pages that open in the browser instead of a window of this app: releases, donations, Korg's firmware downloads, Instagram for help.
fn outside(url: &Url) -> bool {
    url.scheme() == "https"
        && matches!(
            url.host_str(),
            Some("github.com")
                | Some("www.paypal.me")
                | Some("www.korg.com")
                | Some("www.instagram.com")
        )
}

/// The page closes the emulator window by navigating here (site/app/emu-window.mjs); WebKit has no window.close() for it.
const CLOSE_HOST: &str = "close.gelumpe.invalid";
const EMULATOR: &str = "emulator";

/// window.open from the page: its own emulator window opens once, the outside pages go to the browser, nothing else opens.
/// Any https page counts as outside here: a creator's profile link can point anywhere, and a new window of the page is
/// only ever a link the user clicked. Navigation in place keeps the short list of `outside`.
fn new_window(
    app: &AppHandle,
    url: Url,
    features: tauri::webview::NewWindowFeatures,
) -> NewWindowResponse<tauri::Wry> {
    if outside(&url) || url.scheme() == "https" {
        open_in_browser(url.as_str());
        return NewWindowResponse::Deny;
    }
    if !url.path().ends_with("/emulator.html") {
        return NewWindowResponse::Deny;
    }
    if let Some(window) = app.get_webview_window(EMULATOR) {
        let _ = window.set_focus();
        return NewWindowResponse::Deny;
    }
    let handle = app.clone();
    let built = WebviewWindowBuilder::new(
        app,
        EMULATOR,
        WebviewUrl::External("about:blank".parse().unwrap()),
    )
    .window_features(features)
    .on_navigation(move |url| {
        if url.host_str() == Some(CLOSE_HOST) {
            if let Some(window) = handle.get_webview_window(EMULATOR) {
                let _ = window.close();
            }
            return false;
        }
        true
    })
    .title("Emulator · Kuhler's GELUMPE")
    .min_inner_size(600.0, 360.0)
    .build();
    match built {
        Ok(window) => NewWindowResponse::Create { window },
        Err(_) => NewWindowResponse::Deny,
    }
}

/// Where the main window stood and how large it was, in logical pixels, kept between starts in the app's config folder.
/// Without a saved one (the first start) the window opens maximized.
#[derive(Clone, Copy)]
struct Placement {
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    maximized: bool,
}

/// The placement of this run, followed while the window moves and written when it closes or the app quits.
struct Placed(Mutex<Option<Placement>>);

fn placement_file(app: &AppHandle) -> Option<PathBuf> {
    app.path()
        .app_config_dir()
        .ok()
        .map(|dir| dir.join("window.json"))
}

fn load_placement(app: &AppHandle) -> Option<Placement> {
    let v: serde_json::Value =
        serde_json::from_slice(&std::fs::read(placement_file(app)?).ok()?).ok()?;
    let n = |k: &str| v.get(k).and_then(|x| x.as_f64());
    Some(Placement {
        x: n("x")?,
        y: n("y")?,
        w: n("w")?,
        h: n("h")?,
        maximized: v.get("maximized")?.as_bool()?,
    })
}

fn save_placement(app: &AppHandle) {
    let Some(p) = app
        .try_state::<Placed>()
        .and_then(|placed| *placed.0.lock().ok()?)
    else {
        return;
    };
    let Some(file) = placement_file(app) else {
        return;
    };
    let _ = std::fs::create_dir_all(file.parent().unwrap_or(&file));
    let json =
        serde_json::json!({ "x": p.x, "y": p.y, "w": p.w, "h": p.h, "maximized": p.maximized });
    let _ = std::fs::write(file, json.to_string());
}

/// The window's place now. While it is maximized the size it had before stays, so un-maximizing after a restart finds it.
fn follow_placement(window: &WebviewWindow) {
    let Some(placed) = window.try_state::<Placed>() else {
        return;
    };
    let Ok(mut slot) = placed.0.lock() else {
        return;
    };
    let maximized = window.is_maximized().unwrap_or(false);
    if maximized {
        if let Some(p) = slot.as_mut() {
            p.maximized = true;
            return;
        }
    }
    let scale = window.scale_factor().unwrap_or(1.0);
    let (Ok(at), Ok(size)) = (window.outer_position(), window.inner_size()) else {
        return;
    };
    let (at, size) = (at.to_logical::<f64>(scale), size.to_logical::<f64>(scale));
    *slot = Some(Placement {
        x: at.x,
        y: at.y,
        w: size.width,
        h: size.height,
        maximized,
    });
}

/// True when the top left corner of a saved place lies on a screen that is still there.
fn on_a_screen(app: &AppHandle, p: &Placement) -> bool {
    app.available_monitors()
        .unwrap_or_default()
        .iter()
        .any(|m| {
            let scale = m.scale_factor();
            let (at, size) = (
                m.position().to_logical::<f64>(scale),
                m.size().to_logical::<f64>(scale),
            );
            p.x + 40.0 >= at.x
                && p.x + 40.0 < at.x + size.width
                && p.y + 20.0 >= at.y
                && p.y + 20.0 < at.y + size.height
        })
}

/// Start (or find) the service and open the window. Any failure comes back
/// as text for a dialog; nothing in here panics.
fn open_app(app: &tauri::App) -> Result<(), String> {
    let (port, token, own) = match running_service() {
        // Somebody else's service: show it, and never stop it.
        Some((port, token)) => (port, token, None),
        None => {
            let port = free_port().map_err(|e| format!("Kein freier Port: {e}"))?;
            let token = token()?;
            let mut child = start_service(port, &token, false)?;
            if let Err(message) = wait_for(port, &mut child) {
                stop_service(child);
                return Err(message);
            }
            (port, token, Some(child))
        }
    };
    let service = Service {
        child: Arc::new(Mutex::new(own)),
        quitting: Arc::new(AtomicBool::new(false)),
    };
    watchdog(
        port,
        token.clone(),
        service.child.clone(),
        service.quitting.clone(),
    );
    app.manage(service);
    let version = app.package_info().version.to_string();
    let native_midi = cfg!(any(target_os = "macos", target_os = "linux"));
    let saved = load_placement(app.handle());
    app.manage(Placed(Mutex::new(saved)));
    let handle = app.handle().clone();
    let mut builder = WebviewWindowBuilder::new(
        app,
        "main",
        WebviewUrl::App(format!("index.html#emu={port}:{token}").into()),
    )
    // The page shows "Neue Version verfügbar" only when it knows its version.
    .initialization_script(format!(
        "window.__GELUMPE_APP = {{ version: \"{version}\", nativeMidi: {native_midi} }};"
    ))
    // A link to the release page or the donate page opens in the browser, not in this window.
    .on_navigation(|url| {
        if outside(url) {
            open_in_browser(url.as_str());
            return false;
        }
        true
    })
    .on_new_window(move |url, features| new_window(&handle, url, features))
    .on_page_load(|window, payload| {
        if let Some(midi) = window.try_state::<MidiService>() {
            match payload.event() {
                PageLoadEvent::Started => midi.invalidate(),
                PageLoadEvent::Finished => midi.document_loaded(),
            }
        }
    })
    .title("Kuhler's GELUMPE")
    .inner_size(1280.0, 860.0)
    .min_inner_size(900.0, 600.0);
    match saved {
        Some(p) => {
            builder = builder
                .inner_size(p.w.max(900.0), p.h.max(600.0))
                .maximized(p.maximized);
            if on_a_screen(app.handle(), &p) {
                builder = builder.position(p.x, p.y);
            }
        }
        None => builder = builder.maximized(true),
    }
    let window = builder
        .build()
        .map_err(|e| format!("Das Fenster ließ sich nicht öffnen: {e}"))?;
    // The emulator window belongs to the main one and goes with it.
    let handle = app.handle().clone();
    let followed = window.clone();
    window.on_window_event(move |event| {
        if let WindowEvent::Moved(_) | WindowEvent::Resized(_) = event {
            follow_placement(&followed);
        }
        if let WindowEvent::CloseRequested { .. } = event {
            save_placement(&handle);
        }
        if let WindowEvent::Destroyed = event {
            if let Some(midi) = handle.try_state::<MidiService>() {
                midi.invalidate();
            }
            if let Some(emulator) = handle.get_webview_window(EMULATOR) {
                let _ = emulator.close();
            }
        }
    });
    Ok(())
}

fn main() {
    let built = tauri::Builder::default()
        .manage(MidiService::new(
            Arc::new(NativeDriver),
            MidiConfig::default(),
        ))
        .invoke_handler(tauri::generate_handler![
            midi::midi_list,
            midi::midi_open,
            midi::midi_send,
            midi::midi_ack,
            midi::midi_read,
            midi::midi_close,
            kuhlers_gelumpe::update::update_install,
            kuhlers_gelumpe::korg::korg_firmware
        ])
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
        if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
            if let Some(midi) = handle.try_state::<MidiService>() {
                midi.shutdown();
            }
            if let Some(service) = handle.try_state::<Service>() {
                service.quitting.store(true, Ordering::SeqCst);
            }
        }
        if let RunEvent::Exit = event {
            // Quitting with Cmd+Q closes no window by request: the placement is written here as well.
            save_placement(handle);
            // Only a service this app started itself is stopped.
            if let Some(service) = handle.try_state::<Service>() {
                let child = service.child.lock().ok().and_then(|mut slot| slot.take());
                if let Some(child) = child {
                    stop_service(child);
                }
            }
        }
    });
}
