//! The process "crash shield": OS-level lifecycle binding that guarantees
//! the Python daemon child process cannot outlive this app, even if the
//! app crashes rather than exiting gracefully. See SPEC-101 §2.
use std::process::Child;
#[cfg(any(target_os = "linux", target_os = "windows"))]
use std::process::Command;

/// Kills `child` immediately. Used from the graceful-shutdown path
/// (e.g. macOS `RunEvent::Exit`) where the OS gives us a chance to clean up.
pub fn kill_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

/// Configures `command` so that, once spawned, the OS itself kills the
/// child the moment this process dies for any reason — including a hard
/// crash where our own shutdown code never runs.
#[cfg(target_os = "linux")]
pub fn bind_child_lifetime(command: &mut Command) {
    use std::os::unix::process::CommandExt;

    unsafe {
        command.pre_exec(|| {
            linux::set_kill_on_parent_death()?;
            Ok(())
        });
    }
}

#[cfg(target_os = "linux")]
pub(crate) mod linux {
    use std::io;

    /// `PR_SET_PDEATHSIG` asks the kernel to send `sig` to the *calling*
    /// process when its direct parent dies for any reason (exit, crash,
    /// SIGKILL). Must be called in the child after `fork`, before `exec`.
    pub fn set_kill_on_parent_death() -> io::Result<()> {
        // SAFETY: prctl(PR_SET_PDEATHSIG, ...) has no preconditions beyond
        // being called from the process that should receive the signal.
        let ret = unsafe { libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL as libc::c_ulong) };
        if ret != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

#[cfg(target_os = "windows")]
pub fn bind_child_lifetime(command: &mut Command) -> std::io::Result<windows::JobHandle> {
    windows::assign_new_job_object(command)
}

#[cfg(target_os = "windows")]
pub(crate) mod windows {
    use std::io;
    use std::process::Command;

    use windows::Win32::Foundation::{CloseHandle, HANDLE};
    use windows::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    /// Owns the Job Object handle. Dropping it (e.g. on our own process
    /// exit) tears the job down, which — because of
    /// `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` — kills every process still
    /// assigned to it, including the Python daemon.
    pub struct JobHandle(HANDLE);

    impl Drop for JobHandle {
        fn drop(&mut self) {
            unsafe {
                let _ = CloseHandle(self.0);
            }
        }
    }

    /// Creates a fresh Job Object configured to kill all member processes
    /// when the job closes, and assigns `command`'s future child to it.
    /// The returned `JobHandle` must be kept alive for as long as the
    /// child should be supervised.
    pub fn assign_new_job_object(command: &mut Command) -> io::Result<JobHandle> {
        unsafe {
            let job = CreateJobObjectW(None, None).map_err(io::Error::from)?;

            let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                std::mem::size_of_val(&info) as u32,
            )
            .map_err(io::Error::from)?;

            // The child is assigned to the job right after spawning, from
            // the caller — Windows has no `pre_exec` equivalent, so we
            // hand back the job handle for `daemon::spawn_daemon` to use
            // via `AssignProcessToJobObject` once it has a PID.
            let _ = command;
            Ok(JobHandle(job))
        }
    }

    pub fn assign_process(job: &JobHandle, process_handle: HANDLE) -> io::Result<()> {
        unsafe { AssignProcessToJobObject(job.0, process_handle).map_err(io::Error::from) }
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use std::time::Duration;

    fn process_is_alive(pid: libc::pid_t) -> bool {
        unsafe { libc::kill(pid, 0) == 0 }
    }

    /// Proves the core "no dangling processes" guarantee end to end:
    /// spawn an intermediate process that forks a grandchild configured
    /// with `set_kill_on_parent_death`, then let the intermediate exit.
    /// The grandchild must be killed by the kernel, not by any of our own
    /// cleanup code — nothing here calls `kill` on it directly.
    #[test]
    fn grandchild_dies_when_its_direct_parent_exits() {
        let mut pipe_fds = [0i32; 2];
        assert_eq!(unsafe { libc::pipe(pipe_fds.as_mut_ptr()) }, 0);
        let [read_fd, write_fd] = pipe_fds;

        let intermediate_pid = unsafe { libc::fork() };
        assert!(intermediate_pid >= 0, "fork failed");

        if intermediate_pid == 0 {
            unsafe { libc::close(read_fd) };

            let grandchild_pid = unsafe { libc::fork() };
            if grandchild_pid == 0 {
                let _ = super::linux::set_kill_on_parent_death();
                unsafe { libc::pause() };
                unsafe { libc::_exit(0) };
            }

            let msg = format!("{grandchild_pid}\n");
            unsafe {
                libc::write(write_fd, msg.as_ptr() as *const _, msg.len());
                libc::close(write_fd);
            }
            unsafe { libc::_exit(0) };
        }

        unsafe { libc::close(write_fd) };
        let mut buf = [0u8; 32];
        let n = unsafe { libc::read(read_fd, buf.as_mut_ptr() as *mut _, buf.len()) };
        unsafe { libc::close(read_fd) };
        let grandchild_pid: libc::pid_t = std::str::from_utf8(&buf[..n.max(0) as usize])
            .expect("pid pipe should contain utf8")
            .trim()
            .parse()
            .expect("pid pipe should contain a pid");

        let mut status: i32 = 0;
        unsafe { libc::waitpid(intermediate_pid, &mut status, 0) };

        let mut died = false;
        for _ in 0..50 {
            if !process_is_alive(grandchild_pid) {
                died = true;
                break;
            }
            std::thread::sleep(Duration::from_millis(20));
        }

        assert!(
            died,
            "grandchild (pid {grandchild_pid}) should be killed by the kernel \
             when its direct parent exits, without any explicit kill() call"
        );
    }
}
