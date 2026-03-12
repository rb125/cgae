"""
Modal deployment for CGAE Live Economy Backend.

Runs the live_runner continuously and persists results to Modal Volume.
Dashboard (Streamlit Cloud) reads from this volume via Modal's web endpoint.
"""

import modal

# Create Modal app
app = modal.App("cgae-economy")

# Create persistent volume for results
volume = modal.Volume.from_name("cgae-results", create_if_missing=True)

# Define container image with dependencies and cached audits
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .pip_install("fastapi>=0.110,<1")
    .env({
        "PYTHONUNBUFFERED": "1",
    })
    .add_local_dir("server/live_results/audit_cache", remote_path="/app/audit_cache")  # Keep add_local_* last
)


@app.function(
    image=image,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_name("azure_credentials")],  # All credentials in one secret
    timeout=86400,  # 24 hours
    cpu=2.0,
    memory=4096,
    keep_warm=1,  # Keep one instance always running
)
def run_live_economy():
    """Run the CGAE live economy continuously."""
    import json
    import os
    import threading
    import time
    from pathlib import Path

    # Set output directory to mounted volume
    os.environ["CGAE_OUTPUT_DIR"] = "/results"

    # Write heartbeat metadata so scheduler can detect healthy/stale workers.
    lock_path = Path("/results/.live_runner.lock")
    stop_heartbeat = threading.Event()

    def heartbeat():
        while not stop_heartbeat.is_set():
            payload = {
                "status": "running",
                "pid": os.getpid(),
                "last_heartbeat": time.time(),
            }
            lock_path.write_text(json.dumps(payload), encoding="utf-8")
            volume.commit()
            stop_heartbeat.wait(30)

    heartbeat_thread = threading.Thread(target=heartbeat, name="live-runner-heartbeat", daemon=True)
    heartbeat_thread.start()

    # Import and run
    from server.live_runner import LiveSimulationRunner, LiveSimConfig

    config = LiveSimConfig(
        num_rounds=-1,  # Infinite
        output_dir="/results",
        live_audit_cache_dir="/app/audit_cache",  # Use pre-computed audits
        seed=42,
    )

    runner = LiveSimulationRunner(config)
    try:
        runner.run()
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=2)
        if lock_path.exists():
            lock_path.unlink()
        volume.commit()


@app.function(
    image=image,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_name("azure_credentials")],
    schedule=modal.Period(minutes=5),
    timeout=120,
)
def ensure_live_economy_running():
    """
    Scheduled keeper that starts the runner when no fresh heartbeat exists.

    This runs automatically after `modal deploy` and then every 5 minutes.
    """
    import json
    import time
    from pathlib import Path

    volume.reload()
    lock_path = Path("/results/.live_runner.lock")
    now = time.time()
    stale_after_seconds = 15 * 60

    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            last_heartbeat = float(lock_data.get("last_heartbeat", 0))
            if now - last_heartbeat < stale_after_seconds:
                return {
                    "status": "runner_healthy",
                    "last_heartbeat": last_heartbeat,
                }
        except Exception:
            # Fall through and restart if lock file is malformed.
            pass

    # Write a startup heartbeat immediately to avoid duplicate starts.
    startup_payload = {
        "status": "starting",
        "last_heartbeat": now,
    }
    lock_path.write_text(json.dumps(startup_payload), encoding="utf-8")
    volume.commit()
    run_live_economy.spawn()
    return {"status": "runner_started", "started_at": now}


@app.function(
    image=image,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_name("azure_credentials")],
    timeout=300,
)
@modal.fastapi_endpoint(method="GET")
def get_results(path: str = "final_summary.json"):
    """
    Web endpoint to serve result files to Streamlit dashboard.

    Usage: https://your-modal-app.modal.run/get_results?path=final_summary.json
    """
    import json
    from pathlib import Path

    from fastapi import HTTPException

    volume.reload()
    results_root = Path("/results").resolve()
    requested_path = Path(path)

    # Block absolute paths and parent traversal.
    if requested_path.is_absolute() or ".." in requested_path.parts:
        raise HTTPException(status_code=400, detail="Invalid file path")

    file_path = (results_root / requested_path).resolve()
    if results_root not in file_path.parents and file_path != results_root:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.function(
    image=image,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_name("azure_credentials")],
    timeout=60,
)
@modal.fastapi_endpoint(method="GET")
def list_results():
    """
    List all available result files.

    Usage: https://your-modal-app.modal.run/list_results
    """
    from pathlib import Path

    volume.reload()
    results_dir = Path("/results")
    if not results_dir.exists():
        return {"files": []}

    files = [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        }
        for f in results_dir.glob("*.json")
    ]
    
    return {"files": files}


@app.function(
    image=image,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_name("azure_credentials")],
    timeout=60,
)
@modal.fastapi_endpoint(method="GET")
def health():
    """
    Report live runner health based on lock-file heartbeat.

    Usage: https://your-modal-app.modal.run/health
    """
    import json
    import time
    from pathlib import Path

    from fastapi import HTTPException

    volume.reload()
    lock_path = Path("/results/.live_runner.lock")
    now = time.time()
    stale_after_seconds = 15 * 60

    if not lock_path.exists():
        return {
            "status": "down",
            "reason": "heartbeat_lock_missing",
            "stale_after_seconds": stale_after_seconds,
            "timestamp": now,
        }

    try:
        lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Malformed lock file: {e}") from e

    last_heartbeat = float(lock_data.get("last_heartbeat", 0))
    age_seconds = max(0.0, now - last_heartbeat)
    if age_seconds >= stale_after_seconds:
        return {
            "status": "stale",
            "age_seconds": age_seconds,
            "last_heartbeat": last_heartbeat,
            "stale_after_seconds": stale_after_seconds,
            "lock": lock_data,
        }

    return {
        "status": "running",
        "age_seconds": age_seconds,
        "last_heartbeat": last_heartbeat,
        "stale_after_seconds": stale_after_seconds,
        "lock": lock_data,
    }


@app.local_entrypoint()
def main():
    """Manual helper for `modal run modal_deploy.py`."""
    print("Triggering CGAE live economy run once...")
    run_live_economy.remote()
