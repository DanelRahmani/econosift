use std::time::Duration;

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

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
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            // Ensure app data directory exists
            let data_dir = app_data_dir();
            std::fs::create_dir_all(&data_dir)
                .expect("Failed to create app data directory");

            // Pass data dir to the backend via environment variable
            std::env::set_var(
                "AXIOM_DATA_DIR",
                data_dir.to_string_lossy().as_ref(),
            );

            // Spawn the Python backend sidecar
            let shell = app.shell();
            let sidecar_command = shell
                .sidecar("axiom-backend")
                .map_err(|e| format!("Failed to create sidecar command: {e}"))
                .unwrap();

            let (_rx, _child) = sidecar_command
                .spawn()
                .expect("Failed to spawn backend sidecar");

            // Wait for backend to be ready (non-blocking)
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match wait_for_backend(30).await {
                    Ok(()) => {
                        println!("Backend is ready");
                    }
                    Err(e) => {
                        eprintln!("Backend startup failed: {e}");
                        let _ = tauri_plugin_dialog::MessageDialogBuilder::new(
                            "Startup Error",
                            &format!(
                                "Failed to start the analysis engine: {e}\n\n\
                                 Please try restarting the application."
                            ),
                        )
                        .kind(tauri_plugin_dialog::MessageDialogKind::Error)
                        .blocking_show(Some(&app_handle));
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_app_data_dir, get_settings_path])
        .run(tauri::generate_context!())
        .expect("error while running Axiom Finance");
}
