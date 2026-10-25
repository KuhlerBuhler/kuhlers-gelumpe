#[cfg(any(target_os = "macos", target_os = "linux"))]
mod smoke {
    use kuhlers_gelumpe::midi::{self, Config, MidiService, NativeDriver};
    use midir::{
        os::unix::{VirtualInput, VirtualOutput},
        Ignore, MidiInput, MidiOutput,
    };
    use std::sync::{Arc, Mutex};
    use tauri::{AppHandle, WebviewUrl, WebviewWindowBuilder};

    #[tauri::command]
    fn smoke_result(app: AppHandle, window: tauri::WebviewWindow, ok: bool, detail: String) {
        println!(
            "WebKit MIDI smoke: {ok}: {detail}; native URL: {:?}",
            window.url()
        );
        app.exit(if ok { 0 } else { 1 });
    }

    pub fn run() {
        let name = format!("Electribe GELUMPE smoke {}", std::process::id());
        let source = MidiOutput::new("GELUMPE own smoke")
            .unwrap()
            .create_virtual(&name)
            .expect("Own virtual MIDI source unavailable");
        let source = Arc::new(Mutex::new(source));
        let echo = source.clone();
        let mut input = MidiInput::new("GELUMPE own smoke").unwrap();
        input.ignore(Ignore::None);
        let sink = input
            .create_virtual(
                &name,
                move |_, bytes, _| {
                    if bytes == [0xf0, 0x7d, 1, 0xf7] {
                        echo.lock().unwrap().send(&[0xf0, 0x7d, 2, 0xf7]).unwrap();
                    }
                },
                (),
            )
            .expect("Own virtual MIDI sink unavailable");
        let script = format!(
            r#"
            window.__GELUMPE_APP = {{ version: "smoke", nativeMidi: true }};
            addEventListener("DOMContentLoaded", async () => {{
                const report = (ok, detail) => window.__TAURI__.core.invoke("smoke_result", {{ ok, detail }});
                try {{
                    const {{ createMidiTransport }} = await import(new URL("./app/midi.mjs", location.href).href);
                    const midi = createMidiTransport();
                    const access = await midi.requestAccess();
                    const name = {name};
                    const out = [...access.outputs.values()].find(p => p.name.includes(name));
                    const input = [...access.inputs.values()].find(p => p.name === out?.name);
                    if (!out || !input) throw new Error("Own virtual pair missing");
                    const port = {{ out, in: input, name: out.name }};
                    await midi.openPort(port);
                    const reply = new Promise((resolve, reject) => {{
                        const timer = setTimeout(() => reject(new Error("Channel reply timeout")), 5000);
                        input.onmidimessage = event => {{ clearTimeout(timer); resolve([...event.data]); }};
                    }});
                    await out.send([0xf0, 0x7d, 1, 0xf7]);
                    if ((await reply).join() !== "240,125,2,247") throw new Error("Reply bytes differ");
                    const closed = await midi.closePort(port);
                    if (closed.state !== "closed") throw new Error("Port not released");
                    await report(true, "Actual WebKit adapter, invoke, OS virtual ports and Channel passed");
                }} catch (error) {{ await report(false, `${{location.href}}: ${{error.message ?? String(error)}}`); }}
            }});
        "#,
            name = serde_json::to_string(&name).unwrap()
        );
        tauri::Builder::default()
            .manage(MidiService::new(Arc::new(NativeDriver), Config::default()))
            .manage(Mutex::new(sink))
            .manage(source)
            .invoke_handler(tauri::generate_handler![
                midi::midi_list,
                midi::midi_open,
                midi::midi_send,
                midi::midi_ack,
                midi::midi_read,
                midi::midi_close,
                smoke_result
            ])
            .setup(move |app| {
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .visible(false)
                    .initialization_script(script)
                    .build()?;
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_secs(30));
                    eprintln!("WebKit MIDI smoke exceeded 30 seconds");
                    handle.exit(1);
                });
                Ok(())
            })
            .run(tauri::generate_context!())
            .expect("WebKit MIDI smoke failed to start");
    }
}

#[cfg(any(target_os = "macos", target_os = "linux"))]
fn main() {
    smoke::run();
}

#[cfg(not(any(target_os = "macos", target_os = "linux")))]
fn main() {
    eprintln!("Native MIDI smoke requires macOS or Linux");
    std::process::exit(1);
}
