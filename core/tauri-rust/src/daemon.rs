//! The IPC transport layer described in SPEC-101 §2: a raw string pipe
//! between the frontend and the Python JSON-RPC daemon. This layer never
//! parses the JSON-RPC payload itself — that is the daemon's job.
use std::collections::BTreeMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager};

/// How often the macOS heartbeat monitor checks in (SPEC-107 §2/§3).
#[cfg(target_os = "macos")]
const HEARTBEAT_CHECK_INTERVAL_S: u64 = 5;

/// How long without a heartbeat/ready line before the daemon is treated as
/// hard-crashed. 3x the daemon's own 5s heartbeat interval (`daemon.py`'s
/// `_HEARTBEAT_INTERVAL_S`) rather than 2x, to leave real margin for
/// scheduling jitter under load before concluding a live daemon crashed.
#[cfg(target_os = "macos")]
const HEARTBEAT_TIMEOUT_S: u64 = 15;

/// Event name the frontend listens on for daemon `stdout` lines.
pub const DAEMON_RESPONSE_EVENT: &str = "daemon://response";

/// Secret keys this app currently stores in the OS keychain and hands to
/// the daemon via the `daemon.configure` handshake (SPEC-106 §2). The
/// four LLM provider keys are SPEC-201's; SPEC-203 (a supplier API key)
/// is the next spec with a real key name to add here. Kept as an
/// explicit allowlist rather than "fetch everything stored under our
/// service name" so a stray keychain entry from some unrelated feature
/// never leaks into the daemon's configure handshake. Naming convention:
/// `<provider>_api_key`, matching `llm_providers.py`'s own lookup
/// (`CONFIG["secrets"][f"{provider}_api_key"]`). Ollama needs no key --
/// it isn't listed here.
const KNOWN_SECRET_KEYS: &[&str] = &[
    "anthropic_api_key",
    "google_api_key",
    "openai_api_key",
    "perplexity_api_key",
];

/// Builds the `daemon.configure` JSON-RPC request line (SPEC-106 §2) that
/// `spawn_daemon` writes as the very first thing on the daemon's `stdin`.
/// Secrets travel this way -- over the same private pipe `SPEC-101`
/// already built -- rather than as an env var or, worse, a command-line
/// argument visible to any user via `ps`. A pure function of the secrets
/// map, so it's directly unit-testable without a real child process.
pub fn build_configure_request(secrets: &BTreeMap<String, String>) -> String {
    serde_json::json!({
        "jsonrpc": "2.0",
        "method": "daemon.configure",
        "params": { "secrets": secrets },
        "id": 0,
    })
    .to_string()
}

/// True if `line` is a `daemon.ready` or `daemon.heartbeat` notification --
/// the two signals the macOS crash-detection monitor (SPEC-107 §2) treats
/// as proof the daemon is still alive. A narrow, deliberate exception to
/// this module's own "never parse the payload" principle (this file's own
/// header comment) -- detecting these two method names is structurally
/// required for heartbeat-based crash detection to exist at all. Every
/// other aspect of forwarding `stdout` to the frontend remains unparsed.
#[cfg(target_os = "macos")]
fn is_heartbeat_signal(line: &str) -> bool {
    let Ok(parsed) = serde_json::from_str::<serde_json::Value>(line) else {
        return false;
    };
    matches!(
        parsed.get("method").and_then(|m| m.as_str()),
        Some("daemon.ready") | Some("daemon.heartbeat")
    )
}

/// Watches `last_heartbeat`; if too long passes without a `daemon.ready`/
/// `daemon.heartbeat` line, treats the daemon as hard-crashed and runs the
/// same cleanup `RunEvent::Exit` would have (SPEC-107 §2) -- the missing
/// half of `CTX-101.1`'s crash shield on macOS, where `RunEvent::Exit`
/// only ever fires on a *graceful* quit. Windows/Linux already have
/// working OS-level crash shields (Job Objects / `prctl`); this path is
/// macOS-only by design, not an oversight (SPEC-107 §3).
#[cfg(target_os = "macos")]
fn spawn_heartbeat_monitor(app: &AppHandle, last_heartbeat: Arc<Mutex<Instant>>) {
    let app_handle = app.clone();
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(HEARTBEAT_CHECK_INTERVAL_S));

        let elapsed = last_heartbeat
            .lock()
            .map(|guard| guard.elapsed())
            .unwrap_or(Duration::ZERO);

        if elapsed > Duration::from_secs(HEARTBEAT_TIMEOUT_S) {
            log::warn!(
                "No daemon heartbeat for {elapsed:?} -- treating as a hard crash (SPEC-107) and cleaning up"
            );
            if let Some(handle) = app_handle.try_state::<DaemonHandle>() {
                handle.shutdown();
            }
            break;
        }
    });
}

/// Owns the daemon child process and the `Arc<Mutex<ChildStdin>>` transport
/// handle described in SPEC-101, so `dispatch_to_daemon` can write to it
/// from any thread without taking ownership of the child itself.
pub struct DaemonHandle {
    child: Mutex<Child>,
    stdin: Arc<Mutex<ChildStdin>>,
    // Kept alive for its `Drop` side effect: closing the last handle to a
    // job created with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` kills every
    // process still assigned to it. The OS closes this handle for us even
    // on a hard crash, which is what makes the Windows path crash-proof.
    #[cfg(target_os = "windows")]
    _job_handle: crate::supervisor::windows::JobHandle,
}

/// Spawns `services/python-daemon/daemon.py` relative to the app's own
/// resource directory, wires the supervisor's crash shield onto it, and
/// starts a background thread that forwards its `stdout` to the frontend.
pub fn spawn_daemon(app: &AppHandle, script_path: PathBuf) -> std::io::Result<DaemonHandle> {
    let mut command = Command::new("python3");
    command
        .arg(&script_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());

    // SPEC-106 §2: Rust owns config and secrets, injecting them at spawn.
    // Non-secret settings ride as an env var -- visible only to this OS
    // user, a materially smaller exposure than `ps`'s world-readable argv.
    let mut daemon_config = crate::config::load_config(app);
    // SPEC-301 §2: unlike every other DaemonConfig field, output_dir is
    // never read from config.json -- always Rust-computed so it agrees
    // exactly with tauri.conf.json's assetProtocol.scope.
    daemon_config.output_dir = crate::config::resolve_output_dir(app);
    for (name, value) in crate::config::build_daemon_env(&daemon_config) {
        command.env(name, value);
    }

    #[cfg(target_os = "linux")]
    crate::supervisor::bind_child_lifetime(&mut command);

    #[cfg(target_os = "windows")]
    let job_handle = crate::supervisor::windows::assign_new_job_object(&mut command)?;

    let mut child = command.spawn()?;

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::io::AsRawHandle;
        use windows::Win32::Foundation::HANDLE;

        crate::supervisor::windows::assign_process(&job_handle, HANDLE(child.as_raw_handle()))?;
    }

    let mut stdin = child
        .stdin
        .take()
        .expect("daemon child was spawned with Stdio::piped() stdin");
    let stdout = child
        .stdout
        .take()
        .expect("daemon child was spawned with Stdio::piped() stdout");

    // SPEC-106 §2: secrets go over stdin, as the very first line the
    // daemon ever reads -- before spawn_daemon returns and hands the
    // stdin handle to anything that could write a second, ordinary
    // request ahead of it.
    let secrets: BTreeMap<String, String> = KNOWN_SECRET_KEYS
        .iter()
        .filter_map(|key| {
            crate::secrets::get_secret(key)
                .ok()
                .flatten()
                .map(|value| (key.to_string(), value))
        })
        .collect();
    write_request(&mut stdin, &build_configure_request(&secrets))?;

    // SPEC-107 §2: the clock starts now, not on the first heartbeat --
    // otherwise a daemon that's slow to reach its own daemon.ready would
    // look identical to one that already crashed.
    #[cfg(target_os = "macos")]
    let last_heartbeat = Arc::new(Mutex::new(Instant::now()));
    #[cfg(target_os = "macos")]
    let stdout_last_heartbeat = last_heartbeat.clone();

    let app_handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            match line {
                Ok(line) if !line.trim().is_empty() => {
                    #[cfg(target_os = "macos")]
                    if is_heartbeat_signal(&line) {
                        if let Ok(mut last) = stdout_last_heartbeat.lock() {
                            *last = Instant::now();
                        }
                    }
                    let _ = app_handle.emit(DAEMON_RESPONSE_EVENT, line);
                }
                Ok(_) => {}
                Err(_) => break,
            }
        }
    });

    #[cfg(target_os = "macos")]
    spawn_heartbeat_monitor(app, last_heartbeat);

    Ok(DaemonHandle {
        child: Mutex::new(child),
        stdin: Arc::new(Mutex::new(stdin)),
        #[cfg(target_os = "windows")]
        _job_handle: job_handle,
    })
}

impl DaemonHandle {
    /// Terminates the daemon as part of a graceful shutdown (e.g. macOS
    /// `RunEvent::Exit`). This is a best-effort backstop on top of the
    /// OS-level crash shield, not a replacement for it.
    pub fn shutdown(&self) {
        if let Ok(mut child) = self.child.lock() {
            crate::supervisor::kill_child(&mut child);
        }
    }
}

/// Writes one JSON-RPC request line to `stdin` and flushes it, so the
/// daemon (which reads line-by-line) sees it immediately. Generic over
/// `Write` so the framing logic is unit-testable without a real child
/// process — see the tests below.
pub fn write_request<W: Write>(stdin: &mut W, request: &str) -> std::io::Result<()> {
    writeln!(stdin, "{request}")?;
    stdin.flush()
}

/// The Tauri command React dispatches JSON-RPC requests through. Rust
/// treats `request` as an opaque string — per SPEC-101's non-goals, it
/// never parses or validates the payload contents.
#[tauri::command]
pub fn dispatch_to_daemon(
    app: AppHandle,
    request: String,
) -> Result<(), String> {
    let daemon = app.state::<DaemonHandle>();
    let mut stdin = daemon
        .stdin
        .lock()
        .map_err(|_| "daemon stdin lock was poisoned".to_string())?;
    write_request(&mut *stdin, &request).map_err(|e| e.to_string())
}

#[cfg(all(test, target_os = "macos"))]
mod heartbeat_tests {
    use super::is_heartbeat_signal;

    #[test]
    fn recognizes_daemon_ready_as_a_heartbeat_signal() {
        assert!(is_heartbeat_signal(
            r#"{"jsonrpc": "2.0", "method": "daemon.ready", "params": {"kicad_available": true}}"#
        ));
    }

    #[test]
    fn recognizes_daemon_heartbeat_as_a_heartbeat_signal() {
        assert!(is_heartbeat_signal(r#"{"jsonrpc": "2.0", "method": "daemon.heartbeat", "params": {}}"#));
    }

    #[test]
    fn an_ordinary_response_is_not_a_heartbeat_signal() {
        assert!(!is_heartbeat_signal(r#"{"jsonrpc": "2.0", "result": {"job_id": "abc"}, "id": 1}"#));
    }

    #[test]
    fn a_different_notification_method_is_not_a_heartbeat_signal() {
        assert!(!is_heartbeat_signal(
            r#"{"jsonrpc": "2.0", "method": "job.progress", "params": {"job_id": "abc"}}"#
        ));
    }

    #[test]
    fn malformed_json_is_not_a_heartbeat_signal() {
        assert!(!is_heartbeat_signal("not json at all"));
    }
}

#[cfg(test)]
mod tests {
    use super::{build_configure_request, write_request};
    use std::collections::BTreeMap;

    #[test]
    fn build_configure_request_produces_a_valid_daemon_configure_line() {
        let mut secrets = BTreeMap::new();
        secrets.insert("llm_api_key".to_string(), "sk-test-123".to_string());

        let line = build_configure_request(&secrets);
        let parsed: serde_json::Value = serde_json::from_str(&line)
            .expect("build_configure_request should produce valid JSON");

        assert_eq!(parsed["jsonrpc"], "2.0");
        assert_eq!(parsed["method"], "daemon.configure");
        assert_eq!(parsed["params"]["secrets"]["llm_api_key"], "sk-test-123");
        assert!(parsed.get("id").is_some(), "a JSON-RPC request must carry an id");
    }

    #[test]
    fn build_configure_request_composes_with_write_request() {
        let secrets = BTreeMap::new();
        let mut buf: Vec<u8> = Vec::new();

        write_request(&mut buf, &build_configure_request(&secrets)).unwrap();

        let written = String::from_utf8(buf).unwrap();
        assert!(written.ends_with('\n'), "the configure line must be newline-terminated like any other request");
        let parsed: serde_json::Value = serde_json::from_str(written.trim_end()).unwrap();
        assert_eq!(parsed["method"], "daemon.configure");
    }

    #[test]
    fn writes_the_request_terminated_by_a_single_newline_and_flushes() {
        let mut buf: Vec<u8> = Vec::new();
        write_request(&mut buf, r#"{"jsonrpc":"2.0","method":"kicad.generate_component","id":1}"#)
            .expect("write_request should succeed against an in-memory buffer");

        assert_eq!(
            buf,
            b"{\"jsonrpc\":\"2.0\",\"method\":\"kicad.generate_component\",\"id\":1}\n".to_vec()
        );
    }

    #[test]
    fn writes_each_request_on_its_own_line() {
        let mut buf: Vec<u8> = Vec::new();
        write_request(&mut buf, "first").unwrap();
        write_request(&mut buf, "second").unwrap();

        assert_eq!(buf, b"first\nsecond\n".to_vec());
    }
}
