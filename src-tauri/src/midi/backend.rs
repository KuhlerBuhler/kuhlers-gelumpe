use super::service::{Connection, Driver, InputCallback, Port, Ports};
use midir::{Ignore, MidiInput, MidiOutput};
use std::sync::atomic::AtomicBool;

pub struct NativeDriver;
fn input() -> Result<MidiInput, String> {
    let mut midi = MidiInput::new("GELUMPE input").map_err(|e| e.to_string())?;
    midi.ignore(Ignore::None);
    Ok(midi)
}
fn output() -> Result<MidiOutput, String> {
    MidiOutput::new("GELUMPE output").map_err(|e| e.to_string())
}
fn input_ports(midi: &MidiInput) -> Vec<Port> {
    midi.ports()
        .iter()
        .filter_map(|port| {
            midi.port_name(port).ok().map(|name| Port {
                id: format!("{}|{name}", port.id()),
                name,
            })
        })
        .collect()
}
fn output_ports(midi: &MidiOutput) -> Vec<Port> {
    midi.ports()
        .iter()
        .filter_map(|port| {
            midi.port_name(port).ok().map(|name| Port {
                id: format!("{}|{name}", port.id()),
                name,
            })
        })
        .collect()
}
#[cfg(target_os = "macos")]
#[path = "macos.rs"]
mod platform;
#[cfg(target_os = "linux")]
#[path = "linux.rs"]
mod platform;
#[cfg(not(any(target_os = "macos", target_os = "linux")))]
#[path = "windows.rs"]
mod platform;
impl Driver for NativeDriver {
    fn list(&self) -> Result<Ports, String> {
        Ok(Ports {
            inputs: input_ports(&input()?),
            outputs: output_ports(&output()?),
        })
    }
    fn open(
        &self,
        input_id: &str,
        output_id: &str,
        callback: InputCallback,
    ) -> Result<Box<dyn Connection>, String> {
        let monitor_in = input()?;
        let monitor_out = output()?;
        let in_port = monitor_in
            .ports()
            .into_iter()
            .find(|port| {
                monitor_in
                    .port_name(port)
                    .is_ok_and(|name| format!("{}|{name}", port.id()) == input_id)
            })
            .ok_or("MIDI-Eingang nicht mehr vorhanden.")?;
        let out_port = monitor_out
            .ports()
            .into_iter()
            .find(|port| {
                monitor_out
                    .port_name(port)
                    .is_ok_and(|name| format!("{}|{name}", port.id()) == output_id)
            })
            .ok_or("MIDI-Ausgang nicht mehr vorhanden.")?;
        let io = platform::Io::open(&in_port.id(), &out_port.id(), callback)?;
        Ok(Box::new(NativeConnection {
            io,
            input_id: input_id.into(),
            output_id: output_id.into(),
            monitor_in,
            monitor_out,
        }))
    }
}
struct NativeConnection {
    io: platform::Io,
    input_id: String,
    output_id: String,
    monitor_in: MidiInput,
    monitor_out: MidiOutput,
}
impl Connection for NativeConnection {
    fn send(&mut self, bytes: &[u8], active: &AtomicBool) -> Result<(), String> {
        self.io.send(bytes, active)
    }
    fn connected(&mut self) -> Result<bool, String> {
        self.io.healthy()?;
        Ok(input_ports(&self.monitor_in)
            .iter()
            .any(|p| p.id == self.input_id)
            && output_ports(&self.monitor_out)
                .iter()
                .any(|p| p.id == self.output_id))
    }
}

#[cfg(test)]
mod packet_tests {
    #[test]
    fn coremidi_frames_fit_packet_length_and_keep_one_sysex_boundary() {
        let mut frame = vec![0x55; 128 * 1024];
        frame[0] = 0xf0;
        *frame.last_mut().unwrap() = 0xf7;
        let mut received = Vec::new();
        super::coremidi_packets(&frame, |packet| {
            assert!(packet.len() <= 1024);
            received.extend_from_slice(packet);
            Ok(())
        })
        .unwrap();
        assert_eq!(received, frame);
        assert_eq!(received.iter().filter(|b| **b == 0xf0).count(), 1);
        assert_eq!(received.iter().filter(|b| **b == 0xf7).count(), 1);
    }
}
#[cfg(any(target_os = "macos", test))]
fn coremidi_packets(
    bytes: &[u8],
    mut emit: impl FnMut(&[u8]) -> Result<(), String>,
) -> Result<(), String> {
    for packet in bytes.chunks(1024) {
        emit(packet)?;
    }
    Ok(())
}

#[cfg(all(test, any(target_os = "macos", target_os = "linux")))]
mod tests {
    use super::*;
    use crate::midi::{Config, Event, MidiService};
    use midir::os::unix::{VirtualInput, VirtualOutput};
    use std::{
        sync::{mpsc, Arc},
        time::{Duration, SystemTime, UNIX_EPOCH},
    };
    #[test]
    #[ignore = "Creates only uniquely named virtual MIDI ports; requires a functioning OS MIDI service."]
    fn virtual_ports_round_trip_large_sysex_and_disconnect() {
        let suffix = format!(
            "{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let source_name = format!("GELUMPE own test source {suffix}");
        let sink_name = format!("GELUMPE own test sink {suffix}");
        let (received_tx, received_rx) = mpsc::channel();
        let sink = input()
            .unwrap()
            .create_virtual(
                &sink_name,
                move |_, bytes, _| {
                    received_tx.send(bytes.to_vec()).unwrap();
                },
                (),
            )
            .expect("Own virtual input could not be created");
        let mut source = output()
            .unwrap()
            .create_virtual(&source_name)
            .expect("Own virtual output could not be created");
        let service = MidiService::new(Arc::new(NativeDriver), Config::default());
        let ports = service.list().unwrap();
        let input = ports
            .inputs
            .into_iter()
            .find(|p| p.name.contains(&source_name))
            .expect("Own source missing");
        let output = ports
            .outputs
            .into_iter()
            .find(|p| p.name.contains(&sink_name))
            .expect("Own sink missing");
        let (tx, rx) = mpsc::channel();
        let id = service
            .open(
                input.id,
                output.id,
                Arc::new(move |e| tx.send(e).map_err(|e| e.to_string())),
            )
            .unwrap();
        for size in [
            6,
            7,
            255,
            256,
            257,
            4096,
            52400,
            59894,
            128 * 1024,
            1024 * 1024,
        ] {
            let mut frame = vec![0x55; size];
            frame[0] = 0xf0;
            *frame.last_mut().unwrap() = 0xf7;
            service.send(&id, frame.clone()).unwrap();
            let mut received = Vec::new();
            while received.len() < frame.len() {
                received.extend(
                    received_rx
                        .recv_timeout(Duration::from_secs(15))
                        .expect("Own sink received no MIDI"),
                );
            }
            assert_eq!(received, frame, "outgoing frame {size}");
        }
        assert!(service.send(&id, vec![0xf0]).is_err());
        assert!(service.send(&id, vec![0x55; 1024 * 1024 + 1]).is_err());
        assert!(received_rx.try_recv().is_err());
        let mut incoming = vec![0x33; 128 * 1024];
        incoming[0] = 0xf0;
        *incoming.last_mut().unwrap() = 0xf7;
        for packet in incoming.chunks(1024) {
            source.send(packet).unwrap();
            std::thread::sleep(Duration::from_micros(200));
        }
        assert!(
            matches!(rx.recv_timeout(Duration::from_secs(5)).unwrap(),Event::Message{bytes,..} if bytes==incoming)
        );
        drop(source);
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(5)).unwrap(),
            Event::Disconnected { .. }
        ));
        assert!(service.send(&id, vec![0x90, 60, 0]).is_err());
        assert_eq!(service.close(&id).unwrap().state, "closed");
        drop(sink);
    }
}
