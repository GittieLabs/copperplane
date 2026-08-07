//! The IPC transport layer described in SPEC-101 §2: a raw string pipe
//! between the frontend and the Python JSON-RPC daemon. This layer never
//! parses the JSON-RPC payload itself — that is the daemon's job.
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};

use tauri::{AppHandle, Emitter, Manager};

/// Event name the frontend listens on for daemon `stdout` lines.
pub const DAEMON_RESPONSE_EVENT: &str = "daemon://response";

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

    let stdin = child
        .stdin
        .take()
        .expect("daemon child was spawned with Stdio::piped() stdin");
    let stdout = child
        .stdout
        .take()
        .expect("daemon child was spawned with Stdio::piped() stdout");

    let app_handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            match line {
                Ok(line) if !line.trim().is_empty() => {
                    let _ = app_handle.emit(DAEMON_RESPONSE_EVENT, line);
                }
                Ok(_) => {}
                Err(_) => break,
            }
        }
    });

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

#[cfg(test)]
mod tests {
    use super::write_request;

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
