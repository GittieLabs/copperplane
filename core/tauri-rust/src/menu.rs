//! CTX-312.3 built the real native `File`/`Edit`/`View`/`Help` app menu
//! -- `ROADMAP.md` §3.3's third `SPEC-312` question, never built until
//! then. `CTX-316.1` (`SPEC-316`) grows it into the app's real command
//! surface: a leftmost app-name menu (About/Settings/Services/Hide/
//! Quit, the standard macOS home for these -- previously Quit lived in
//! `File` and About in `Help`, functional but non-standard), a grouped
//! `Design` menu holding `Schematic`/`PCB`/`Enclosure` submenus of each
//! area's already-real actions, and a `Library` menu. Real API surface
//! verified directly against the vendored `tauri 2.11.5` source before
//! writing this, not assumed from general Tauri knowledge --
//! `tauri::menu` compiles in unconditionally at this version, no Cargo
//! feature needed; `PredefinedMenuItem::{hide,hide_others,show_all,
//! services}` and `SubmenuBuilder::with_id` are all real, confirmed
//! present (`menu/predefined.rs`, `menu/builders/submenu.rs`).
//!
//! Every custom item only emits a real event to the frontend, reusing
//! the exact same idiom `daemon.rs`'s own `DAEMON_RESPONSE_EVENT`
//! already established (`app_handle.emit(...)`) -- one dedicated event
//! per action, matching `CTX-312.3`'s own Save/Open Project precedent,
//! not a new payload-parsing pattern for the newer items. Everything
//! else (Quit, Edit's undo/redo/cut/copy/paste/select-all, About,
//! Services/Hide/Hide Others/Show All) is a real `PredefinedMenuItem`,
//! handled entirely natively by the OS -- no Rust logic needed for
//! those at all.
//!
//! `menu_design`/`menu_library`'s explicit ids (`SubmenuBuilder::with_id`)
//! aren't read anywhere in this file yet -- they exist so `CTX-316.2` can
//! look these submenus up via `Menu::get` to enable/disable them and to
//! append real per-library items, without this file needing to change
//! again just to add an id it forgot.

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
/// Emitted when "Settings…" (app-name menu, `CmdOrCtrl+,`) is clicked.
pub const MENU_OPEN_SETTINGS_EVENT: &str = "menu://open-settings";
/// Emitted when "Default Library" (Library menu) is clicked.
pub const MENU_OPEN_DEFAULT_LIBRARY_EVENT: &str = "menu://open-library-default";
/// Emitted when "Manage Libraries…" (Library menu) is clicked.
pub const MENU_MANAGE_LIBRARIES_EVENT: &str = "menu://manage-libraries";
/// Emitted when Design > Schematic > "Open in KiCad" is clicked.
pub const MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT: &str = "menu://design/schematic/open-kicad";
/// Emitted when Design > Schematic > "Pick Schematic Manually…" is clicked.
pub const MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT: &str = "menu://design/schematic/pick-manually";
/// Emitted when Design > PCB > "Open in KiCad" is clicked.
pub const MENU_DESIGN_PCB_OPEN_KICAD_EVENT: &str = "menu://design/pcb/open-kicad";
/// Emitted when Design > Enclosure > "Open in KiCad" is clicked.
pub const MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT: &str = "menu://design/enclosure/open-kicad";
/// Emitted when Design > Enclosure > "Pick PCB File…" is clicked.
pub const MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT: &str = "menu://design/enclosure/pick-pcb";
/// Emitted when Design > Enclosure > "Generate" is clicked.
pub const MENU_DESIGN_ENCLOSURE_GENERATE_EVENT: &str = "menu://design/enclosure/generate";

const GITHUB_REPO_URL: &str = "https://github.com/GittieLabs/hardware-agent-studio";

const FILE_SAVE_PROJECT_ID: &str = "file_save_project";
const FILE_OPEN_PROJECT_ID: &str = "file_open_project";
#[cfg(debug_assertions)]
const VIEW_TOGGLE_DEVTOOLS_ID: &str = "view_toggle_devtools";
const HELP_GITHUB_ID: &str = "help_github";
const APP_SETTINGS_ID: &str = "app_settings";
const LIBRARY_OPEN_DEFAULT_ID: &str = "library_open_default";
const LIBRARY_MANAGE_ID: &str = "library_manage";
const DESIGN_SCHEMATIC_OPEN_KICAD_ID: &str = "design_schematic_open_kicad";
const DESIGN_SCHEMATIC_PICK_MANUALLY_ID: &str = "design_schematic_pick_manually";
const DESIGN_PCB_OPEN_KICAD_ID: &str = "design_pcb_open_kicad";
const DESIGN_ENCLOSURE_OPEN_KICAD_ID: &str = "design_enclosure_open_kicad";
const DESIGN_ENCLOSURE_PICK_PCB_ID: &str = "design_enclosure_pick_pcb";
const DESIGN_ENCLOSURE_GENERATE_ID: &str = "design_enclosure_generate";

/// Builds the real app-global menu. Called once from `lib.rs`'s own
/// `Builder::menu(...)`.
pub fn build_menu(app: &AppHandle<Wry>) -> tauri::Result<Menu<Wry>> {
    // The leftmost, app-name menu -- macOS replaces whatever title string
    // is passed here with the running app's own real bundle name, so the
    // literal text below is never actually shown. Standard macOS home for
    // About/Preferences/Services/Hide/Quit; Quit and About previously
    // lived in File/Help (CTX-312.3) and move here.
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
    let settings = MenuItemBuilder::with_id(APP_SETTINGS_ID, "Settings…")
        .accelerator("CmdOrCtrl+,")
        .build(app)?;
    let services = PredefinedMenuItem::services(app, None)?;
    let hide = PredefinedMenuItem::hide(app, None)?;
    let hide_others = PredefinedMenuItem::hide_others(app, None)?;
    let show_all = PredefinedMenuItem::show_all(app, None)?;
    let quit = PredefinedMenuItem::quit(app, None)?;
    let app_menu = SubmenuBuilder::new(app, "Hardware Agent Studio")
        .item(&about)
        .separator()
        .item(&settings)
        .separator()
        .item(&services)
        .separator()
        .item(&hide)
        .item(&hide_others)
        .item(&show_all)
        .separator()
        .item(&quit)
        .build()?;

    let save_project = MenuItemBuilder::with_id(FILE_SAVE_PROJECT_ID, "Save Project")
        .accelerator("CmdOrCtrl+S")
        .build(app)?;
    let open_project = MenuItemBuilder::with_id(FILE_OPEN_PROJECT_ID, "Open Project…")
        .accelerator("CmdOrCtrl+O")
        .build(app)?;
    let file_menu = SubmenuBuilder::new(app, "File")
        .item(&save_project)
        .item(&open_project)
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

    // SPEC-316: only the parameterless, acts-on-current-state handlers
    // each area component already has (`handleOpenKicad`,
    // `handlePickManually`, `handlePickPcbFile`, `handleGenerate`) are
    // real menu actions -- `handleCheck`/`handleCheckBoard`/
    // `handleSelectBoard` all require a specific candidate argument, so
    // there's no single "the" target for a menu click to act on yet.
    let schematic_open_kicad =
        MenuItemBuilder::with_id(DESIGN_SCHEMATIC_OPEN_KICAD_ID, "Open in KiCad").build(app)?;
    let schematic_pick_manually =
        MenuItemBuilder::with_id(DESIGN_SCHEMATIC_PICK_MANUALLY_ID, "Pick Schematic Manually…").build(app)?;
    let schematic_menu = SubmenuBuilder::new(app, "Schematic")
        .item(&schematic_open_kicad)
        .item(&schematic_pick_manually)
        .build()?;

    // BoardAdvisor has no manual-pick equivalent today -- a real, current
    // limitation of that component, not an oversight here.
    let pcb_open_kicad = MenuItemBuilder::with_id(DESIGN_PCB_OPEN_KICAD_ID, "Open in KiCad").build(app)?;
    let pcb_menu = SubmenuBuilder::new(app, "PCB").item(&pcb_open_kicad).build()?;

    let enclosure_open_kicad =
        MenuItemBuilder::with_id(DESIGN_ENCLOSURE_OPEN_KICAD_ID, "Open in KiCad").build(app)?;
    let enclosure_pick_pcb =
        MenuItemBuilder::with_id(DESIGN_ENCLOSURE_PICK_PCB_ID, "Pick PCB File…").build(app)?;
    let enclosure_generate = MenuItemBuilder::with_id(DESIGN_ENCLOSURE_GENERATE_ID, "Generate").build(app)?;
    let enclosure_menu = SubmenuBuilder::new(app, "Enclosure")
        .item(&enclosure_open_kicad)
        .item(&enclosure_pick_pcb)
        .item(&enclosure_generate)
        .build()?;

    // Explicit id (not read in this file yet) so CTX-316.2 can look this
    // submenu up via `Menu::get("menu_design")` to enable/disable it based
    // on whether a project is open.
    let design_menu = SubmenuBuilder::with_id(app, "menu_design", "Design")
        .item(&schematic_menu)
        .item(&pcb_menu)
        .item(&enclosure_menu)
        .build()?;

    // SPEC-315: Default is always real and present; real custom libraries
    // need live daemon data the menu doesn't have at build time
    // (CTX-316.2's own scope, named in SPEC-316's Known Constraints) --
    // "Manage Libraries…" is this phase's real way to reach them.
    let library_open_default =
        MenuItemBuilder::with_id(LIBRARY_OPEN_DEFAULT_ID, "Default Library").build(app)?;
    let library_manage = MenuItemBuilder::with_id(LIBRARY_MANAGE_ID, "Manage Libraries…").build(app)?;
    let library_menu = SubmenuBuilder::with_id(app, "menu_library", "Library")
        .item(&library_open_default)
        .separator()
        .item(&library_manage)
        .build()?;

    let github = MenuItemBuilder::with_id(HELP_GITHUB_ID, "GitHub Repository").build(app)?;
    let help_menu = SubmenuBuilder::new(app, "Help").item(&github).build()?;

    let mut builder = MenuBuilder::new(app)
        .item(&app_menu)
        .item(&file_menu)
        .item(&edit_menu)
        .item(&design_menu)
        .item(&library_menu);

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
        APP_SETTINGS_ID => {
            let _ = app.emit(MENU_OPEN_SETTINGS_EVENT, ());
        }
        LIBRARY_OPEN_DEFAULT_ID => {
            let _ = app.emit(MENU_OPEN_DEFAULT_LIBRARY_EVENT, ());
        }
        LIBRARY_MANAGE_ID => {
            let _ = app.emit(MENU_MANAGE_LIBRARIES_EVENT, ());
        }
        DESIGN_SCHEMATIC_OPEN_KICAD_ID => {
            let _ = app.emit(MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT, ());
        }
        DESIGN_SCHEMATIC_PICK_MANUALLY_ID => {
            let _ = app.emit(MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT, ());
        }
        DESIGN_PCB_OPEN_KICAD_ID => {
            let _ = app.emit(MENU_DESIGN_PCB_OPEN_KICAD_EVENT, ());
        }
        DESIGN_ENCLOSURE_OPEN_KICAD_ID => {
            let _ = app.emit(MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT, ());
        }
        DESIGN_ENCLOSURE_PICK_PCB_ID => {
            let _ = app.emit(MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT, ());
        }
        DESIGN_ENCLOSURE_GENERATE_ID => {
            let _ = app.emit(MENU_DESIGN_ENCLOSURE_GENERATE_EVENT, ());
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
