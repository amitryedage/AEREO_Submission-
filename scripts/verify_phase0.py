"""Verify Phase 0 server startup and /health + /docs responses."""

import multiprocessing
import time
import urllib.request
import uvicorn


def run_server():
    uvicorn.run("certgen.main:app", host="127.0.0.1", port=8000, log_level="error")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    p = multiprocessing.Process(target=run_server)
    p.start()
    time.sleep(2)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health") as resp:
            print("Health check response:", resp.status, resp.read().decode())
            assert resp.status == 200
        with urllib.request.urlopen("http://127.0.0.1:8000/docs") as resp:
            print("Swagger docs response status:", resp.status)
            assert resp.status == 200
        print("Phase 0 server validation completed successfully!")
    finally:
        p.terminate()
        p.join()
