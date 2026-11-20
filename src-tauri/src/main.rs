#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// The desktop app lives in desktop.rs. On Android the app starts from the library (lib.rs, mobile.rs); the build
// there still compiles this binary, so it stays empty for mobile targets.
#[cfg(desktop)]
mod desktop;

fn main() {
    #[cfg(desktop)]
    desktop::main();
}
