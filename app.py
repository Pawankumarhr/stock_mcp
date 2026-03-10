"""
Stock Analysis Platform — Render Entry Point
Launches the Streamlit web UI directly.
"""
import sys, os, subprocess


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    port = os.environ.get("PORT", "8501")

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(here, "streamlit_app.py"),
        "--server.port", port,
        "--server.headless", "true",
        "--server.address", "0.0.0.0",
    ]

    print(f"🚀 Starting Streamlit on port {port} ...")
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
