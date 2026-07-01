use std::time::Duration;

use tauri::Manager;
use tauri::path::BaseDirectory;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_dialog::DialogExt;

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

#[tauri::command]
fn get_settings_path() -> String {
    app_data_dir()
        .join("settings.json")
        .to_string_lossy()
        .to_string()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            // Ensure app data directory exists
            let data_dir = app_data_dir();
            std::fs::create_dir_all(&data_dir)
                .expect("Failed to create app data directory");

            let data_dir_str = data_dir.to_string_lossy().to_string();

            // Resolve the bundled onedir backend executable from the resource dir.
            // In `tauri dev` this resolves to src-tauri/binaries/axiom-backend/…;
            // in a bundled build it resolves inside the app's resource directory.
            let backend_exe = app
                .path()
                .resolve(
                    "binaries/axiom-backend/axiom-backend.exe",
                    BaseDirectory::Resource,
                )
                .expect("Failed to resolve backend executable path");

            // Spawn the Python backend as a child process. Pass AXIOM_DATA_DIR
            // explicitly on the command — the shell plugin does not inherit env
            // vars set via std::env::set_var at runtime, so without this the
            // backend falls back to a CWD-relative ./data and its SQLite DB /
            // settings never land in %APPDATA%/AxiomFinance.
            let (_rx, _child) = app
                .shell()
                .command(backend_exe)
                .env("AXIOM_DATA_DIR", &data_dir_str)
                .spawn()
                .expect("Failed to spawn backend process");

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
        .invoke_handler(tauri::generate_handler![get_app_data_dir, get_settings_path])
        .run(tauri::generate_context!())
        .expect("error while running Axiom Finance");
}
