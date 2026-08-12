//! Non-secret daemon configuration (SPEC-106 §2): loaded from a JSON file
//! in Tauri's own `app_config_dir`, injected into the daemon at spawn as a
//! single environment variable -- see `daemon.rs`'s `spawn_daemon` for how
//! it's actually applied, and `secrets.rs` for the OS-keychain-backed
//! counterpart this deliberately doesn't hold.
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// Env var name the daemon reads its non-secret config from at startup.
/// Must match `_DAEMON_CONFIG_ENV_VAR` in `services/python-daemon/daemon.py`.
pub const DAEMON_CONFIG_ENV_VAR: &str = "HAS_DAEMON_CONFIG";

#[derive(Debug, Default, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct DaemonConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub freecadcmd_path_override: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kicad_socket_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kicad_timeout_ms: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub llm_provider: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub llm_model: Option<String>,
    /// Where `freecad_bridge.generate_enclosure` (SPEC-301 §2) writes its
    /// `.glb` output -- unlike every other field above, this is never
    /// read from `config.json`; `spawn_daemon` always overwrites it with
    /// `resolve_output_dir`'s real, Rust-computed value before this
    /// struct is serialized. Kept on this struct anyway rather than as a
    /// second env var, reusing the one injection mechanism CTX-106.1
    /// already established instead of adding a parallel one for a single
    /// path.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_dir: Option<String>,
}

/// `AppHandle`-free core of `load_config`, directly unit-testable against
/// a real (temporary) filesystem directory rather than a live Tauri app --
/// the same split this file already uses for `ensure_output_dir`.
fn load_config_from_dir(dir: &std::path::Path) -> DaemonConfig {
    match std::fs::read_to_string(dir.join("config.json")) {
        Ok(contents) => serde_json::from_str(&contents).unwrap_or_default(),
        Err(_) => DaemonConfig::default(),
    }
}

/// Loads `config.json` from the app's own config directory, defaulting to
/// an all-`None` config if the file doesn't exist yet (first run) -- not
/// an error, since there's nothing wrong with never having configured
/// anything.
pub fn load_config(app: &AppHandle) -> DaemonConfig {
    match app.path().app_config_dir() {
        Ok(dir) => load_config_from_dir(&dir),
        Err(_) => DaemonConfig::default(),
    }
}

/// `AppHandle`-free core of `save_config`; see `load_config_from_dir`.
fn save_config_to_dir(dir: &std::path::Path, config: &DaemonConfig) -> std::io::Result<()> {
    std::fs::create_dir_all(dir)?;
    let json = serde_json::to_string_pretty(config).map_err(std::io::Error::other)?;
    std::fs::write(dir.join("config.json"), json)
}

/// Writes `config` to `config.json` in the app's own config directory
/// (SPEC-303) -- `load_config` above only ever read this file; nothing
/// wrote it until now. `output_dir` is included if set, but harmless
/// either way -- `spawn_daemon` always overwrites it with the real,
/// Rust-computed value before it's ever serialized for the daemon.
pub fn save_config(app: &AppHandle, config: &DaemonConfig) -> std::io::Result<()> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| std::io::Error::other(e.to_string()))?;
    save_config_to_dir(&dir, config)
}

/// Tauri command wrapper so the Settings UI (SPEC-303) can read the
/// current non-secret configuration to prefill its form.
#[tauri::command]
pub fn get_config(app: AppHandle) -> DaemonConfig {
    load_config(&app)
}

/// Tauri command wrapper around `save_config`.
#[tauri::command]
pub fn save_config_cmd(app: AppHandle, config: DaemonConfig) -> Result<(), String> {
    save_config(&app, &config).map_err(|e| e.to_string())
}

/// Serializes `config` into the single env var the daemon reads at
/// startup. A pure function, independent of any real `Command` or
/// filesystem, so it's directly unit-testable without spawning anything.
pub fn build_daemon_env(config: &DaemonConfig) -> Vec<(String, String)> {
    match serde_json::to_string(config) {
        Ok(json) => vec![(DAEMON_CONFIG_ENV_VAR.to_string(), json)],
        Err(_) => Vec::new(),
    }
}

/// Creates (if missing) and returns `<app_data_dir>/generated` -- the app
/// -owned directory `generate_enclosure`'s `.glb` output moves into
/// (SPEC-301 §2), so `tauri.conf.json`'s `assetProtocol.scope` can be
/// narrowed to exactly this directory instead of the whole shared OS temp
/// directory. The directory-creation logic is split out as its own
/// function, independent of any real `AppHandle`, so it's directly
/// unit-testable against a real (temporary) filesystem path.
pub fn ensure_output_dir(app_data_dir: &std::path::Path) -> std::io::Result<std::path::PathBuf> {
    let dir = app_data_dir.join("generated");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

/// The `AppHandle`-dependent half of `ensure_output_dir` -- resolves the
/// app's real data directory via Tauri's own `$APPDATA` path variable
/// (the same one `tauri.conf.json`'s `assetProtocol.scope` uses), so the
/// two are guaranteed to agree on exactly the same directory.
pub fn resolve_output_dir(app: &AppHandle) -> Option<String> {
    let app_data_dir = app.path().app_data_dir().ok()?;
    let dir = ensure_output_dir(&app_data_dir).ok()?;
    Some(dir.to_string_lossy().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn save_config_to_dir_and_load_config_from_dir_round_trip_a_real_file() {
        let base = std::env::temp_dir().join(format!("ctx-303.1-config-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let config = DaemonConfig {
            freecadcmd_path_override: Some("/opt/freecad/bin/freecadcmd".to_string()),
            kicad_socket_path: Some("/tmp/kicad/api.sock".to_string()),
            kicad_timeout_ms: Some(5000),
            llm_provider: Some("anthropic".to_string()),
            llm_model: Some("claude-sonnet".to_string()),
            output_dir: None,
        };

        save_config_to_dir(&base, &config).expect("save_config_to_dir should succeed");
        let loaded = load_config_from_dir(&base);

        assert_eq!(loaded, config);
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn load_config_from_dir_defaults_cleanly_when_no_file_exists_yet() {
        let base = std::env::temp_dir().join(format!("ctx-303.1-config-missing-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let loaded = load_config_from_dir(&base);
        assert_eq!(loaded, DaemonConfig::default());
    }

    #[test]
    fn build_daemon_env_serializes_set_fields_and_omits_unset_ones() {
        let config = DaemonConfig {
            freecadcmd_path_override: Some("/opt/freecad/bin/freecadcmd".to_string()),
            kicad_socket_path: None,
            kicad_timeout_ms: Some(5000),
            llm_provider: None,
            llm_model: None,
            output_dir: Some("/app/data/generated".to_string()),
        };

        let env = build_daemon_env(&config);
        assert_eq!(env.len(), 1);
        let (name, value) = &env[0];
        assert_eq!(name, DAEMON_CONFIG_ENV_VAR);

        let parsed: serde_json::Value = serde_json::from_str(value).unwrap();
        assert_eq!(parsed["freecadcmd_path_override"], "/opt/freecad/bin/freecadcmd");
        assert_eq!(parsed["kicad_timeout_ms"], 5000);
        assert_eq!(parsed["output_dir"], "/app/data/generated");
        assert!(
            parsed.get("kicad_socket_path").is_none(),
            "unset fields should be omitted, not serialized as null"
        );
    }

    #[test]
    fn build_daemon_env_of_an_all_default_config_is_an_empty_json_object() {
        let env = build_daemon_env(&DaemonConfig::default());
        let (_, value) = &env[0];
        assert_eq!(value, "{}");
    }

    #[test]
    fn ensure_output_dir_creates_the_generated_subdirectory_for_real() {
        let base = std::env::temp_dir().join(format!("ctx-301.1-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base); // in case a previous run left it behind

        let created = ensure_output_dir(&base).expect("ensure_output_dir should succeed");

        assert_eq!(created, base.join("generated"));
        assert!(created.is_dir(), "the directory should really exist on disk");

        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn ensure_output_dir_is_idempotent() {
        let base = std::env::temp_dir().join(format!("ctx-301.1-test-idempotent-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        ensure_output_dir(&base).expect("first call should succeed");
        let second = ensure_output_dir(&base).expect("calling it again should not error");

        assert!(second.is_dir());
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }
}
