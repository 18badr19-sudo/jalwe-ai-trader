"""Keep Railway health tied to both research and dashboard processes."""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


def supervise(commands, stop, grace=10, interval=0.5):
    children = []
    try:
        for name, command in commands:
            if stop.is_set():
                return 0
            child = subprocess.Popen(command, start_new_session=True)
            children.append((name, child))
            print(f"Supervisor started {name} pid={child.pid}", flush=True)
        while not stop.wait(interval):
            for name, child in children:
                code = child.poll()
                if code is not None:
                    print(f"Supervisor: {name} exited code={code}; requesting service restart", flush=True)
                    return 1
        return 0
    finally:
        # Terminate entire groups, including descendants of an exited parent.
        for _, child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace
        for _, child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for _, child in children:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()


def main():
    os.chdir(Path(__file__).resolve().parent)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    return supervise([
        ("research", [sys.executable, "-u", "apex_research_loop.py"]),
        ("dashboard", [sys.executable, "-m", "streamlit", "run", "dashboard.py",
                       "--server.port", os.getenv("PORT", "8501"),
                       "--server.address", "0.0.0.0"]),
    ], stop)


if __name__ == "__main__":
    sys.exit(main())
