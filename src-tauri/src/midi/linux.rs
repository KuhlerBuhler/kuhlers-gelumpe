use crate::midi::InputCallback;
use alsa::{
    seq::{Addr, Event, EventType, MidiEvent, PortCap, PortSubscribe, PortType},
    Seq,
};
use std::{
    ffi::CString,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread::JoinHandle,
    time::Duration,
};
pub struct Io {
    seq: Seq,
    port: i32,
    running: Arc<AtomicBool>,
    broken: Arc<AtomicBool>,
    reader: Option<JoinHandle<()>>,
}
fn address(value: &str) -> Result<Addr, String> {
    value.parse::<Addr>().map_err(|e| e.to_string())
}
fn name(value: &str) -> CString {
    CString::new(value).unwrap()
}
impl Io {
    pub fn open(
        input_id: &str,
        output_id: &str,
        mut callback: InputCallback,
    ) -> Result<Self, String> {
        let source = address(input_id)?;
        let dest = address(output_id)?;
        let seq = Seq::open(None, None, false).map_err(|e| e.to_string())?;
        seq.set_client_name(&name("GELUMPE output"))
            .map_err(|e| e.to_string())?;
        let port = seq
            .create_simple_port(
                &name("GELUMPE send"),
                PortCap::READ | PortCap::SUBS_READ,
                PortType::MIDI_GENERIC | PortType::APPLICATION,
            )
            .map_err(|e| e.to_string())?;
        let subscription = PortSubscribe::empty().map_err(|e| e.to_string())?;
        subscription.set_sender(Addr {
            client: seq.client_id().map_err(|e| e.to_string())?,
            port,
        });
        subscription.set_dest(dest);
        seq.subscribe_port(&subscription)
            .map_err(|e| e.to_string())?;
        let incoming =
            Seq::open(None, Some(alsa::Direction::Capture), true).map_err(|e| e.to_string())?;
        incoming
            .set_client_name(&name("GELUMPE input"))
            .map_err(|e| e.to_string())?;
        let input_port = incoming
            .create_simple_port(
                &name("GELUMPE receive"),
                PortCap::WRITE | PortCap::SUBS_WRITE,
                PortType::MIDI_GENERIC | PortType::APPLICATION,
            )
            .map_err(|e| e.to_string())?;
        let subscription = PortSubscribe::empty().map_err(|e| e.to_string())?;
        subscription.set_sender(source);
        subscription.set_dest(Addr {
            client: incoming.client_id().map_err(|e| e.to_string())?,
            port: input_port,
        });
        incoming
            .subscribe_port(&subscription)
            .map_err(|e| e.to_string())?;
        let running = Arc::new(AtomicBool::new(true));
        let broken = Arc::new(AtomicBool::new(false));
        let alive = running.clone();
        let failed = broken.clone();
        let reader = std::thread::Builder::new()
            .name("midi-alsa-input".into())
            .spawn(move || {
                let decoder = match MidiEvent::new(0) {
                    Ok(d) => d,
                    Err(_) => {
                        failed.store(true, Ordering::SeqCst);
                        return;
                    }
                };
                decoder.enable_running_status(false);
                let mut input = incoming.input();
                let mut buffer = [0u8; 12];
                while alive.load(Ordering::SeqCst) {
                    match input.event_input() {
                        Ok(mut event) => {
                            if decode_event(&decoder, &mut event, &mut buffer, &mut callback)
                                .is_err()
                            {
                                failed.store(true, Ordering::SeqCst);
                                break;
                            }
                        }
                        Err(error) if error.errno() == libc::EAGAIN => {
                            std::thread::sleep(Duration::from_millis(1))
                        }
                        Err(_) => {
                            failed.store(true, Ordering::SeqCst);
                            break;
                        }
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        Ok(Self {
            seq,
            port,
            running,
            broken,
            reader: Some(reader),
        })
    }
    fn emit(&self, event: &mut Event<'_>, active: &AtomicBool) -> Result<(), String> {
        if !active.load(Ordering::SeqCst) {
            return Err("MIDI-Sitzung geschlossen.".into());
        }
        event.set_source(self.port);
        event.set_subs();
        event.set_direct();
        self.seq
            .event_output_direct(event)
            .map_err(|e| e.to_string())?;
        self.seq.drain_output().map_err(|e| e.to_string())?;
        std::thread::sleep(Duration::from_millis(2));
        Ok(())
    }
    pub fn send(&mut self, bytes: &[u8], active: &AtomicBool) -> Result<(), String> {
        if bytes[0] == 0xf0 {
            for chunk in bytes.chunks(256) {
                self.emit(&mut Event::new_ext(EventType::Sysex, chunk), active)?;
            }
        } else {
            let mut encoder = MidiEvent::new(256).map_err(|e| e.to_string())?;
            let (used, event) = encoder.encode(bytes).map_err(|e| e.to_string())?;
            if used != bytes.len() {
                return Err("ALSA hat die MIDI-Nachricht nicht vollständig gelesen.".into());
            }
            self.emit(
                &mut event.ok_or("ALSA hat kein MIDI-Ereignis erzeugt.")?,
                active,
            )?;
        }
        Ok(())
    }
    pub fn healthy(&self) -> Result<(), String> {
        if self.broken.load(Ordering::SeqCst) {
            Err("ALSA-Eingabe fehlgeschlagen.".into())
        } else {
            Ok(())
        }
    }
}
fn decode_event(
    decoder: &MidiEvent,
    event: &mut Event<'_>,
    buffer: &mut [u8],
    callback: &mut dyn FnMut(&[u8]),
) -> Result<(), alsa::Error> {
    if event.get_type() == EventType::Sysex {
        if let Some(bytes) = event.get_ext() {
            callback(bytes);
        }
    } else {
        match decoder.decode(buffer, event) {
            Ok(0) => {}
            Ok(n) => callback(&buffer[..n]),
            Err(error) if error.errno() == libc::ENOENT => {}
            Err(error) => return Err(error),
        }
    }
    Ok(())
}

impl Drop for Io {
    fn drop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(reader) = self.reader.take() {
            let _ = reader.join();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sequencer_metadata_is_not_a_midi_transport_failure() {
        let decoder = MidiEvent::new(0).unwrap();
        let mut event = Event::new(
            EventType::PortSubscribed,
            alsa::seq::Connect {
                sender: Addr { client: 1, port: 2 },
                dest: Addr { client: 3, port: 4 },
            },
        );
        let mut buffer = [0u8; 12];
        let mut called = false;
        decode_event(&decoder, &mut event, &mut buffer, &mut |_| called = true).unwrap();
        assert!(!called);
        let mut event = Event::new_ext(EventType::Sysex, &[0xf0, 0x7d, 0xf7][..]);
        let mut received = Vec::new();
        decode_event(&decoder, &mut event, &mut buffer, &mut |bytes| {
            received.extend_from_slice(bytes)
        })
        .unwrap();
        assert_eq!(received, [0xf0, 0x7d, 0xf7]);
    }
}
