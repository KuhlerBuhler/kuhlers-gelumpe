//! Android has no MIDI backend yet: listing and opening say so, nothing else happens.
use super::service::{Connection, Driver, InputCallback, Ports};

pub struct NativeDriver;

const NONE: &str = "Die Android-App hat noch kein MIDI.";

impl Driver for NativeDriver {
    fn list(&self) -> Result<Ports, String> {
        Err(NONE.into())
    }
    fn open(
        &self,
        _input_id: &str,
        _output_id: &str,
        _callback: InputCallback,
    ) -> Result<Box<dyn Connection>, String> {
        Err(NONE.into())
    }
}
