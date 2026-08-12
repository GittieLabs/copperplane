mod config;
mod daemon;
mod secrets;
mod supervisor;

use std::path::PathBuf;

use daemon::DaemonHandle;
use tauri::Manager;

/// Path to the Python daemon script, resolved relative to this crate's own
/// manifest directory rather than the process's current working directory,
/// so `cargo tauri dev` behaves the same no matter where it's invoked from.
fn daemon_script_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../services/python-daemon/daemon.py")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let daemon_handle = daemon::spawn_daemon(app.handle(), daemon_script_path())?;
            app.manage(daemon_handle);

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            daemon::dispatch_to_daemon,
            secrets::save_secret,
            secrets::clear_secret,
            config::get_config,
            config::save_config_cmd,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // macOS crash shield: RunEvent::Exit only fires on a graceful
            // quit, so it's a backstop layered on top of (not a
            // replacement for) the Linux prctl / Windows Job Object paths.
            // Full crash coverage on macOS additionally needs the
            // Python-side heartbeat noted in SPEC-101 — tracked as a
            // follow-up in this feature's CTX file.
            if let tauri::RunEvent::Exit = event {
                if let Some(daemon_handle) = app_handle.try_state::<DaemonHandle>() {
                    daemon_handle.shutdown();
                }
            }
        });
}
