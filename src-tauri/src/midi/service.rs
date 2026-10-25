use serde::Serialize;
use std::collections::HashMap;
use std::sync::{
    atomic::{AtomicBool, AtomicUsize, Ordering},
    mpsc::{self, Receiver, SyncSender},
    Arc, Mutex,
};
use std::time::{Duration, Instant};

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct CommandError {
    pub code: &'static str,
    pub message: String,
}
impl CommandError {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
    pub fn driver(error: impl std::fmt::Display) -> Self {
        Self::new("driver_error", error.to_string())
    }
}
impl std::fmt::Display for CommandError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.message.fmt(f)
    }
}
impl std::error::Error for CommandError {}
pub const MAX_FRAME: usize = 1024 * 1024;
const MAX_WORKERS: usize = 2;
const INBOUND_QUEUE: usize = 32;
const INBOUND_BYTES: usize = 2 * MAX_FRAME;
pub type InputCallback = Box<dyn FnMut(&[u8]) + Send>;
pub type EventSink = Arc<dyn Fn(Event) -> Result<(), String> + Send + Sync>;
#[derive(Clone, Debug, Serialize)]
pub struct Port {
    pub id: String,
    pub name: String,
}
#[derive(Clone, Debug, Serialize)]
pub struct Ports {
    pub inputs: Vec<Port>,
    pub outputs: Vec<Port>,
}
#[derive(Clone, Debug, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum Event {
    Message {
        #[serde(rename = "sessionId")]
        session_id: String,
        sequence: u64,
        bytes: Vec<u8>,
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
pub trait Connection: Send {
    fn send(&mut self, bytes: &[u8], active: &AtomicBool) -> Result<(), String>;
    fn connected(&mut self) -> Result<bool, String>;
}
pub trait Driver: Send + Sync + 'static {
    fn list(&self) -> Result<Ports, String>;
    fn open(
        &self,
        input: &str,
        output: &str,
        callback: InputCallback,
    ) -> Result<Box<dyn Connection>, String>;
}
#[derive(Clone)]
pub struct Config {
    pub open_timeout: Duration,
    pub list_timeout: Duration,
    pub close_timeout: Duration,
    pub send_base: Duration,
    pub send_per_byte: Duration,
    pub poll: Duration,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            open_timeout: Duration::from_secs(5),
            list_timeout: Duration::from_secs(3),
            close_timeout: Duration::from_secs(2),
            send_base: Duration::from_secs(2),
            send_per_byte: Duration::from_micros(300),
            poll: Duration::from_millis(500),
        }
    }
}
#[derive(Clone)]
pub struct MidiService(Arc<Shared>);
struct Shared {
    state: Mutex<State>,
    driver: Arc<dyn Driver>,
    config: Config,
    workers: Arc<AtomicUsize>,
    credits: Arc<Credits>,
}
#[derive(Default)]
struct State {
    active: Option<Arc<Session>>,
    held: Vec<Arc<Session>>,
    shutdown: bool,
    epoch: usize,
    loading: bool,
}
struct Session {
    id: String,
    input: String,
    output: String,
    active: AtomicBool,
    released: AtomicBool,
    sending: AtomicBool,
    tx: SyncSender<Operation>,
    sink: EventSink,
    overflow: AtomicBool,
    terminal: Mutex<Option<Event>>,
}
#[derive(Default)]
struct Credits {
    state: Mutex<CreditState>,
}
#[derive(Default)]
struct CreditState {
    next: u64,
    bytes: usize,
    outstanding: HashMap<u64, CreditEntry>,
}
struct CreditEntry {
    session: String,
    bytes: usize,
    attempted: bool,
    payload: Option<Vec<u8>>,
}
struct Credit {
    credits: Arc<Credits>,
    session: String,
    sequence: u64,
    attempted: bool,
}
struct Incoming {
    bytes: Vec<u8>,
    credit: Credit,
}
impl Credits {
    fn reserve(self: &Arc<Self>, session: &str, bytes: usize) -> Result<Credit, ()> {
        let mut state = self.state.lock().map_err(|_| ())?;
        if state.outstanding.len() >= INBOUND_QUEUE
            || state
                .bytes
                .checked_add(bytes)
                .filter(|n| *n <= INBOUND_BYTES)
                .is_none()
        {
            return Err(());
        }
        let sequence = state
            .next
            .checked_add(1)
            .filter(|n| *n < (1u64 << 53))
            .ok_or(())?;
        state.next = sequence;
        state.bytes += bytes;
        state.outstanding.insert(
            sequence,
            CreditEntry {
                session: session.into(),
                bytes,
                attempted: false,
                payload: None,
            },
        );
        Ok(Credit {
            credits: self.clone(),
            session: session.into(),
            sequence,
            attempted: false,
        })
    }
    fn ack(&self, session: &str, sequence: u64) -> Result<(), CommandError> {
        let mut state = self
            .state
            .lock()
            .map_err(|_| CommandError::new("driver_error", "MIDI-Zustand nicht verfügbar."))?;
        let entry = state
            .outstanding
            .get(&sequence)
            .filter(|e| e.session == session && e.attempted)
            .ok_or_else(|| {
                CommandError::new("invalid_session", "Unbekannte MIDI-Empfangsbestätigung.")
            })?;
        let bytes = entry.bytes;
        state.outstanding.remove(&sequence);
        state.bytes -= bytes;
        Ok(())
    }
}
impl Credit {
    fn attempt(&mut self, bytes: &[u8]) -> Result<(), ()> {
        let mut state = self.credits.state.lock().map_err(|_| ())?;
        let entry = state
            .outstanding
            .get_mut(&self.sequence)
            .filter(|entry| entry.session == self.session)
            .ok_or(())?;
        entry.payload = Some(bytes.to_vec());
        entry.attempted = true;
        self.attempted = true;
        Ok(())
    }
}
impl Drop for Credit {
    fn drop(&mut self) {
        if self.attempted {
            return;
        }
        if let Ok(mut state) = self.credits.state.lock() {
            if let Some(entry) = state.outstanding.remove(&self.sequence) {
                state.bytes -= entry.bytes;
            }
        }
    }
}
struct Operation {
    bytes: Vec<u8>,
    reply: SyncSender<Result<(), CommandError>>,
}
struct Lease(Arc<AtomicUsize>);
impl Drop for Lease {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::SeqCst);
    }
}
struct Released(Arc<Session>);
impl Drop for Released {
    fn drop(&mut self) {
        self.0.released.store(true, Ordering::SeqCst);
    }
}
struct Sending<'a>(&'a AtomicBool);
impl Drop for Sending<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::SeqCst);
    }
}
impl MidiService {
    pub fn new(driver: Arc<dyn Driver>, config: Config) -> Self {
        Self(Arc::new(Shared {
            state: Mutex::new(State::default()),
            driver,
            config,
            workers: Arc::new(AtomicUsize::new(0)),
            credits: Arc::new(Credits::default()),
        }))
    }
    fn lease(&self) -> Result<Lease, CommandError> {
        let mut workers = self.0.workers.load(Ordering::SeqCst);
        loop {
            if workers >= MAX_WORKERS {
                return Err(CommandError::new(
                    "busy",
                    "MIDI-Treiber belegt; vorherige Vorgänge müssen enden.",
                ));
            }
            match self.0.workers.compare_exchange_weak(
                workers,
                workers + 1,
                Ordering::SeqCst,
                Ordering::SeqCst,
            ) {
                Ok(_) => return Ok(Lease(self.0.workers.clone())),
                Err(observed) => workers = observed,
            }
        }
    }
    pub fn list(&self) -> Result<Ports, CommandError> {
        let lease = self.lease()?;
        let driver = self.0.driver.clone();
        let (tx, rx) = mpsc::sync_channel(1);
        std::thread::Builder::new()
            .name("midi-list".into())
            .spawn(move || {
                let _lease = lease;
                let _ = tx.send(driver.list().map_err(CommandError::driver));
            })
            .map_err(CommandError::driver)?;
        rx.recv_timeout(self.0.config.list_timeout).map_err(|_| {
            CommandError::new(
                "transport_timeout",
                "Die MIDI-Portsuche hat die Wartezeit überschritten.",
            )
        })?
    }
    pub fn open(
        &self,
        input: String,
        output: String,
        sink: EventSink,
    ) -> Result<String, CommandError> {
        self.open_epoch(None, input, output, sink)
    }
    pub fn epoch(&self) -> Result<usize, CommandError> {
        let state = self
            .0
            .state
            .lock()
            .map_err(|_| CommandError::new("driver_error", "MIDI-Zustand nicht verfügbar."))?;
        if state.loading {
            return Err(CommandError::new(
                "invalid_session",
                "Das App-Dokument wird neu geladen.",
            ));
        }
        Ok(state.epoch)
    }
    pub fn open_for_document(
        &self,
        epoch: usize,
        input: String,
        output: String,
        sink: EventSink,
    ) -> Result<String, CommandError> {
        self.open_epoch(Some(epoch), input, output, sink)
    }
    fn open_epoch(
        &self,
        epoch: Option<usize>,
        input: String,
        output: String,
        sink: EventSink,
    ) -> Result<String, CommandError> {
        if input.is_empty() || output.is_empty() || input.len() > 512 || output.len() > 512 {
            return Err(CommandError::new(
                "invalid_message",
                "Ungültige MIDI-Port-ID.",
            ));
        }
        let mut state = self
            .0
            .state
            .lock()
            .map_err(|_| CommandError::new("driver_error", "MIDI-Zustand nicht verfügbar."))?;
        if state.loading || epoch.is_some_and(|epoch| epoch != state.epoch) {
            return Err(CommandError::new(
                "invalid_session",
                "Das App-Dokument wurde neu geladen.",
            ));
        }
        if state.shutdown {
            return Err(CommandError::new("invalid_session", "MIDI-Dienst beendet."));
        }
        state.held.retain(|s| !s.released.load(Ordering::SeqCst));
        if state
            .active
            .as_ref()
            .is_some_and(|s| s.active.load(Ordering::SeqCst))
        {
            return Err(CommandError::new(
                "busy",
                "Eine MIDI-Sitzung ist bereits geöffnet.",
            ));
        }
        if state
            .held
            .iter()
            .any(|s| s.input == input || s.output == output)
        {
            return Err(CommandError::new(
                "busy",
                "MIDI-Port quarantined bis der Treiber ihn freigibt.",
            ));
        }
        let lease = self.lease()?;
        let mut random = [0u8; 16];
        getrandom::fill(&mut random).map_err(CommandError::driver)?;
        let id = random
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<String>();
        let (tx, rx) = mpsc::sync_channel(1);
        let (in_tx, in_rx) = mpsc::sync_channel(INBOUND_QUEUE);
        let (ready_tx, ready_rx) = mpsc::sync_channel(1);
        let session = Arc::new(Session {
            id: id.clone(),
            input,
            output,
            active: AtomicBool::new(true),
            released: AtomicBool::new(false),
            sending: AtomicBool::new(false),
            tx,
            sink,
            overflow: AtomicBool::new(false),
            terminal: Mutex::new(None),
        });
        state.active = Some(session.clone());
        state.held.push(session.clone());
        drop(state);
        let owner = session.clone();
        let credits = self.0.credits.clone();
        let driver = self.0.driver.clone();
        let poll = self.0.config.poll;
        if let Err(error) = std::thread::Builder::new()
            .name("midi-owner".into())
            .spawn(move || {
                let _lease = lease;
                let _released = Released(owner.clone());
                let result = (|| {
                    if !owner.active.load(Ordering::SeqCst) {
                        return Err(CommandError::new(
                            "invalid_session",
                            "MIDI-Sitzung geschlossen.",
                        ));
                    }
                    let ports = driver.list().map_err(CommandError::driver)?;
                    if !ports.inputs.iter().any(|p| p.id == owner.input)
                        || !ports.outputs.iter().any(|p| p.id == owner.output)
                    {
                        return Err(CommandError::new(
                            "port_missing",
                            "Der gewählte MIDI-Port ist nicht mehr vorhanden.",
                        ));
                    }
                    if !owner.active.load(Ordering::SeqCst) {
                        return Err(CommandError::new(
                            "invalid_session",
                            "MIDI-Sitzung geschlossen.",
                        ));
                    }
                    let mut framer = Framer::default();
                    let incoming = owner.clone();
                    let callback_tx = in_tx.clone();
                    let callback: InputCallback = Box::new(move |bytes| {
                        if !incoming.active.load(Ordering::SeqCst) {
                            return;
                        }
                        if bytes.len() > MAX_FRAME
                            || framer
                                .feed(bytes, |frame| {
                                    let credit = credits.reserve(&incoming.id, frame.len())?;
                                    callback_tx
                                        .try_send(Incoming {
                                            bytes: frame,
                                            credit,
                                        })
                                        .map_err(|_| ())?;
                                    Ok(())
                                })
                                .is_err()
                        {
                            incoming.overflow.store(true, Ordering::SeqCst);
                            incoming.active.store(false, Ordering::SeqCst);
                        }
                    });
                    driver
                        .open(&owner.input, &owner.output, callback)
                        .map_err(CommandError::driver)
                })();
                let mut connection = match result {
                    Ok(c) => {
                        let _ = ready_tx.send(Ok(()));
                        c
                    }
                    Err(e) => {
                        let _ = ready_tx.send(Err(e));
                        return;
                    }
                };
                while owner.active.load(Ordering::SeqCst) {
                    match rx.recv_timeout(poll) {
                        Ok(operation) => {
                            if !owner.active.load(Ordering::SeqCst) {
                                let _ = operation.reply.send(Err(CommandError::new(
                                    "invalid_session",
                                    "MIDI-Sitzung geschlossen.",
                                )));
                                break;
                            }
                            let result = connection
                                .send(&operation.bytes, &owner.active)
                                .map_err(CommandError::driver);
                            let failed = result.is_err();
                            let result = if owner.active.load(Ordering::SeqCst) {
                                result
                            } else {
                                Err(CommandError::new(
                                    "invalid_session",
                                    "MIDI-Sitzung geschlossen.",
                                ))
                            };
                            let _ = operation.reply.send(result);
                            if failed {
                                break;
                            }
                        }
                        Err(mpsc::RecvTimeoutError::Timeout) => {
                            let event = match connection.connected() {
                                Ok(true) => continue,
                                Ok(false) => Event::Disconnected {
                                    session_id: owner.id.clone(),
                                },
                                Err(message) => Event::Error {
                                    session_id: owner.id.clone(),
                                    code: "driver_error".into(),
                                    message,
                                },
                            };
                            if let Ok(mut terminal) = owner.terminal.lock() {
                                *terminal = Some(event);
                            }
                            owner.active.store(false, Ordering::SeqCst);
                            break;
                        }
                        Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    }
                }
                drop(connection);
            })
        {
            session.active.store(false, Ordering::SeqCst);
            session.released.store(true, Ordering::SeqCst);
            return Err(CommandError::driver(error));
        }
        let dispatch = session.clone();
        if let Err(error) = std::thread::Builder::new()
            .name("midi-events".into())
            .spawn(move || dispatch_events(dispatch, in_rx))
        {
            session.active.store(false, Ordering::SeqCst);
            return Err(CommandError::driver(error));
        }
        match ready_rx.recv_timeout(self.0.config.open_timeout) {
            Ok(Ok(())) if session.active.load(Ordering::SeqCst) => Ok(id),
            Ok(Err(e)) => {
                self.fail(&session, &e);
                Err(e)
            }
            _ => {
                let error = CommandError::new(
                    "transport_timeout",
                    "Das Öffnen der MIDI-Sitzung hat die Wartezeit überschritten.",
                );
                self.fail(&session, &error);
                Err(error)
            }
        }
    }
    fn session(&self, id: &str) -> Result<Arc<Session>, CommandError> {
        let state = self
            .0
            .state
            .lock()
            .map_err(|_| CommandError::new("driver_error", "MIDI-Zustand nicht verfügbar."))?;
        state
            .active
            .as_ref()
            .filter(|s| s.id == id && s.active.load(Ordering::SeqCst))
            .cloned()
            .ok_or_else(|| {
                CommandError::new(
                    "invalid_session",
                    "MIDI-Sitzung ist ungültig oder geschlossen.",
                )
            })
    }
    fn fail(&self, session: &Session, error: &CommandError) {
        if session.active.swap(false, Ordering::SeqCst) {
            let _ = (session.sink)(Event::Error {
                session_id: session.id.clone(),
                code: error.code.into(),
                message: error.message.clone(),
            });
        }
    }
    pub fn send(&self, id: &str, bytes: Vec<u8>) -> Result<(), CommandError> {
        validate_frame(&bytes)?;
        let session = self.session(id)?;
        if session.sending.swap(true, Ordering::SeqCst) {
            return Err(CommandError::new("busy", "MIDI-Ausgabe ist belegt."));
        }
        let _sending = Sending(&session.sending);
        let timeout = self
            .0
            .config
            .send_base
            .saturating_add(
                self.0
                    .config
                    .send_per_byte
                    .saturating_mul(bytes.len() as u32),
            )
            .min(Duration::from_secs(60));
        let (tx, rx) = mpsc::sync_channel(1);
        if session.tx.try_send(Operation { bytes, reply: tx }).is_err() {
            self.fail(
                &session,
                &CommandError::new("queue_full", "MIDI-Ausgabewarteschlange nicht verfügbar."),
            );
            return Err(CommandError::new(
                "queue_full",
                "MIDI-Ausgabewarteschlange nicht verfügbar.",
            ));
        }
        let result = rx.recv_timeout(timeout).unwrap_or_else(|_| {
            Err(CommandError::new("transport_timeout","Die MIDI-Sendezeit wurde überschritten; der Port bleibt bis zur Freigabe quarantined."))
        });
        if let Err(ref e) = result {
            self.fail(&session, e);
        }
        result
    }
    pub fn read(&self, session_id: &str, sequence: u64) -> Result<Vec<u8>, CommandError> {
        let state = self
            .0
            .credits
            .state
            .lock()
            .map_err(|_| CommandError::new("driver_error", "MIDI-Empfang nicht verfügbar."))?;
        state
            .outstanding
            .get(&sequence)
            .filter(|entry| entry.session == session_id && entry.attempted)
            .and_then(|entry| entry.payload.clone())
            .ok_or_else(|| {
                CommandError::new(
                    "invalid_session",
                    "MIDI-Nachricht ist nicht mehr verfügbar.",
                )
            })
    }
    pub fn ack(&self, session_id: &str, sequence: u64) -> Result<(), CommandError> {
        self.0.credits.ack(session_id, sequence)
    }
    pub fn close(&self, id: &str) -> Result<CloseResult, CommandError> {
        let session = {
            let state =
                self.0.state.lock().map_err(|_| {
                    CommandError::new("driver_error", "MIDI-Zustand nicht verfügbar.")
                })?;
            state
                .held
                .iter()
                .find(|s| s.id == id)
                .cloned()
                .or_else(|| state.active.as_ref().filter(|s| s.id == id).cloned())
                .ok_or_else(|| CommandError::new("invalid_session", "Unbekannte MIDI-Sitzung."))?
        };
        session.active.store(false, Ordering::SeqCst);
        let start = Instant::now();
        while !session.released.load(Ordering::SeqCst)
            && start.elapsed() < self.0.config.close_timeout
        {
            std::thread::sleep(Duration::from_millis(2));
        }
        Ok(CloseResult {
            state: if session.released.load(Ordering::SeqCst) {
                "closed"
            } else {
                "quarantined"
            },
        })
    }
    pub fn invalidate(&self) {
        if let Ok(mut state) = self.0.state.lock() {
            state.epoch = state.epoch.wrapping_add(1);
            state.loading = true;
            for s in &state.held {
                s.active.store(false, Ordering::SeqCst);
            }
        }
    }
    pub fn document_loaded(&self) {
        if let Ok(mut state) = self.0.state.lock() {
            if state.loading {
                if let Ok(mut credits) = self.0.credits.state.lock() {
                    credits.outstanding.clear();
                    credits.bytes = 0;
                }
                state.loading = false;
            }
        }
    }
    pub fn shutdown(&self) {
        if let Ok(mut state) = self.0.state.lock() {
            state.shutdown = true;
            for s in &state.held {
                s.active.store(false, Ordering::SeqCst);
            }
        }
    }
}
fn dispatch_events(session: Arc<Session>, rx: Receiver<Incoming>) {
    loop {
        let active = session.active.load(Ordering::SeqCst);
        if session.overflow.load(Ordering::SeqCst) {
            let _=(session.sink)(Event::Error{session_id:session.id.clone(),code:"input_overflow".into(),message:"MIDI-Eingabe überschreitet die begrenzte Warteschlange oder enthält eine ungültige Nachricht.".into()});
            break;
        }
        if let Some(event) = session
            .terminal
            .lock()
            .ok()
            .and_then(|mut terminal| terminal.take())
        {
            session.active.store(false, Ordering::SeqCst);
            let _ = (session.sink)(event);
            break;
        }
        if !active {
            break;
        }
        match rx.recv_timeout(Duration::from_millis(10)) {
            Ok(mut incoming) => {
                if !session.active.load(Ordering::SeqCst) {
                    continue;
                }
                if incoming.credit.attempt(&incoming.bytes).is_err() {
                    session.active.store(false, Ordering::SeqCst);
                    break;
                }
                let event = Event::Message {
                    session_id: session.id.clone(),
                    sequence: incoming.credit.sequence,
                    bytes: incoming.bytes,
                };
                if (session.sink)(event).is_err() {
                    session.active.store(false, Ordering::SeqCst);
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                if session.active.swap(false, Ordering::SeqCst) {
                    let _ = (session.sink)(Event::Error {
                        session_id: session.id.clone(),
                        code: "driver_error".into(),
                        message: "Der MIDI-Treiber wurde unerwartet beendet.".into(),
                    });
                    break;
                }
                continue;
            }
        }
    }
}
#[derive(Default)]
struct Framer {
    pending: Vec<u8>,
    expected: usize,
}
impl Framer {
    fn feed(
        &mut self,
        bytes: &[u8],
        mut emit: impl FnMut(Vec<u8>) -> Result<(), ()>,
    ) -> Result<(), ()> {
        for &byte in bytes {
            if byte >= 0xf8 {
                emit(vec![byte])?;
                continue;
            }
            if self.pending.is_empty() {
                self.expected = match byte {
                    0x80..=0xbf | 0xe0..=0xef => 3,
                    0xc0..=0xdf | 0xf1 | 0xf3 => 2,
                    0xf2 => 3,
                    0xf6 => 1,
                    0xf0 => MAX_FRAME,
                    _ => return Err(()),
                };
                self.pending.push(byte);
            } else {
                if byte >= 0x80 && !(self.pending[0] == 0xf0 && byte == 0xf7) {
                    return Err(());
                }
                if self.pending.len() >= MAX_FRAME {
                    return Err(());
                }
                self.pending.push(byte);
            }
            if (self.pending[0] == 0xf0 && byte == 0xf7)
                || (self.pending[0] != 0xf0 && self.pending.len() == self.expected)
            {
                let frame = std::mem::take(&mut self.pending);
                validate_frame(&frame).map_err(|_| ())?;
                emit(frame)?;
            }
        }
        Ok(())
    }
}
#[derive(Debug, Serialize)]
pub struct CloseResult {
    pub state: &'static str,
}
pub fn validate_frame(bytes: &[u8]) -> Result<(), CommandError> {
    if bytes.is_empty() || bytes.len() > MAX_FRAME {
        return Err(CommandError::new(
            "invalid_message",
            "Ungültige MIDI-Nachrichtenlänge.",
        ));
    }
    let status = bytes[0];
    let size = match status {
        0x80..=0xbf | 0xe0..=0xef => 3,
        0xc0..=0xdf | 0xf1 | 0xf3 => 2,
        0xf2 => 3,
        0xf6 | 0xf8..=0xff => 1,
        0xf0 => bytes.len(),
        _ => 0,
    };
    let data_end = if status == 0xf0 {
        if bytes.len() < 2 || bytes.last() != Some(&0xf7) {
            return Err(CommandError::new(
                "invalid_message",
                "Unvollständige SysEx-Nachricht.",
            ));
        }
        bytes.len() - 1
    } else {
        bytes.len()
    };
    if bytes.len() != size || bytes[1..data_end].iter().any(|b| *b >= 0x80) {
        return Err(CommandError::new(
            "invalid_message",
            "Ungültige MIDI-Nachricht.",
        ));
    }
    Ok(())
}
pub fn trusted_origin(label: &str, address: &str) -> bool {
    let Ok(url) = tauri::Url::parse(address) else {
        return false;
    };
    label == "main"
        && url.username().is_empty()
        && url.password().is_none()
        && url.port().is_none()
        && matches!(
            (url.scheme(), url.host_str()),
            ("tauri", Some("localhost")) | ("http" | "https", Some("tauri.localhost"))
        )
        && matches!(url.path(), "" | "/" | "/index.html")
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Default)]
    struct Fake {
        sends: AtomicUsize,
        opens: AtomicUsize,
        lists: AtomicUsize,
        list_blocked: AtomicBool,
        open_blocked: AtomicBool,
        fail: AtomicBool,
        blocked: AtomicBool,
        release: AtomicBool,
        removed: AtomicBool,
        drop_blocked: AtomicBool,
        callback: Mutex<Option<InputCallback>>,
    }
    struct FakeConnection(Arc<Fake>);
    impl Connection for FakeConnection {
        fn send(&mut self, bytes: &[u8], _active: &AtomicBool) -> Result<(), String> {
            self.0.sends.fetch_add(1, Ordering::SeqCst);
            if self.0.blocked.load(Ordering::SeqCst) {
                while !self.0.release.load(Ordering::SeqCst) {
                    std::thread::sleep(Duration::from_millis(1));
                }
            }
            if self.0.fail.load(Ordering::SeqCst) {
                return Err("driver rejected".into());
            }
            if let Some(callback) = self.0.callback.lock().unwrap().as_mut() {
                callback(bytes);
            }
            Ok(())
        }
        fn connected(&mut self) -> Result<bool, String> {
            Ok(!self.0.removed.load(Ordering::SeqCst))
        }
    }
    impl Drop for FakeConnection {
        fn drop(&mut self) {
            while self.0.drop_blocked.load(Ordering::SeqCst) {
                std::thread::sleep(Duration::from_millis(1));
            }
            self.0.callback.lock().unwrap().take();
        }
    }
    impl Driver for Arc<Fake> {
        fn list(&self) -> Result<Ports, String> {
            self.lists.fetch_add(1, Ordering::SeqCst);
            while self.list_blocked.load(Ordering::SeqCst) {
                std::thread::sleep(Duration::from_millis(1));
            }
            Ok(Ports {
                inputs: vec![Port {
                    id: "in".into(),
                    name: "own input".into(),
                }],
                outputs: vec![Port {
                    id: "out".into(),
                    name: "own output".into(),
                }],
            })
        }
        fn open(
            &self,
            _i: &str,
            _o: &str,
            cb: InputCallback,
        ) -> Result<Box<dyn Connection>, String> {
            self.opens.fetch_add(1, Ordering::SeqCst);
            while self.open_blocked.load(Ordering::SeqCst) {
                std::thread::sleep(Duration::from_millis(1));
            }
            *self.callback.lock().unwrap() = Some(cb);
            Ok(Box::new(FakeConnection(self.clone())))
        }
    }
    fn setup() -> (MidiService, Arc<Fake>, mpsc::Receiver<Event>) {
        let fake = Arc::new(Fake::default());
        let config = Config {
            open_timeout: Duration::from_millis(50),
            list_timeout: Duration::from_millis(50),
            close_timeout: Duration::from_millis(25),
            send_base: Duration::from_millis(40),
            send_per_byte: Duration::ZERO,
            poll: Duration::from_millis(10),
        };
        let service = MidiService::new(Arc::new(fake.clone()), config);
        let (_tx, rx) = mpsc::channel();
        (service, fake, rx)
    }
    fn open(service: &MidiService) -> (String, mpsc::Receiver<Event>) {
        let (tx, rx) = mpsc::channel();
        let id = service
            .open(
                "in".into(),
                "out".into(),
                Arc::new(move |e| tx.send(e).map_err(|e| e.to_string())),
            )
            .unwrap();
        (id, rx)
    }
    fn close_released(service: &MidiService, id: &str) {
        service.close(id).unwrap();
        until(|| {
            service
                .close(id)
                .is_ok_and(|result| result.state == "closed")
        });
    }
    fn until(condition: impl Fn() -> bool) {
        let start = Instant::now();
        while !condition() {
            assert!(start.elapsed() < Duration::from_secs(2));
            std::thread::sleep(Duration::from_millis(2));
        }
    }
    #[test]
    fn os_completion_is_required_and_parallel_sends_are_rejected() {
        let (service, fake, _) = setup();
        let (id, _rx) = open(&service);
        fake.blocked.store(true, Ordering::SeqCst);
        let sender = service.clone();
        let session_id = id.clone();
        let (done_tx, done_rx) = mpsc::channel();
        let thread = std::thread::spawn(move || {
            done_tx
                .send(sender.send(&session_id, vec![0x90, 60, 127]))
                .unwrap();
        });
        until(|| fake.sends.load(Ordering::SeqCst) == 1);
        assert!(done_rx.try_recv().is_err());
        assert!(service
            .send(&id, vec![0x90, 60, 0])
            .unwrap_err()
            .message
            .contains("belegt"));
        fake.release.store(true, Ordering::SeqCst);
        done_rx
            .recv_timeout(Duration::from_secs(1))
            .unwrap()
            .unwrap();
        thread.join().unwrap();
        assert_eq!(fake.sends.load(Ordering::SeqCst), 1);
        close_released(&service, &id);
    }
    #[test]
    fn hung_enumerations_cannot_create_unbounded_workers() {
        let (service, fake, _) = setup();
        fake.list_blocked.store(true, Ordering::SeqCst);
        assert!(service.list().unwrap_err().code == "transport_timeout");
        assert!(service.list().unwrap_err().code == "transport_timeout");
        assert!(service.list().unwrap_err().message.contains("belegt"));
        assert!(service
            .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
            .is_err());
        assert_eq!(fake.lists.load(Ordering::SeqCst), MAX_WORKERS);
        fake.list_blocked.store(false, Ordering::SeqCst);
        until(|| service.0.workers.load(Ordering::SeqCst) == 0);
        assert_eq!(service.list().unwrap().inputs[0].id, "in");
    }
    #[test]
    fn timed_out_open_stays_quarantined_and_old_document_cannot_reopen() {
        let (service, fake, _) = setup();
        fake.open_blocked.store(true, Ordering::SeqCst);
        assert!(
            service
                .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
                .unwrap_err()
                .code
                == "transport_timeout"
        );
        assert!(service
            .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
            .unwrap_err()
            .message
            .contains("quarant"));
        fake.open_blocked.store(false, Ordering::SeqCst);
        until(|| service.0.workers.load(Ordering::SeqCst) == 0);
        let epoch = service.epoch().unwrap();
        service.invalidate();
        assert!(service
            .open_for_document(epoch, "in".into(), "out".into(), Arc::new(|_| Ok(())))
            .is_err());
        assert_eq!(fake.opens.load(Ordering::SeqCst), 1);
        service.document_loaded();
        let (id, _) = open(&service);
        close_released(&service, &id);
    }
    #[test]
    fn stalled_event_delivery_never_blocks_native_callback_and_overflow_is_terminal() {
        let (service, fake, _) = setup();
        let blocked = Arc::new(AtomicBool::new(false));
        let release = Arc::new(AtomicBool::new(false));
        let block = blocked.clone();
        let resume = release.clone();
        let (tx, rx) = mpsc::channel();
        let id = service
            .open(
                "in".into(),
                "out".into(),
                Arc::new(move |event| {
                    if matches!(&event, Event::Message { .. }) {
                        block.store(true, Ordering::SeqCst);
                        while !resume.load(Ordering::SeqCst) {
                            std::thread::sleep(Duration::from_millis(1));
                        }
                    }
                    tx.send(event).map_err(|e| e.to_string())
                }),
            )
            .unwrap();
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        until(|| blocked.load(Ordering::SeqCst));
        {
            let mut callback = fake.callback.lock().unwrap();
            for _ in 0..INBOUND_QUEUE + 2 {
                callback.as_mut().unwrap()(&[0x90, 60, 127]);
            }
        }
        assert!(service.send(&id, vec![0x90, 60, 0]).is_err());
        release.store(true, Ordering::SeqCst);
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(1)).unwrap(),
            Event::Message { .. }
        ));
        assert!(
            matches!(rx.recv_timeout(Duration::from_secs(1)).unwrap(),Event::Error{code,..} if code=="input_overflow")
        );
        close_released(&service, &id);
    }
    #[test]
    fn disconnect_survives_a_full_inbound_queue_and_invalidates_immediately() {
        let (service, fake, _) = setup();
        let blocked = Arc::new(AtomicBool::new(false));
        let release = Arc::new(AtomicBool::new(false));
        let acker = service.clone();
        let block = blocked.clone();
        let resume = release.clone();
        let (tx, rx) = mpsc::channel();
        let id = service
            .open(
                "in".into(),
                "out".into(),
                Arc::new(move |event| {
                    if let Event::Message {
                        session_id,
                        sequence,
                        ..
                    } = &event
                    {
                        acker.ack(session_id, *sequence).unwrap();
                    }
                    if matches!(&event, Event::Message { .. }) {
                        block.store(true, Ordering::SeqCst);
                        while !resume.load(Ordering::SeqCst) {
                            std::thread::sleep(Duration::from_millis(1));
                        }
                    }
                    tx.send(event).map_err(|e| e.to_string())
                }),
            )
            .unwrap();
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        until(|| blocked.load(Ordering::SeqCst));
        for _ in 0..INBOUND_QUEUE {
            fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        }
        fake.removed.store(true, Ordering::SeqCst);
        until(|| service.0.workers.load(Ordering::SeqCst) == 0);
        let invalid = service.session(&id).is_err();
        release.store(true, Ordering::SeqCst);
        assert!(
            invalid,
            "Disconnected owner must invalidate even with a full receive queue"
        );
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(1)).unwrap(),
            Event::Message { .. }
        ));
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(1)).unwrap(),
            Event::Disconnected { .. }
        ));
        close_released(&service, &id);
    }
    #[test]
    fn nonblocking_renderer_without_ack_has_one_global_bound_across_sessions() {
        let (service, fake, _) = setup();
        for _ in 0..4 {
            let (id, rx) = open(&service);
            for _ in 0..INBOUND_QUEUE / 4 {
                fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
                assert!(matches!(
                    rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                    Event::Message { .. }
                ));
            }
            close_released(&service, &id);
        }
        let (id, rx) = open(&service);
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        assert!(
            matches!(
                rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                Event::Error { .. }
            ),
            "Previously queued renderer data must retain credit after reopening"
        );
        close_released(&service, &id);
    }
    #[test]
    fn matching_ack_frees_credit_even_for_a_closed_prior_session() {
        let (service, fake, _) = setup();
        let (id, rx) = open(&service);
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        let Event::Message { sequence, .. } = rx.recv_timeout(Duration::from_secs(1)).unwrap()
        else {
            panic!("message missing")
        };
        assert_eq!(service.read(&id, sequence).unwrap(), [0x90, 60, 127]);
        assert!(service.read("wrong-session", sequence).is_err());
        assert!(service.ack("wrong-session", sequence).is_err());
        assert!(service.ack(&id, sequence + 1).is_err());
        close_released(&service, &id);
        service.ack(&id, sequence).unwrap();
        assert!(service.read(&id, sequence).is_err());
        assert!(service.ack(&id, sequence).is_err());
        let (next, rx) = open(&service);
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        let Event::Message {
            sequence: next_sequence,
            ..
        } = rx.recv_timeout(Duration::from_secs(1)).unwrap()
        else {
            panic!("message missing")
        };
        assert!(next_sequence > sequence);
        service.ack(&next, next_sequence).unwrap();
        close_released(&service, &next);
    }
    #[test]
    fn completed_document_load_recovers_unacknowledged_frames() {
        let (service, fake, _) = setup();
        let (id, rx) = open(&service);
        for _ in 0..INBOUND_QUEUE {
            fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
            assert!(matches!(
                rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                Event::Message { .. }
            ));
        }
        service.invalidate();
        assert!(service.epoch().is_err());
        close_released(&service, &id);
        service.document_loaded();
        let (next, rx) = open(&service);
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(1)).unwrap(),
            Event::Message { .. }
        ));
        close_released(&service, &next);
    }

    #[test]
    fn unacknowledged_large_frames_keep_global_byte_credit_after_nonblocking_sink() {
        let (service, fake, _) = setup();
        let (id, rx) = open(&service);
        let mut frame = vec![0x55; MAX_FRAME];
        frame[0] = 0xf0;
        *frame.last_mut().unwrap() = 0xf7;
        for _ in 0..2 {
            fake.callback.lock().unwrap().as_mut().unwrap()(&frame);
            assert!(matches!(
                rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                Event::Message { .. }
            ));
        }
        fake.callback.lock().unwrap().as_mut().unwrap()(&[0x90, 60, 127]);
        assert!(
            matches!(
                rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                Event::Error { .. }
            ),
            "Byte budget must stay reserved while Tauri awaits renderer delivery"
        );
        close_released(&service, &id);
    }
    #[test]
    fn command_errors_have_explicit_codes_and_timeouts_keep_their_event_code() {
        let (service, fake, _) = setup();
        assert_eq!(
            serde_json::to_value(service.send("missing", vec![0xf0]).unwrap_err()).unwrap()["code"],
            "invalid_message"
        );
        assert_eq!(
            serde_json::to_value(service.send("missing", vec![0x90, 60, 0]).unwrap_err()).unwrap()
                ["code"],
            "invalid_session"
        );
        assert_eq!(
            serde_json::to_value(
                service
                    .open("missing".into(), "out".into(), Arc::new(|_| Ok(())))
                    .unwrap_err()
            )
            .unwrap()["code"],
            "port_missing"
        );
        let (id, rx) = open(&service);
        assert_eq!(
            serde_json::to_value(
                service
                    .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
                    .unwrap_err()
            )
            .unwrap()["code"],
            "busy"
        );
        fake.blocked.store(true, Ordering::SeqCst);
        let error = service.send(&id, vec![0x90, 60, 127]).unwrap_err();
        fake.release.store(true, Ordering::SeqCst);
        assert_eq!(
            serde_json::to_value(error).unwrap()["code"],
            "transport_timeout"
        );
        assert!(
            matches!(rx.recv_timeout(Duration::from_secs(1)).unwrap(),Event::Error{code,..} if code=="transport_timeout")
        );
        close_released(&service, &id);
    }
    #[test]
    fn accepts_bounded_complete_messages_and_rejects_bad_frames() {
        assert!(validate_frame(&[0x90, 60, 127]).is_ok());
        assert!(validate_frame(&[0xf0, 1, 2, 0xf7]).is_ok());
        for invalid in [
            vec![],
            vec![0xf0, 1],
            vec![0xf0, 0x80, 0xf7],
            vec![0x90, 60],
            vec![1, 2, 3],
            vec![0xf0; MAX_FRAME + 1],
        ] {
            assert!(validate_frame(&invalid).is_err());
        }
    }
    #[test]
    fn only_local_main_document_can_use_device_commands() {
        assert!(trusted_origin("main", "tauri://localhost"));
        assert!(trusted_origin(
            "main",
            "tauri://localhost/index.html#emu=123:secret"
        ));
        assert!(trusted_origin("main", "http://tauri.localhost/index.html"));
        for (label, url) in [
            ("emulator", "tauri://localhost/index.html"),
            ("main", "https://evil.test"),
            ("main", "http://127.0.0.1:8080/index.html"),
            ("main", "tauri://localhost/evil.html"),
            ("main", "https://tauri.localhost.evil.test/index.html"),
        ] {
            assert!(!trusted_origin(label, url));
        }
    }
    #[test]
    fn sends_after_os_completion_and_uses_session_identity() {
        let (s, f, _) = setup();
        let (id, rx) = open(&s);
        s.send(&id, vec![0xf0, 1, 0xf7]).unwrap();
        assert_eq!(f.sends.load(Ordering::SeqCst), 1);
        assert!(
            matches!(rx.recv_timeout(Duration::from_millis(200)).unwrap(),Event::Message{session_id,bytes,..} if session_id==id && bytes==[0xf0,1,0xf7])
        );
        assert!(s.send("old-session", vec![0x90, 1, 2]).is_err());
        close_released(&s, &id);
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
    }
    #[test]
    fn invalid_port_and_frame_never_reach_driver() {
        let (s, f, _) = setup();
        assert!(s
            .open("missing".into(), "out".into(), Arc::new(|_| Ok(())))
            .is_err());
        assert_eq!(f.opens.load(Ordering::SeqCst), 0);
        let (id, _) = open(&s);
        assert!(s.send(&id, vec![0xf0, 1]).is_err());
        assert_eq!(f.sends.load(Ordering::SeqCst), 0);
        close_released(&s, &id);
    }
    #[test]
    fn timeout_invalidates_session_and_quarantines_ports_until_drop_finishes() {
        let (s, f, _) = setup();
        let (id, _) = open(&s);
        f.blocked.store(true, Ordering::SeqCst);
        assert!(s.send(&id, vec![0x90, 1, 2]).unwrap_err().code == "transport_timeout");
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
        assert!(s
            .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
            .unwrap_err()
            .message
            .contains("quarant"));
        assert_eq!(s.close(&id).unwrap().state, "quarantined");
        f.release.store(true, Ordering::SeqCst);
        until(|| {
            s.open("in".into(), "out".into(), Arc::new(|_| Ok(())))
                .is_ok()
        });
        s.invalidate();
    }
    #[test]
    fn close_and_reload_invalidate_before_blocked_drop_returns() {
        let (s, f, _) = setup();
        let (id, _) = open(&s);
        f.drop_blocked.store(true, Ordering::SeqCst);
        assert_eq!(s.close(&id).unwrap().state, "quarantined");
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
        assert!(s
            .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
            .is_err());
        f.drop_blocked.store(false, Ordering::SeqCst);
        until(|| {
            s.open("in".into(), "out".into(), Arc::new(|_| Ok(())))
                .is_ok()
        });
        s.invalidate();
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
    }
    #[test]
    fn send_error_and_unplug_are_terminal_without_retry() {
        let (s, f, _) = setup();
        let (id, rx) = open(&s);
        f.fail.store(true, Ordering::SeqCst);
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
        assert!(matches!(
            rx.recv_timeout(Duration::from_millis(200)).unwrap(),
            Event::Error { .. }
        ));
        assert_eq!(f.sends.load(Ordering::SeqCst), 1);
        close_released(&s, &id);
        f.fail.store(false, Ordering::SeqCst);
        let (id, rx) = open(&s);
        f.removed.store(true, Ordering::SeqCst);
        assert!(matches!(
            rx.recv_timeout(Duration::from_millis(200)).unwrap(),
            Event::Disconnected { .. }
        ));
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
        close_released(&s, &id);
    }
    #[test]
    fn ingress_reassembles_sysex_and_drops_late_session_callbacks() {
        let (s, f, _) = setup();
        let (id, rx) = open(&s);
        {
            let mut lock = f.callback.lock().unwrap();
            let cb = lock.as_mut().unwrap();
            cb(&[0xf0, 1]);
            cb(&[2, 0xf7]);
        }
        assert!(
            matches!(rx.recv_timeout(Duration::from_millis(200)).unwrap(),Event::Message{bytes,..} if bytes==[0xf0,1,2,0xf7])
        );
        let mut late_callback = f.callback.lock().unwrap().take().unwrap();
        close_released(&s, &id);
        late_callback(&[0x90, 1, 2]);
        assert!(rx.try_recv().is_err());
    }
    #[test]
    fn shutdown_never_reopens_and_native_callbacks_are_bounded() {
        let (s, f, _) = setup();
        let (id, rx) = open(&s);
        {
            let mut cb = f.callback.lock().unwrap();
            cb.as_mut().unwrap()(&vec![0xf0; MAX_FRAME + 1]);
        }
        assert!(matches!(
            rx.recv_timeout(Duration::from_millis(200)).unwrap(),
            Event::Error { .. }
        ));
        assert!(s.send(&id, vec![0x90, 1, 2]).is_err());
        s.shutdown();
        assert!(s
            .open("in".into(), "out".into(), Arc::new(|_| Ok(())))
            .is_err());
    }
}
