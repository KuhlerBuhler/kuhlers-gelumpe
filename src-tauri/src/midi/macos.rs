use crate::midi::InputCallback;
use coremidi::{
    Client, Destination, Destinations, InputPort, OutputPort, PacketBuffer, Source, Sources,
};
use std::sync::atomic::{AtomicBool, Ordering};

pub struct Io {
    _input: InputPort,
    output: OutputPort,
    destination: Destination,
    _source: Source,
    _client: Client,
}
impl Io {
    pub fn open(
        input_id: &str,
        output_id: &str,
        mut callback: InputCallback,
    ) -> Result<Self, String> {
        let source = Sources
            .into_iter()
            .find(|p| p.unique_id().is_some_and(|id| id.to_string() == input_id))
            .ok_or("CoreMIDI-Eingang nicht vorhanden.")?;
        let destination = Destinations
            .into_iter()
            .find(|p| p.unique_id().is_some_and(|id| id.to_string() == output_id))
            .ok_or("CoreMIDI-Ausgang nicht vorhanden.")?;
        let client = Client::new("GELUMPE MIDI").map_err(|e| format!("CoreMIDI-Client: {e}"))?;
        let input = client
            .input_port("GELUMPE receive", move |packets| {
                for packet in packets.iter() {
                    callback(packet.data());
                }
            })
            .map_err(|e| format!("CoreMIDI-Eingang: {e}"))?;
        input
            .connect_source(&source)
            .map_err(|e| format!("CoreMIDI-Verbindung: {e}"))?;
        let output = client
            .output_port("GELUMPE send")
            .map_err(|e| format!("CoreMIDI-Ausgang: {e}"))?;
        Ok(Self {
            _input: input,
            output,
            destination,
            _source: source,
            _client: client,
        })
    }
    pub fn send(&mut self, bytes: &[u8], active: &AtomicBool) -> Result<(), String> {
        super::coremidi_packets(bytes, |packet| {
            if !active.load(Ordering::SeqCst) {
                return Err("MIDI-Sitzung geschlossen.".into());
            }
            self.output
                .send(&self.destination, &PacketBuffer::new(0, packet))
                .map_err(|e| format!("CoreMIDI-Ausgabe: {e}"))
        })
    }
    pub fn healthy(&self) -> Result<(), String> {
        Ok(())
    }
}
