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

use serde::{Deserialize, Serialize};
use tauri::{
    menu::{AboutMetadataBuilder, Menu, MenuBuilder, MenuEvent, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder},
    AppHandle, Emitter, Manager, Wry,
};
use tauri_plugin_shell::ShellExt;

/// CTX-316.2: the frontend's own real `LibrarySummary` (`SPEC-315`),
/// trimmed to just what the native Library menu needs. Crosses the
/// Tauri command boundary from `update_library_menu`'s own `Vec`
/// argument.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LibraryMenuEntry {
    pub id: String,
    pub name: String,
}

/// Emitted when a real, dynamically-listed custom library is clicked in
/// the Library menu -- payload is that library's own real id. Unlike
/// every other menu event in this file, this one can't have a
/// compile-time const per action: a custom library's identity is
/// inherently open-ended and user-defined.
pub const MENU_OPEN_LIBRARY_EVENT: &str = "menu://open-library";

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
/// Emitted when Design > Schematic > "Run Review" is clicked (SPEC-319 §2.4).
pub const MENU_DESIGN_SCHEMATIC_RUN_REVIEW_EVENT: &str = "menu://design/schematic/run-review";
/// Emitted when Design > PCB > "Run Review" is clicked (SPEC-319 §2.4).
pub const MENU_DESIGN_PCB_RUN_REVIEW_EVENT: &str = "menu://design/pcb/run-review";
/// Emitted when Design > Enclosure > "Run Review" is clicked (SPEC-319 §2.4).
pub const MENU_DESIGN_ENCLOSURE_RUN_REVIEW_EVENT: &str = "menu://design/enclosure/run-review";

const GITHUB_REPO_URL: &str = "https://github.com/GittieLabs/copperplane";

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
const DESIGN_SCHEMATIC_RUN_REVIEW_ID: &str = "design_schematic_run_review";
const DESIGN_PCB_RUN_REVIEW_ID: &str = "design_pcb_run_review";
const DESIGN_ENCLOSURE_RUN_REVIEW_ID: &str = "design_enclosure_run_review";
const LIBRARY_OPEN_CUSTOM_PREFIX: &str = "library_open_custom_";
/// Must match `library_store.DEFAULT_LIBRARY_ID` in
/// `services/python-daemon/library_store.py` -- Default already has its
/// own always-present static item, so it's excluded here rather than
/// risking a real, visible duplicate if the registry ever returns it.
const DEFAULT_LIBRARY_ID: &str = "default";

/// CTX-316.2: excludes Default (already a static menu item) from a real
/// library list before it becomes dynamic Library-menu entries. No
/// `AppHandle` involved -- real, directly unit-testable Rust, unlike
/// menu construction itself.
fn filter_custom_libraries(libraries: Vec<LibraryMenuEntry>) -> Vec<LibraryMenuEntry> {
    libraries.into_iter().filter(|entry| entry.id != DEFAULT_LIBRARY_ID).collect()
}

/// Builds the real app-global menu with no real custom libraries yet --
/// called once from `lib.rs`'s own `Builder::menu(...)`, before the
/// daemon is ready to answer `library.list_libraries()`. See
/// `update_library_menu` for the real, later rebuild.
pub fn build_menu(app: &AppHandle<Wry>) -> tauri::Result<Menu<Wry>> {
    build_menu_inner(app, &[])
}

/// The real menu builder both `build_menu` and `update_library_menu`
/// share -- `custom_libraries` is empty at initial launch, real once
/// `CTX-316.2`'s own sync has run at least once.
fn build_menu_inner(app: &AppHandle<Wry>, custom_libraries: &[LibraryMenuEntry]) -> tauri::Result<Menu<Wry>> {
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
                .name(Some("Copperplane"))
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
    let app_menu = SubmenuBuilder::new(app, "Copperplane")
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

    let open_project = MenuItemBuilder::with_id(FILE_OPEN_PROJECT_ID, "Open Project…")
        .accelerator("CmdOrCtrl+O")
        .build(app)?;
    // "Save Project" and its Cmd+S were removed with the button: every field
    // now persists at the moment it changes, so a save command had nothing
    // left to do, and a whole-record write was actively destructive
    // (SPEC-333). A menu item that appears to save and does nothing useful is
    // worse than no menu item.
    let file_menu = SubmenuBuilder::new(app, "File")
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
    // SPEC-319 §2.4: Run Review reuses the same real, area-scoped agent
    // chat.review already dispatches to -- ReviewPanel's own in-area
    // button is the same action, this is just a second, native entry
    // point to it.
    let schematic_run_review =
        MenuItemBuilder::with_id(DESIGN_SCHEMATIC_RUN_REVIEW_ID, "Run Review").build(app)?;
    let schematic_menu = SubmenuBuilder::new(app, "Schematic")
        .item(&schematic_open_kicad)
        .item(&schematic_pick_manually)
        .separator()
        .item(&schematic_run_review)
        .build()?;

    // BoardAdvisor has no manual-pick equivalent today -- a real, current
    // limitation of that component, not an oversight here.
    let pcb_open_kicad = MenuItemBuilder::with_id(DESIGN_PCB_OPEN_KICAD_ID, "Open in KiCad").build(app)?;
    let pcb_run_review = MenuItemBuilder::with_id(DESIGN_PCB_RUN_REVIEW_ID, "Run Review").build(app)?;
    let pcb_menu = SubmenuBuilder::new(app, "PCB")
        .item(&pcb_open_kicad)
        .separator()
        .item(&pcb_run_review)
        .build()?;

    let enclosure_open_kicad =
        MenuItemBuilder::with_id(DESIGN_ENCLOSURE_OPEN_KICAD_ID, "Open in KiCad").build(app)?;
    let enclosure_pick_pcb =
        MenuItemBuilder::with_id(DESIGN_ENCLOSURE_PICK_PCB_ID, "Pick PCB File…").build(app)?;
    let enclosure_generate = MenuItemBuilder::with_id(DESIGN_ENCLOSURE_GENERATE_ID, "Generate").build(app)?;
    let enclosure_run_review =
        MenuItemBuilder::with_id(DESIGN_ENCLOSURE_RUN_REVIEW_ID, "Run Review").build(app)?;
    let enclosure_menu = SubmenuBuilder::new(app, "Enclosure")
        .item(&enclosure_open_kicad)
        .item(&enclosure_pick_pcb)
        .item(&enclosure_generate)
        .separator()
        .item(&enclosure_run_review)
        .build()?;

    // Explicit id (not read in this file yet) so CTX-316.2 can look this
    // submenu up via `Menu::get("menu_design")` to enable/disable it based
    // on whether a project is open.
    let design_menu = SubmenuBuilder::with_id(app, "menu_design", "Design")
        .item(&schematic_menu)
        .item(&pcb_menu)
        .item(&enclosure_menu)
        .build()?;

    // SPEC-315: Default is always real and present. Real custom libraries
    // (CTX-316.2) are appended after it, in real registry order, only
    // when `update_library_menu` has actually run with a non-empty list
    // -- at initial launch (`custom_libraries` empty) this renders
    // byte-identical to CTX-316.1's own static Default/Manage-only shape.
    let library_open_default =
        MenuItemBuilder::with_id(LIBRARY_OPEN_DEFAULT_ID, "Default Library").build(app)?;
    let custom_library_items = custom_libraries
        .iter()
        .map(|entry| {
            MenuItemBuilder::with_id(format!("{LIBRARY_OPEN_CUSTOM_PREFIX}{}", entry.id), &entry.name).build(app)
        })
        .collect::<tauri::Result<Vec<_>>>()?;
    let library_manage = MenuItemBuilder::with_id(LIBRARY_MANAGE_ID, "Manage Libraries…").build(app)?;
    let mut library_menu_builder =
        SubmenuBuilder::with_id(app, "menu_library", "Library").item(&library_open_default);
    for item in &custom_library_items {
        library_menu_builder = library_menu_builder.item(item);
    }
    let library_menu = library_menu_builder.separator().item(&library_manage).build()?;

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

/// CTX-316.2: rebuilds the whole menu with `libraries`' real, non-Default
/// entries as the Library menu's dynamic items, then replaces the app's
/// live menu with it (`AppHandle::set_menu`, real and confirmed present
/// via `shared_app_impl!(AppHandle<R>)`) -- called from the frontend
/// after every real `library.list_libraries()` fetch (`lib/menu.ts`'s
/// own `syncLibraryMenu`), not pushed proactively by the daemon.
#[tauri::command]
pub fn update_library_menu(app: AppHandle<Wry>, libraries: Vec<LibraryMenuEntry>) -> Result<(), String> {
    let custom = filter_custom_libraries(libraries);
    let menu = build_menu_inner(&app, &custom).map_err(|e| e.to_string())?;
    app.set_menu(menu).map_err(|e| e.to_string())?;
    Ok(())
}

/// CTX-316.2: enables/disables the whole `Design` menu based on whether
/// a project is currently open -- one real, coarse-grained sync point
/// (SPEC-316's own Known Constraints named this as the deliberately
/// simple starting behavior, not per-action preconditions).
#[tauri::command]
pub fn set_design_menu_enabled(app: AppHandle<Wry>, enabled: bool) -> Result<(), String> {
    let menu = app.menu().ok_or_else(|| "no app menu set".to_string())?;
    let design_item = menu.get("menu_design").ok_or_else(|| "menu_design not found".to_string())?;
    design_item.as_submenu_unchecked().set_enabled(enabled).map_err(|e| e.to_string())
}

/// Handles a real menu click. Registered once from `lib.rs`'s own
/// `Builder::on_menu_event(...)`. `Quit`/Edit items need no arm here at
/// all -- `PredefinedMenuItem`s are dispatched entirely natively, never
/// reaching this function.
pub fn handle_menu_event(app: &AppHandle<Wry>, event: MenuEvent) {
    match event.id().as_ref() {
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
        DESIGN_SCHEMATIC_RUN_REVIEW_ID => {
            let _ = app.emit(MENU_DESIGN_SCHEMATIC_RUN_REVIEW_EVENT, ());
        }
        DESIGN_PCB_RUN_REVIEW_ID => {
            let _ = app.emit(MENU_DESIGN_PCB_RUN_REVIEW_EVENT, ());
        }
        DESIGN_ENCLOSURE_RUN_REVIEW_ID => {
            let _ = app.emit(MENU_DESIGN_ENCLOSURE_RUN_REVIEW_EVENT, ());
        }
        id if id.starts_with(LIBRARY_OPEN_CUSTOM_PREFIX) => {
            let library_id = &id[LIBRARY_OPEN_CUSTOM_PREFIX.len()..];
            let _ = app.emit(MENU_OPEN_LIBRARY_EVENT, library_id);
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

#[cfg(test)]
mod tests {
    use super::{filter_custom_libraries, LibraryMenuEntry};

    fn entry(id: &str, name: &str) -> LibraryMenuEntry {
        LibraryMenuEntry { id: id.to_string(), name: name.to_string() }
    }

    #[test]
    fn filter_custom_libraries_excludes_default_and_preserves_real_order() {
        let libraries = vec![entry("default", "Default"), entry("esp32-boards", "ESP32 Boards"), entry("sensors", "Sensors")];

        let custom = filter_custom_libraries(libraries);

        assert_eq!(custom.len(), 2);
        assert_eq!(custom[0].id, "esp32-boards");
        assert_eq!(custom[1].id, "sensors");
    }

    #[test]
    fn filter_custom_libraries_on_an_empty_input_returns_an_empty_output() {
        assert!(filter_custom_libraries(vec![]).is_empty());
    }

    #[test]
    fn filter_custom_libraries_with_only_default_returns_an_empty_output() {
        assert!(filter_custom_libraries(vec![entry("default", "Default")]).is_empty());
    }
}
