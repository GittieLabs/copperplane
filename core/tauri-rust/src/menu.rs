//! CTX-312.3: the real native `File`/`Edit`/`View`/`Help` app menu --
//! `ROADMAP.md` §3.3's third `SPEC-312` question, never built until now
//! (confirmed by grep: zero `menu`/`Menu` hits anywhere in this crate
//! before this file). Real API surface verified directly against the
//! vendored `tauri 2.11.5` source before writing this, not assumed from
//! general Tauri knowledge -- `tauri::menu` compiles in unconditionally
//! at this version, no Cargo feature needed.
//!
//! Custom items (Save Project, Open Project…) only emit a real event to
//! the frontend, reusing the exact same idiom `daemon.rs`'s own
//! `DAEMON_RESPONSE_EVENT` already established (`app_handle.emit(...)`)
//! rather than inventing a second one. Everything else (Quit, Edit's
//! undo/redo/cut/copy/paste/select-all, About) is a real
//! `PredefinedMenuItem`, handled entirely natively by the OS -- no Rust
//! logic needed for those at all.

use tauri::{
    menu::{AboutMetadataBuilder, Menu, MenuBuilder, MenuEvent, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder},
    AppHandle, Emitter, Manager, Wry,
};
use tauri_plugin_shell::ShellExt;

/// Emitted when "Save Project" is clicked -- the frontend's own
/// already-existing `handleSaveProject()` (`CTX-312.1`) is the real
/// handler; this file only ever tells it to run.
pub const MENU_SAVE_PROJECT_EVENT: &str = "menu://save-project";
/// Emitted when "Open Project…" is clicked -- the frontend picks the
/// real folder and calls the real `project.open_from_directory` route
/// (`CTX-312.3`); this file only ever tells it to start.
pub const MENU_OPEN_PROJECT_EVENT: &str = "menu://open-project";

const GITHUB_REPO_URL: &str = "https://github.com/GittieLabs/hardware-agent-studio";

const FILE_SAVE_PROJECT_ID: &str = "file_save_project";
const FILE_OPEN_PROJECT_ID: &str = "file_open_project";
#[cfg(debug_assertions)]
const VIEW_TOGGLE_DEVTOOLS_ID: &str = "view_toggle_devtools";
const HELP_GITHUB_ID: &str = "help_github";

/// Builds the real app-global menu. Called once from `lib.rs`'s own
/// `Builder::menu(...)`.
pub fn build_menu(app: &AppHandle<Wry>) -> tauri::Result<Menu<Wry>> {
    let save_project = MenuItemBuilder::with_id(FILE_SAVE_PROJECT_ID, "Save Project")
        .accelerator("CmdOrCtrl+S")
        .build(app)?;
    let open_project = MenuItemBuilder::with_id(FILE_OPEN_PROJECT_ID, "Open Project…")
        .accelerator("CmdOrCtrl+O")
        .build(app)?;
    let quit = PredefinedMenuItem::quit(app, None)?;
    let file_menu = SubmenuBuilder::new(app, "File")
        .item(&save_project)
        .item(&open_project)
        .separator()
        .item(&quit)
        .build()?;

    // Entirely native -- also what makes this app's own text inputs get
    // real OS-level Cmd/Ctrl+C/V/X/Z, which they don't reliably get with
    // no menu configured at all.
    let edit_menu = SubmenuBuilder::new(app, "Edit")
        .undo()
        .redo()
        .separator()
        .cut()
        .copy()
        .paste()
        .select_all()
        .build()?;

    let about = PredefinedMenuItem::about(
        app,
        None,
        Some(
            AboutMetadataBuilder::new()
                .name(Some("Hardware Agent Studio"))
                .version(Some(env!("CARGO_PKG_VERSION")))
                .build(),
        ),
    )?;
    let github = MenuItemBuilder::with_id(HELP_GITHUB_ID, "GitHub Repository").build(app)?;
    let help_menu = SubmenuBuilder::new(app, "Help").item(&about).item(&github).build()?;

    let mut builder = MenuBuilder::new(app).item(&file_menu).item(&edit_menu);

    // `WebviewWindow::open_devtools`/`close_devtools` are themselves only
    // compiled under this same real cfg (`#[cfg(any(debug_assertions,
    // feature = "devtools"))]`, confirmed directly against the vendored
    // source) -- a release build without the `devtools` Cargo feature
    // would fail to compile if this item's handler called them
    // unconditionally, so the whole item is dev-build-only too.
    #[cfg(debug_assertions)]
    {
        let toggle_devtools =
            MenuItemBuilder::with_id(VIEW_TOGGLE_DEVTOOLS_ID, "Toggle Developer Tools").build(app)?;
        let view_menu = SubmenuBuilder::new(app, "View").item(&toggle_devtools).build()?;
        builder = builder.item(&view_menu);
    }

    builder.item(&help_menu).build()
}

/// Handles a real menu click. Registered once from `lib.rs`'s own
/// `Builder::on_menu_event(...)`. `Quit`/Edit items need no arm here at
/// all -- `PredefinedMenuItem`s are dispatched entirely natively, never
/// reaching this function.
pub fn handle_menu_event(app: &AppHandle<Wry>, event: MenuEvent) {
    match event.id().as_ref() {
        FILE_SAVE_PROJECT_ID => {
            let _ = app.emit(MENU_SAVE_PROJECT_EVENT, ());
        }
        FILE_OPEN_PROJECT_ID => {
            let _ = app.emit(MENU_OPEN_PROJECT_EVENT, ());
        }
        #[cfg(debug_assertions)]
        VIEW_TOGGLE_DEVTOOLS_ID => {
            if let Some(window) = app.get_webview_window("main") {
                if window.is_devtools_open() {
                    window.close_devtools();
                } else {
                    window.open_devtools();
                }
            }
        }
        HELP_GITHUB_ID => {
            let _ = app.shell().open(GITHUB_REPO_URL, None);
        }
        _ => {}
    }
}
