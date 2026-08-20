mod config;
mod daemon;
mod menu;
mod secrets;
mod supervisor;

use daemon::DaemonHandle;
use tauri::Manager;

/// The app version the Settings screen's "Copy Diagnostics" (SPEC-303
/// Tier 3) includes -- a compile-time constant from this crate's own
/// Cargo.toml, not a value read from disk at runtime.
#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// CTX-309.4: real user feedback exercising the actual running app --
/// someone new to KiCad had no way to tell that "not reachable" meant
/// "KiCad isn't even open," and the app never offered to open it. macOS
/// uses the standard `open -a KiCad` Launch Services lookup by app name
/// -- confirmed working directly on this dev machine (KiCad's own real
/// process appeared within ~2s of running it). Windows/Linux fall back
/// to invoking `kicad` directly, relying on PATH the same way
/// `find_kicad_cli`'s own lookup already does elsewhere in this app --
/// **not verified on those platforms**, named honestly here rather than
/// silently assumed to work the same way.
#[tauri::command]
fn open_kicad() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let result = std::process::Command::new("open").args(["-a", "KiCad"]).spawn();

    #[cfg(not(target_os = "macos"))]
    let result = std::process::Command::new("kicad").spawn();

    result.map(|_| ()).map_err(|e| format!("Could not launch KiCad: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .menu(|app| menu::build_menu(app))
        .on_menu_event(|app, event| menu::handle_menu_event(app, event))
        .setup(|app| {
            // SPEC-402 (CTX-402.2): desktop-only, matching the updater
            // plugin's own real platform support -- registered here
            // rather than in the plugin chain above so it can be guarded
            // by cfg(desktop) without an empty no-op on mobile targets.
            #[cfg(desktop)]
            app.handle()
                .plugin(tauri_plugin_updater::Builder::new().build())?;

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let daemon_handle = daemon::spawn_daemon(app.handle())?;
            app.manage(daemon_handle);

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            daemon::dispatch_to_daemon,
            secrets::save_secret,
            secrets::clear_secret,
            config::get_config,
            config::save_config_cmd,
            get_app_version,
            open_kicad,
            menu::update_library_menu,
            menu::set_design_menu_enabled,
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

#[cfg(test)]
mod tests {
    use super::get_app_version;

    #[test]
    fn get_app_version_matches_this_crates_own_cargo_toml() {
        assert_eq!(get_app_version(), env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn get_app_version_is_not_empty() {
        assert!(!get_app_version().is_empty());
    }
}
