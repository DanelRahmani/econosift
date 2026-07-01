use std::sync::Mutex;
use std::time::Duration;

use tauri::Manager;
use tauri::path::BaseDirectory;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_dialog::DialogExt;

/// Holds the spawned backend child process so it can be killed on app exit.
struct BackendProcess(Mutex<Option<CommandChild>>);

/// Resolve the OS-standard app data directory.
fn app_data_dir() -> std::path::PathBuf {
    let base = dirs::data_dir().unwrap_or_else(|| std::path::PathBuf::from("."));
    base.join("AxiomFinance")
}

/// Poll the backend health endpoint until it responds or timeout elapses.
async fn wait_for_backend(timeout_secs: u64) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {e}"))?;

    let start = std::time::Instant::now();
    while start.elapsed().as_secs() < timeout_secs {
        match client
            .get("http://localhost:8000/api/health")
            .send()
            .await
        {
            Ok(resp) if resp.status().is_success() => return Ok(()),
            _ => tokio::time::sleep(Duration::from_millis(500)).await,
        }
    }
    Err("Backend did not start in time".to_string())
}

#[tauri::command]
fn get_app_data_dir() -> String {
    app_data_dir().to_string_lossy().to_string()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            // Ensure app data directory exists
            let data_dir = app_data_dir();
            std::fs::create_dir_all(&data_dir)
                .expect("Failed to create app data directory");

            let data_dir_str = data_dir.to_string_lossy().to_string();

            // Resolve the bundled onedir backend executable from the resource dir.
            // In `tauri dev` this resolves to src-tauri/binaries/axiom-backend/…;
            // in a bundled build it resolves inside the app's resource directory.
            // PyInstaller only adds the .exe suffix on Windows.
            let exe_name = if cfg!(windows) { "axiom-backend.exe" } else { "axiom-backend" };
            let backend_exe = app
                .path()
                .resolve(
                    format!("binaries/axiom-backend/{exe_name}"),
                    BaseDirectory::Resource,
                )
                .expect("Failed to resolve backend executable path");

            // Spawn the Python backend as a child process. Pass AXIOM_DATA_DIR
            // explicitly on the command — the shell plugin does not inherit env
            // vars set via std::env::set_var at runtime, so without this the
            // backend falls back to a CWD-relative ./data and its SQLite DB /
            // settings never land in %APPDATA%/AxiomFinance.
            let (_rx, child) = app
                .shell()
                .command(backend_exe)
                .env("AXIOM_DATA_DIR", &data_dir_str)
                .spawn()
                .expect("Failed to spawn backend process");

            // Stash the child so it can be killed on exit — dropping a
            // CommandChild does NOT terminate the underlying OS process, which
            // is why axiom-backend.exe used to keep running after the app closed.
            *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);

            // Wait for backend to be ready (non-blocking)
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match wait_for_backend(60).await {
                    Ok(()) => {
                        println!("Backend is ready");
                    }
                    Err(e) => {
                        eprintln!("Backend startup failed: {e}");
                        let _ = app_handle
                            .dialog()
                            .message(format!(
                                "Failed to start the analysis engine: {e}\n\n\
                                 Please try restarting the application."
                            ))
                            .title("Startup Error")
                            .kind(tauri_plugin_dialog::MessageDialogKind::Error)
                            .blocking_show();
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_app_data_dir])
        .build(tauri::generate_context!())
        .expect("error while building Axiom Finance")
        .run(|app_handle, event| {
            // Kill the spawned backend on normal app exit (window close / quit).
            // Force-killing axiom-finance.exe itself still orphans the backend —
            // that requires OS-level process-group/job-object handling, which is
            // a separate, larger fix (see ACTIVE_ISSUES.md DESK-02).
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    if let Some(child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
