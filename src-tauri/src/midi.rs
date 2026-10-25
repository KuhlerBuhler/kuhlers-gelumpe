mod backend;
mod service;
pub use backend::NativeDriver;
pub use service::*;

use serde::Serialize;
use tauri::{ipc::Channel, State, WebviewWindow};

fn authorize(window: &WebviewWindow) -> Result<(), CommandError> {
    if !cfg!(any(target_os = "macos", target_os = "linux")) {
        return Err(CommandError::new(
            "not_authorized",
            "Native MIDI ist auf dieser Plattform nicht freigegeben.",
        ));
    }
    if !trusted_origin(
        window.label(),
        window.url().map_err(CommandError::driver)?.as_str(),
    ) {
        return Err(CommandError::new(
            "not_authorized",
            "MIDI ist nur im lokalen Hauptfenster verfügbar.",
        ));
    }
    Ok(())
}
#[tauri::command]
pub async fn midi_list(
    window: WebviewWindow,
    state: State<'_, MidiService>,
) -> Result<Ports, CommandError> {
    authorize(&window)?;
    let service = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.list())
        .await
        .map_err(CommandError::driver)?
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OpenResult {
    session_id: String,
}
#[tauri::command]
pub async fn midi_open(
    window: WebviewWindow,
    state: State<'_, MidiService>,
    input_id: String,
    output_id: String,
    events: Channel<Notification>,
) -> Result<OpenResult, CommandError> {
    authorize(&window)?;
    let service = state.inner().clone();
    let epoch = service.epoch()?;
    tauri::async_runtime::spawn_blocking(move || {
        service
            .open_for_document(
                epoch,
                input_id,
                output_id,
                std::sync::Arc::new(move |event| {
                    events
                        .send(Notification::from(event))
                        .map_err(|e| e.to_string())
                }),
            )
            .map(|session_id| OpenResult { session_id })
    })
    .await
    .map_err(CommandError::driver)?
}
#[tauri::command]
pub async fn midi_send(
    window: WebviewWindow,
    state: State<'_, MidiService>,
    session_id: String,
    bytes: Vec<u8>,
) -> Result<(), CommandError> {
    authorize(&window)?;
    validate_frame(&bytes)?;
    let service = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.send(&session_id, bytes))
        .await
        .map_err(CommandError::driver)?
}
#[tauri::command]
pub async fn midi_close(
    window: WebviewWindow,
    state: State<'_, MidiService>,
    session_id: String,
) -> Result<CloseResult, CommandError> {
    authorize(&window)?;
    let service = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.close(&session_id))
        .await
        .map_err(CommandError::driver)?
}

#[tauri::command]
pub async fn midi_ack(
    window: WebviewWindow,
    state: State<'_, MidiService>,
    session_id: String,
    sequence: u64,
) -> Result<(), CommandError> {
    authorize(&window)?;
    state.ack(&session_id, sequence)
}

#[derive(Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum Notification {
    Message {
        #[serde(rename = "sessionId")]
        session_id: String,
        sequence: u64,
    },
    Disconnected {
        #[serde(rename = "sessionId")]
        session_id: String,
    },
    Error {
        #[serde(rename = "sessionId")]
        session_id: String,
        code: String,
        message: String,
    },
}
impl From<Event> for Notification {
    fn from(event: Event) -> Self {
        match event {
            Event::Message {
                session_id,
                sequence,
                ..
            } => Self::Message {
                session_id,
                sequence,
            },
            Event::Disconnected { session_id } => Self::Disconnected { session_id },
            Event::Error {
                session_id,
                code,
                message,
            } => Self::Error {
                session_id,
                code,
                message,
            },
        }
    }
}

#[tauri::command]
pub async fn midi_read(
    window: WebviewWindow,
    state: State<'_, MidiService>,
    session_id: String,
    sequence: u64,
) -> Result<Vec<u8>, CommandError> {
    authorize(&window)?;
    state.read(&session_id, sequence)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn channel_notification_never_carries_large_payload() {
        let event = Event::Message {
            session_id: "own-session".into(),
            sequence: 1,
            bytes: vec![0x55; MAX_FRAME],
        };
        let json = serde_json::to_string(&Notification::from(event)).unwrap();
        assert!(json.len() < 256);
        assert!(!json.contains("bytes"));
    }
}
