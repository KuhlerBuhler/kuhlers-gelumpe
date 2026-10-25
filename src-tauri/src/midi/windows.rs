use crate::midi::InputCallback;
use std::sync::atomic::{AtomicBool, Ordering};
pub struct Io {
    _input: midir::MidiInputConnection<()>,
    output: midir::MidiOutputConnection,
}
impl Io {
    pub fn open(
        input_id: &str,
        output_id: &str,
        mut callback: InputCallback,
    ) -> Result<Self, String> {
        let incoming = super::input()?;
        let outgoing = super::output()?;
        let input = incoming
            .ports()
            .into_iter()
            .find(|p| p.id() == input_id)
            .ok_or("MIDI-Eingang nicht vorhanden.")?;
        let output = outgoing
            .ports()
            .into_iter()
            .find(|p| p.id() == output_id)
            .ok_or("MIDI-Ausgang nicht vorhanden.")?;
        let input = incoming
            .connect(
                &input,
                "GELUMPE receive",
                move |_, bytes, _| callback(bytes),
                (),
            )
            .map_err(|e| e.to_string())?;
        let output = outgoing
            .connect(&output, "GELUMPE send")
            .map_err(|e| e.to_string())?;
        Ok(Self {
            _input: input,
            output,
        })
    }
    pub fn send(&mut self, bytes: &[u8], active: &AtomicBool) -> Result<(), String> {
        if !active.load(Ordering::SeqCst) {
            return Err("MIDI-Sitzung geschlossen.".into());
        }
        self.output.send(bytes).map_err(|e| e.to_string())
    }
    pub fn healthy(&self) -> Result<(), String> {
        Ok(())
    }
}
