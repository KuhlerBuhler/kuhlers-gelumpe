//! "Neue Version verfügbar", the second half: the page found a newer release and the user pressed the button.
//! This command downloads the file that fits this system into the Downloads folder, reports the progress to the
//! page and starts the installation. Any failure comes back as text; the page then opens the release page instead.

use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{ipc::Channel, AppHandle, Manager, WebviewWindow};

use crate::midi::trusted_origin;

const REPO: &str = "KuhlerBuhler/kuhlers-gelumpe";

/// What the page hears while the command runs.
#[derive(Clone, Serialize)]
#[serde(tag = "stage", rename_all = "camelCase")]
pub enum Progress {
    #[serde(rename_all = "camelCase")]
    Download {
        received: u64,
        total: Option<u64>,
    },
    Install,
}

/// The release file this system needs, as Tauri names it: `<productName>_<version>_<arch>[-setup].<ext>`
/// (tools/release-lib.mjs, TARGETS). GitHub turns the spaces of the product name into dots, so only the end counts.
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub struct Wanted {
    arch: &'static str,
    ext: &'static str,
    setup: bool,
}

/// `os` and `arch` as `std::env::consts` spells them; `appimage` tells a Linux AppImage from a .deb install.
pub fn wanted(os: &str, arch: &str, appimage: bool) -> Option<Wanted> {
    match (os, arch) {
        ("macos", "aarch64") => Some(Wanted {
            arch: "aarch64",
            ext: "dmg",
            setup: false,
        }),
        ("macos", "x86_64") => Some(Wanted {
            arch: "x64",
            ext: "dmg",
            setup: false,
        }),
        // Windows on ARM runs the x64 installer and app.
        ("windows", "x86_64" | "aarch64") => Some(Wanted {
            arch: "x64",
            ext: "exe",
            setup: true,
        }),
        ("linux", "x86_64") => Some(Wanted {
            arch: "amd64",
            ext: if appimage { "AppImage" } else { "deb" },
            setup: false,
        }),
        _ => None,
    }
}

/// The index of the asset of `version` that fits, from the names of a release.
pub fn pick_asset<S: AsRef<str>>(names: &[S], version: &str, want: Wanted) -> Option<usize> {
    let end = format!(
        "_{version}_{}{}.{}",
        want.arch,
        if want.setup { "-setup" } else { "" },
        want.ext
    );
    names.iter().position(|name| name.as_ref().ends_with(&end))
}

/// "v1.2.3" or "1.2.3" to "1.2.3"; anything else is no tag of ours.
pub fn clean_tag(tag: &str) -> Option<&str> {
    let version = tag.strip_prefix('v').unwrap_or(tag);
    let parts: Vec<&str> = version.split('.').collect();
    let plain = parts.len() == 3
        && parts
            .iter()
            .all(|p| !p.is_empty() && p.len() < 6 && p.bytes().all(|b| b.is_ascii_digit()));
    plain.then_some(version)
}

/// An Apple Silicon Mac stays one when this build runs under Rosetta: the compile-time architecture would say x86_64.
fn real_arch() -> &'static str {
    #[cfg(target_os = "macos")]
    {
        let arm = Command::new("sysctl")
            .args(["-n", "hw.optional.arm64"])
            .output()
            .map(|out| out.stdout.starts_with(b"1"))
            .unwrap_or(false);
        if arm {
            return "aarch64";
        }
    }
    std::env::consts::ARCH
}

fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .user_agent("kuhlers-gelumpe-updater")
        .timeout_connect(Duration::from_secs(15))
        .timeout_read(Duration::from_secs(30))
        .build()
}

/// Streams `url` into `dest` through a `.part` file, so a cut connection never leaves a file that looks complete.
fn download(
    agent: &ureq::Agent,
    url: &str,
    dest: &Path,
    mut progress: impl FnMut(u64, Option<u64>),
) -> Result<(), String> {
    let response = agent
        .get(url)
        .call()
        .map_err(|e| format!("Der Download ließ sich nicht starten: {e}"))?;
    let total = response
        .header("Content-Length")
        .and_then(|v| v.parse::<u64>().ok());
    let mut reader = response.into_reader();
    let mut part = dest.as_os_str().to_owned();
    part.push(".part");
    let part = PathBuf::from(part);
    let written = (|| -> Result<(), String> {
        let mut file = File::create(&part)
            .map_err(|e| format!("{} ließ sich nicht anlegen: {e}", part.display()))?;
        let mut buffer = vec![0u8; 64 * 1024];
        let mut received = 0u64;
        let mut told = Instant::now() - Duration::from_secs(1);
        progress(0, total);
        loop {
            let n = reader
                .read(&mut buffer)
                .map_err(|e| format!("Der Download brach ab: {e}"))?;
            if n == 0 {
                break;
            }
            file.write_all(&buffer[..n])
                .map_err(|e| format!("Schreiben nach {} schlug fehl: {e}", part.display()))?;
            received += n as u64;
            if told.elapsed() >= Duration::from_millis(100) {
                told = Instant::now();
                progress(received, total);
            }
        }
        file.flush()
            .map_err(|e| format!("Schreiben nach {} schlug fehl: {e}", part.display()))?;
        if let Some(total) = total.filter(|t| *t != received) {
            return Err(format!(
                "Der Download ist unvollständig ({received} von {total} Byte)."
            ));
        }
        progress(received, total);
        Ok(())
    })();
    if let Err(message) = written {
        let _ = fs::remove_file(&part);
        return Err(message);
    }
    fs::rename(&part, dest).map_err(|e| format!("{} ließ sich nicht anlegen: {e}", dest.display()))
}

/// Replaces the running AppImage by the new one and starts it once this process is gone: the single-instance
/// lock would hand a second start over to the first one.
#[cfg(target_os = "linux")]
fn replace_appimage(file: &Path, target: &Path) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    let mut staged = target.as_os_str().to_owned();
    staged.push(".new");
    let staged = PathBuf::from(staged);
    let result = fs::copy(file, &staged)
        .and_then(|_| fs::set_permissions(&staged, fs::Permissions::from_mode(0o755)))
        .and_then(|_| fs::rename(&staged, target));
    if let Err(e) = result {
        let _ = fs::remove_file(&staged);
        return Err(format!(
            "{} ließ sich nicht ersetzen: {e}",
            target.display()
        ));
    }
    let _ = fs::remove_file(file);
    Command::new("sh")
        .args(["-c", "sleep 1; exec \"$0\""])
        .arg(target)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("Die neue Version ließ sich nicht starten: {e}"))
}

/// Starts the installation of `file`. True when this app has to quit for it.
fn install(file: &Path) -> Result<bool, String> {
    let opened = |result: std::io::Result<std::process::Child>| {
        result
            .map(|_| ())
            .map_err(|e| format!("Die Installation ließ sich nicht starten: {e}"))
    };
    if cfg!(target_os = "macos") {
        opened(Command::new("open").arg(file).spawn())?;
        return Ok(false);
    }
    if cfg!(windows) {
        opened(Command::new(file).spawn())?;
        return Ok(true);
    }
    #[cfg(target_os = "linux")]
    if let Some(target) = std::env::var_os("APPIMAGE").map(PathBuf::from) {
        replace_appimage(file, &target)?;
        return Ok(true);
    }
    opened(Command::new("xdg-open").arg(file).spawn())?;
    Ok(false)
}

fn run(app: &AppHandle, tag: &str, report: impl Fn(Progress)) -> Result<(PathBuf, bool), String> {
    let version = clean_tag(tag).ok_or("Das ist keine Version dieser App.")?;
    let appimage = std::env::var_os("APPIMAGE").is_some();
    let want = wanted(std::env::consts::OS, real_arch(), appimage)
        .ok_or("Für dieses System gibt es keine fertige Datei.")?;
    let agent = agent();
    let release = agent
        .get(&format!(
            "https://api.github.com/repos/{REPO}/releases/tags/v{version}"
        ))
        .set("Accept", "application/vnd.github+json")
        .call()
        .map_err(|e| format!("Die Release-Daten ließen sich nicht laden: {e}"))?
        .into_reader();
    let release: serde_json::Value = serde_json::from_reader(release)
        .map_err(|e| format!("Die Release-Daten sind unlesbar: {e}"))?;
    let assets = release["assets"]
        .as_array()
        .map(Vec::as_slice)
        .unwrap_or(&[]);
    let names: Vec<&str> = assets
        .iter()
        .map(|a| a["name"].as_str().unwrap_or(""))
        .collect();
    let pick = pick_asset(&names, version, want)
        .ok_or("Das Release hat keine Datei für dieses System.")?;
    let url = assets[pick]["browser_download_url"]
        .as_str()
        .filter(|u| u.starts_with(&format!("https://github.com/{REPO}/releases/download/")))
        .ok_or("Das Release nennt keine Download-Adresse.")?;
    let name = Path::new(names[pick])
        .file_name()
        .ok_or("Das Release nennt keinen Dateinamen.")?;
    let folder = app
        .path()
        .download_dir()
        .map_err(|e| format!("Den Downloads-Ordner gibt es nicht: {e}"))?;
    let dest = folder.join(name);
    download(&agent, url, &dest, |received, total| {
        report(Progress::Download { received, total })
    })?;
    report(Progress::Install);
    let quit = install(&dest)?;
    Ok((dest, quit))
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Installed {
    file: String,
    quits: bool,
}

/// Downloads release `tag` for this system and starts its installation. Only the local main window may ask.
#[tauri::command]
pub async fn update_install(
    window: WebviewWindow,
    app: AppHandle,
    tag: String,
    events: Channel<Progress>,
) -> Result<Installed, String> {
    let address = window.url().map_err(|e| e.to_string())?;
    if !trusted_origin(window.label(), address.as_str()) {
        return Err("Updates lassen sich nur vom lokalen Hauptfenster starten.".into());
    }
    let handle = app.clone();
    let (file, quits) = tauri::async_runtime::spawn_blocking(move || {
        run(&handle, &tag, |p| {
            let _ = events.send(p);
        })
    })
    .await
    .map_err(|e| e.to_string())??;
    if quits {
        // Let the page see the answer, then leave so the installer can replace the files.
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(500));
            app.exit(0);
        });
    }
    Ok(Installed {
        file: file.display().to_string(),
        quits,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader};
    use std::net::TcpListener;

    const NAMES: [&str; 8] = [
        "Kuhlers.GELUMPE_1.3.2_aarch64.dmg",
        "Kuhlers.GELUMPE_1.3.2_x64.dmg",
        "Kuhlers.GELUMPE_1.3.2_x64-setup.exe",
        "Kuhlers.GELUMPE_1.3.2_amd64.AppImage",
        "Kuhlers.GELUMPE_1.3.2_amd64.deb",
        "Kuhlers.GELUMPE_1.3.1_amd64.deb",
        "BLECH.patch",
        "Kuhlers.GELUMPE_1.3.2_x64.dmg.sig",
    ];

    fn pick(os: &str, arch: &str, appimage: bool, version: &str) -> Option<&'static str> {
        let want = wanted(os, arch, appimage)?;
        pick_asset(&NAMES, version, want).map(|i| NAMES[i])
    }

    #[test]
    fn a_mac_gets_the_dmg_of_its_cpu() {
        assert_eq!(pick("macos", "aarch64", false, "1.3.2"), Some(NAMES[0]));
        assert_eq!(pick("macos", "x86_64", false, "1.3.2"), Some(NAMES[1]));
    }

    #[test]
    fn windows_gets_the_setup_not_a_bare_exe() {
        assert_eq!(pick("windows", "x86_64", false, "1.3.2"), Some(NAMES[2]));
        assert_eq!(pick("windows", "aarch64", false, "1.3.2"), Some(NAMES[2]));
    }

    #[test]
    fn linux_picks_appimage_or_deb_by_how_it_was_installed() {
        assert_eq!(pick("linux", "x86_64", true, "1.3.2"), Some(NAMES[3]));
        assert_eq!(pick("linux", "x86_64", false, "1.3.2"), Some(NAMES[4]));
    }

    #[test]
    fn only_the_wanted_version_counts() {
        assert_eq!(pick("linux", "x86_64", false, "1.3.1"), Some(NAMES[5]));
        assert_eq!(pick("linux", "x86_64", false, "1.3.3"), None);
        assert_eq!(pick("macos", "aarch64", false, "1.3"), None);
    }

    #[test]
    fn a_system_without_a_build_gets_none() {
        assert_eq!(wanted("linux", "aarch64", false), None);
        assert_eq!(wanted("freebsd", "x86_64", false), None);
    }

    #[test]
    fn only_plain_version_tags_pass() {
        assert_eq!(clean_tag("v1.3.2"), Some("1.3.2"));
        assert_eq!(clean_tag("1.3.2"), Some("1.3.2"));
        for bad in [
            "",
            "v1.3",
            "v1.3.2.1",
            "v1.3.x",
            "v1.3.2-beta",
            "../1.3.2",
            "v1..2",
        ] {
            assert_eq!(clean_tag(bad), None, "{bad}");
        }
    }

    /// One answer per connection, then the listener is gone.
    fn serve(body: Vec<u8>, claimed: usize) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut lines = BufReader::new(stream.try_clone().unwrap());
            let mut line = String::new();
            while lines.read_line(&mut line).unwrap() > 2 {
                line.clear();
            }
            let head = format!(
                "HTTP/1.1 200 OK\r\nContent-Length: {claimed}\r\nConnection: close\r\n\r\n"
            );
            let _ = stream.write_all(head.as_bytes());
            let _ = stream.write_all(&body);
        });
        format!("http://127.0.0.1:{port}/file.bin")
    }

    fn scratch(name: &str) -> PathBuf {
        let dir =
            std::env::temp_dir().join(format!("gelumpe-update-{}-{name}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn the_download_lands_whole_and_reports_its_progress() {
        let body: Vec<u8> = (0..300_000u32).map(|n| (n % 251) as u8).collect();
        let url = serve(body.clone(), body.len());
        let dir = scratch("whole");
        let dest = dir.join("file.bin");
        let mut seen = Vec::new();
        download(&agent(), &url, &dest, |r, t| seen.push((r, t))).unwrap();
        assert_eq!(fs::read(&dest).unwrap(), body);
        assert_eq!(seen.first(), Some(&(0, Some(300_000))));
        assert_eq!(seen.last(), Some(&(300_000, Some(300_000))));
        assert!(!dir.join("file.bin.part").exists());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn a_cut_download_leaves_no_file() {
        let url = serve(vec![7; 1000], 5000);
        let dir = scratch("cut");
        let dest = dir.join("file.bin");
        assert!(download(&agent(), &url, &dest, |_, _| {}).is_err());
        assert!(!dest.exists());
        assert!(!dir.join("file.bin.part").exists());
        fs::remove_dir_all(dir).unwrap();
    }

    /// The question of the Mac install: a file written by this code carries no quarantine flag, so Gatekeeper never
    /// checks the dmg itself. (Only apps that opt in, like browsers, set com.apple.quarantine on what they download.)
    #[cfg(target_os = "macos")]
    #[test]
    fn a_downloaded_file_carries_no_quarantine_flag() {
        let url = serve(vec![1; 100], 100);
        let dir = scratch("xattr");
        let dest = dir.join("file.bin");
        download(&agent(), &url, &dest, |_, _| {}).unwrap();
        let flagged = Command::new("xattr")
            .args(["-p", "com.apple.quarantine"])
            .arg(&dest)
            .output()
            .unwrap()
            .status
            .success();
        assert!(!flagged);
        fs::remove_dir_all(dir).unwrap();
    }
}
