//! Non-secret daemon configuration (SPEC-106 §2): loaded from a JSON file
//! in Tauri's own `app_config_dir`, injected into the daemon at spawn as a
//! single environment variable -- see `daemon.rs`'s `spawn_daemon` for how
//! it's actually applied, and `secrets.rs` for the OS-keychain-backed
//! counterpart this deliberately doesn't hold.
use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// SPEC-208 §2.2.1: a provider record, as authored in `config.json`'s new
/// `providers` array. Rust never interprets `kind`/`models`/`capabilities`
/// -- it carries the whole record through to the daemon exactly as it
/// carries every other config field it doesn't read (this file's own
/// module doc). `id: "managed"` is reserved (SPEC-208 §2.2.3) and is the
/// daemon's own concern to reject, not this struct's -- Rust has no
/// opinion on which ids are valid, only that the shape round-trips.
#[derive(Debug, Default, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct ProviderRecord {
    pub id: String,
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key_ref: Option<String>,
    pub models: HashMap<String, String>,
    pub capabilities: HashMap<String, bool>,
}

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
    /// Root directory for SPEC-304's `library/`/`projects/`/`.index/`
    /// tree -- like `output_dir` above, always Rust-computed and never
    /// read from `config.json` directly, so this field and the app's real
    /// data directory can never disagree. `resolve_storage_root` computes
    /// this from `storage_root_override` below when a real, usable
    /// override is set, or from the app's own data directory otherwise
    /// (SPEC-110).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub storage_root: Option<String>,
    /// A user-chosen location for `storage_root` above (SPEC-110), set via
    /// Settings' real native folder picker. `None`/empty means "use the
    /// default app-data-dir location" -- the same override-vs-computed
    /// split `freecadcmd_path_override` already establishes, reused here
    /// for a fourth field rather than a new mechanism. Only read at daemon
    /// spawn, same "restart to apply" contract every other override field
    /// on this struct already has.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub storage_root_override: Option<String>,
    /// SPEC-208 §2.2: replaces the flat `llm_provider`/`llm_model` pair
    /// above, which stay present for one release's migration read
    /// (§2.5) rather than being removed here. `None`/absent is a normal,
    /// pre-SPEC-208 install -- the daemon's own migration logic (not
    /// this struct) is what synthesizes `provider_roles` from the legacy
    /// fields when this is unset.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub providers: Option<Vec<ProviderRecord>>,
    /// SPEC-208 §2.3.2: role name -> provider record id. Always the
    /// complete current map when set, never a partial update -- the same
    /// "always the complete current set" contract `CTX-303.1` already
    /// established for `secrets`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider_roles: Option<HashMap<String, String>>,
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

/// Creates (if missing) and returns `<app_data_dir>/storage` -- the root
/// `services/python-daemon/library_store.py` (SPEC-304) creates its
/// `library/`/`projects/`/`.index/` subdirectories under, lazily, on
/// first write. A sibling of `generated` above, not nested under it --
/// generated `.glb`s are ephemeral job output; this is persistent user
/// data.
pub fn ensure_storage_root(app_data_dir: &std::path::Path) -> std::io::Result<std::path::PathBuf> {
    let dir = app_data_dir.join("storage");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

/// Tries a user-chosen override first (a real `create_dir_all`, not just
/// a string check -- SPEC-110 §3's own named gotcha: a chosen directory
/// that's since become unwritable or unmounted must fall back to the
/// default, not fail the daemon's own startup), falling back to
/// `ensure_storage_root`'s existing computed default on an empty
/// override or a real failure to create/use it.
fn resolve_storage_root_with_override(
    app_data_dir: &std::path::Path,
    override_path: Option<&str>,
) -> Option<String> {
    if let Some(path) = override_path {
        if !path.trim().is_empty() {
            let dir = std::path::PathBuf::from(path);
            if std::fs::create_dir_all(&dir).is_ok() {
                return Some(dir.to_string_lossy().to_string());
            }
        }
    }
    let dir = ensure_storage_root(app_data_dir).ok()?;
    Some(dir.to_string_lossy().to_string())
}

/// The `AppHandle`-dependent half of `resolve_storage_root_with_override`;
/// see `resolve_output_dir`'s own docstring for why the default half of
/// this needs to agree with Tauri's own app-data-dir resolution rather
/// than being computed twice.
pub fn resolve_storage_root(app: &AppHandle, override_path: Option<&str>) -> Option<String> {
    let app_data_dir = app.path().app_data_dir().ok()?;
    resolve_storage_root_with_override(&app_data_dir, override_path)
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
            storage_root: None,
            storage_root_override: Some("/Volumes/External/has-storage".to_string()),
            providers: None,
            provider_roles: None,
        };

        save_config_to_dir(&base, &config).expect("save_config_to_dir should succeed");
        let loaded = load_config_from_dir(&base);

        assert_eq!(loaded, config);
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn save_config_to_dir_and_load_config_from_dir_round_trip_provider_records() {
        // SPEC-208 §2.2.1/§2.5: Rust never interprets `providers`/
        // `provider_roles` -- this proves only that the shape survives a
        // real write/read cycle unchanged, same discipline as the
        // pre-SPEC-208 round-trip test above.
        let base = std::env::temp_dir().join(format!("ctx-208.1-provider-records-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let mut models = HashMap::new();
        models.insert("reasoning".to_string(), "qwen2.5:32b".to_string());
        models.insert("fast".to_string(), "qwen2.5:7b".to_string());
        let mut capabilities = HashMap::new();
        capabilities.insert("tool_use".to_string(), true);
        capabilities.insert("strict_json".to_string(), true);
        let mut provider_roles = HashMap::new();
        provider_roles.insert("reasoning".to_string(), "workshop-ollama".to_string());
        provider_roles.insert("fast".to_string(), "workshop-ollama".to_string());

        let config = DaemonConfig {
            providers: Some(vec![ProviderRecord {
                id: "workshop-ollama".to_string(),
                kind: "openai_compat".to_string(),
                base_url: Some("http://nuc.local:11434/v1".to_string()),
                api_key_ref: None,
                models,
                capabilities,
            }]),
            provider_roles: Some(provider_roles),
            ..Default::default()
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
            storage_root: None,
            storage_root_override: None,
            providers: None,
            provider_roles: None,
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

    #[test]
    fn ensure_storage_root_creates_the_storage_subdirectory_for_real() {
        let base = std::env::temp_dir().join(format!("ctx-304.1-storage-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let created = ensure_storage_root(&base).expect("ensure_storage_root should succeed");

        assert_eq!(created, base.join("storage"));
        assert!(created.is_dir(), "the directory should really exist on disk");

        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn ensure_storage_root_is_idempotent() {
        let base = std::env::temp_dir().join(format!("ctx-304.1-storage-idempotent-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        ensure_storage_root(&base).expect("first call should succeed");
        let second = ensure_storage_root(&base).expect("calling it again should not error");

        assert!(second.is_dir());
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn storage_root_and_output_dir_are_siblings_not_nested() {
        let base = std::env::temp_dir().join(format!("ctx-304.1-siblings-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let storage = ensure_storage_root(&base).expect("ensure_storage_root should succeed");
        let generated = ensure_output_dir(&base).expect("ensure_output_dir should succeed");

        assert_eq!(storage.parent(), generated.parent());
        assert_ne!(storage, generated);
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn resolve_storage_root_with_override_prefers_a_real_creatable_override_over_the_default() {
        let base = std::env::temp_dir().join(format!("ctx-110.1-override-{}", std::process::id()));
        let override_dir = std::env::temp_dir().join(format!("ctx-110.1-override-chosen-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);
        let _ = std::fs::remove_dir_all(&override_dir);

        let resolved = resolve_storage_root_with_override(&base, Some(override_dir.to_str().unwrap()))
            .expect("should resolve");

        assert_eq!(resolved, override_dir.to_string_lossy());
        assert!(override_dir.is_dir(), "the override directory should really exist on disk");
        assert!(!base.join("storage").exists(), "the default location must not be created when an override wins");

        std::fs::remove_dir_all(&override_dir).expect("test cleanup should succeed");
    }

    #[test]
    fn resolve_storage_root_with_override_falls_back_to_the_default_when_override_is_none() {
        let base = std::env::temp_dir().join(format!("ctx-110.1-none-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let resolved = resolve_storage_root_with_override(&base, None).expect("should resolve");

        assert_eq!(resolved, base.join("storage").to_string_lossy());
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn resolve_storage_root_with_override_falls_back_to_the_default_when_override_is_blank() {
        let base = std::env::temp_dir().join(format!("ctx-110.1-blank-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);

        let resolved = resolve_storage_root_with_override(&base, Some("   ")).expect("should resolve");

        assert_eq!(resolved, base.join("storage").to_string_lossy());
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }

    #[test]
    fn resolve_storage_root_with_override_falls_back_to_the_default_when_the_override_cannot_be_created() {
        // A real failure mode, not hypothetical (SPEC-110 §3): a file
        // already sitting at the chosen path means create_dir_all fails,
        // exactly as it would for an unmounted external drive.
        let base = std::env::temp_dir().join(format!("ctx-110.1-fail-{}", std::process::id()));
        let blocked_path = std::env::temp_dir().join(format!("ctx-110.1-fail-blocker-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);
        let _ = std::fs::remove_file(&blocked_path);
        std::fs::write(&blocked_path, b"not a directory").expect("setup write should succeed");

        let resolved = resolve_storage_root_with_override(&base, Some(blocked_path.to_str().unwrap()))
            .expect("should still resolve via the fallback");

        assert_eq!(resolved, base.join("storage").to_string_lossy());

        std::fs::remove_file(&blocked_path).expect("test cleanup should succeed");
        std::fs::remove_dir_all(&base).expect("test cleanup should succeed");
    }
}
