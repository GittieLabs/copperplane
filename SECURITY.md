# Security Policy

## Reporting a vulnerability

**Please do not report security issues in a public issue or discussion.**

Use GitHub's private vulnerability reporting:
[**Report a vulnerability**](https://github.com/GittieLabs/hardware-agent-studio/security/advisories/new).
It is private between you and the maintainer, and it lets us prepare a fix
before anything is disclosed.

If that form is unavailable to you, email **keith@gittie.co** with `SECURITY`
in the subject line.

Please include what you were doing, what you observed, the platform and app
version, and a way to reproduce it if you have one. If you are unsure whether
something counts as a security issue, report it privately anyway — an
unnecessary private report costs far less than a premature public one.

### What to expect

This project is maintained by one person, so please read these as honest
intentions rather than a commercial SLA:

| Stage | Target |
| :--- | :--- |
| Acknowledgement | within 3 business days |
| Initial assessment | within 10 business days |
| Fix or documented mitigation | depends on severity; you will get a status update either way |

You will be credited in the advisory and the release notes unless you ask not
to be. There is no bug bounty.

## Supported versions

Only the most recent release receives security fixes. This project is in
early, active development and there are no long-term support branches.

## What has a security surface

Worth stating plainly, because the attack surface of a desktop CAD assistant
is not obvious:

*   **Credentials.** LLM provider API keys are stored in the operating
    system's keychain, never in a configuration file on disk. A bug that
    caused a key to be written to disk, logged, or transmitted anywhere other
    than the provider you configured is a security issue — report it.
*   **Subprocess execution.** The app locates and runs external binaries,
    including `kicad-cli` and `freecadcmd`, and resolves their paths from
    configuration. Anything that lets an untrusted input influence which
    binary runs, or the arguments it runs with, is a security issue.
*   **Untrusted file parsing.** The app parses datasheet PDFs and KiCad
    S-expression files (`.kicad_mod`, `.kicad_sym`, `.kicad_pcb`), which are
    untrusted input. Crashes are bugs; anything that escapes the parser is a
    security issue.
*   **Network fetches.** The app downloads datasheet PDFs from URLs and
    queries GitHub for community libraries. Path traversal via a filename,
    SSRF, or TLS verification being skipped are all security issues.
*   **Local storage.** Projects, parts and cached datasheets are written under
    a user-chosen storage root. Anything that writes outside it is a security
    issue.

## What is not a vulnerability

*   **The unsigned Windows and Linux builds.** These are known and documented.
    Windows SmartScreen warns because no code-signing certificate exists yet,
    not because of a defect. macOS builds are signed and notarized.
*   **An LLM returning wrong or misleading engineering advice.** This is a
    correctness bug and a serious one — please file it as a normal issue — but
    it is not a security vulnerability. The application is an advisor: verify
    its output against the cited source before committing it to a board.
*   **Vulnerabilities in KiCad or FreeCAD themselves.** Report those to the
    respective projects. If our invocation of them makes an issue reachable
    that otherwise would not be, that part is ours — tell us.
