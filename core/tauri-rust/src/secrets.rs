//! OS keychain access for real secrets (API keys), per SPEC-106 §2 --
//! these never touch `config.rs`'s plaintext `config.json` file or the
//! daemon's environment; see `daemon.rs::build_configure_request` for how
//! they're actually handed to the daemon, over its private `stdin` pipe.
use keyring::{Entry, Error as KeyringError};

/// The service name every credential is stored under -- keeps this app's
/// secrets in their own namespace in the OS keychain, distinct from any
/// other app that happens to use the same key names.
const SERVICE: &str = "hardware-agent-studio";

/// Reads a secret from the OS keychain. Returns `Ok(None)` for the normal
/// first-run state (nothing has been stored for this key yet) -- distinct
/// from `Err`, which means the keychain itself couldn't be reached at all
/// (SPEC-106 §3's gotcha: don't confuse "no secret configured" with "the
/// credential store is broken").
pub fn get_secret(key: &str) -> Result<Option<String>, String> {
    let entry = Entry::new(SERVICE, key).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(KeyringError::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

/// Writes a secret to the OS keychain.
pub fn set_secret(key: &str, value: &str) -> Result<(), String> {
    let entry = Entry::new(SERVICE, key).map_err(|e| e.to_string())?;
    entry.set_password(value).map_err(|e| e.to_string())
}

/// Deletes a secret from the OS keychain.
pub fn delete_secret(key: &str) -> Result<(), String> {
    let entry = Entry::new(SERVICE, key).map_err(|e| e.to_string())?;
    match entry.delete_credential() {
        Ok(()) | Err(KeyringError::NoEntry) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

/// Rejects any key that is neither in `KNOWN_SECRET_KEYS` nor a currently
/// saved provider record's own `api_key_ref` (`SPEC-321` §2.2) -- so a
/// typo'd or unrelated keychain entry can never be written under this
/// app's service name via `save_secret`/`clear_secret`, while a real,
/// user-authored `SPEC-208` provider record's own key name is accepted.
/// `AppHandle`-free so the validation logic itself is directly
/// unit-testable, the same split `config.rs` already uses for
/// `ensure_output_dir`/`resolve_output_dir`.
fn validate_known_key_against(key: &str, custom_refs: &[String]) -> Result<(), String> {
    if crate::daemon::KNOWN_SECRET_KEYS.contains(&key) || custom_refs.iter().any(|r| r == key) {
        Ok(())
    } else {
        Err(format!("Unknown secret key: {key}"))
    }
}

/// The `AppHandle`-dependent half of `validate_known_key_against` --
/// reads the real, currently-saved `config.json` to know which custom
/// `api_key_ref`s exist right now. A record must be saved before its own
/// key can be (`SPEC-321` §2.2) -- there is no other source of truth for
/// "is this a real custom ref" than the config that names it.
fn validate_known_key(app: &tauri::AppHandle, key: &str) -> Result<(), String> {
    let config = crate::config::load_config(app);
    let custom_refs: Vec<String> = config
        .providers
        .unwrap_or_default()
        .into_iter()
        .filter_map(|p| p.api_key_ref)
        .collect();
    validate_known_key_against(key, &custom_refs)
}

/// Saves a provider API key and immediately pushes the complete current
/// secret set to the already-running daemon (SPEC-303) -- a human-facing
/// counterpart to `set_secret`, reachable from the frontend.
#[tauri::command]
pub fn save_secret(app: tauri::AppHandle, key: String, value: String) -> Result<(), String> {
    validate_known_key(&app, &key)?;
    set_secret(&key, &value)?;
    crate::daemon::sync_secrets_to_daemon(&app)
}

/// Clears a provider API key and re-syncs the daemon so it stops seeing a
/// now-deleted key as configured, without a restart.
#[tauri::command]
pub fn clear_secret(app: tauri::AppHandle, key: String) -> Result<(), String> {
    validate_known_key(&app, &key)?;
    delete_secret(&key)?;
    crate::daemon::sync_secrets_to_daemon(&app)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_known_key_accepts_every_real_provider_key() {
        for key in crate::daemon::KNOWN_SECRET_KEYS {
            assert!(validate_known_key_against(key, &[]).is_ok(), "{key} should be a known key");
        }
    }

    #[test]
    fn validate_known_key_rejects_anything_not_in_the_allowlist() {
        assert!(validate_known_key_against("not_a_real_provider_api_key", &[]).is_err());
        assert!(validate_known_key_against("", &[]).is_err());
    }

    /// SPEC-321 §2.2: a custom provider record's own `api_key_ref` is
    /// accepted once it's a real, currently-saved ref -- the whole reason
    /// this function stopped operating over a fixed allowlist alone.
    #[test]
    fn validate_known_key_accepts_a_real_custom_ref() {
        let custom_refs = vec!["my_local_server_key".to_string()];
        assert!(validate_known_key_against("my_local_server_key", &custom_refs).is_ok());
    }

    #[test]
    fn validate_known_key_rejects_a_ref_no_saved_record_actually_names() {
        let custom_refs = vec!["my_local_server_key".to_string()];
        assert!(validate_known_key_against("a_different_key_nobody_saved", &custom_refs).is_err());
    }

    /// SPEC-405 §2.1/§3.4: the durable guard against the central hazard
    /// that spec names -- a global find-and-replace during the Copperplane
    /// rename silently orphaning every already-saved key under the old
    /// keychain service name. `SERVICE` stays exactly this string,
    /// deliberately, forever -- this test exists to fail loudly if a
    /// future edit (well-intentioned or not) ever touches it.
    #[test]
    fn service_is_the_frozen_identity_string_spec_405_requires() {
        assert_eq!(SERVICE, "hardware-agent-studio");
    }

    #[test]
    fn real_round_trip_through_the_os_keychain() {
        // Verified for real against this machine's actual OS keychain
        // (Keychain Services on macOS), not mocked, per CLAUDE.md's
        // "verify for real" norm. Skips itself cleanly (prints and
        // returns -- stable Rust has no first-class test-skip) if no
        // keychain service is reachable at all, e.g. a headless CI runner
        // with no Secret Service.
        let test_key = "ctx-106.1-test-secret";

        if let Err(e) = Entry::store_status() {
            eprintln!("Skipping real_round_trip_through_the_os_keychain: no OS keychain store available ({e})");
            return;
        }

        set_secret(test_key, "test-value-123")
            .expect("set_secret should succeed against a real, reachable keychain");

        let retrieved = get_secret(test_key).expect("get_secret should succeed");
        assert_eq!(retrieved, Some("test-value-123".to_string()));

        delete_secret(test_key).expect("cleanup delete_secret should succeed");

        let after_delete = get_secret(test_key).expect("get_secret after delete should not error");
        assert_eq!(after_delete, None);
    }

    #[test]
    fn a_never_set_key_returns_none_not_an_error() {
        if let Err(e) = Entry::store_status() {
            eprintln!("Skipping a_never_set_key_returns_none_not_an_error: no OS keychain store available ({e})");
            return;
        }

        let result = get_secret("ctx-106.1-key-that-was-never-set");
        assert_eq!(result, Ok(None));
    }
}
