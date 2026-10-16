import os
import sys

# Fix for PyInstaller: streamlit calls importlib.metadata.version("streamlit")
# which fails if the .dist-info folder wasn't bundled
try:
    import importlib.metadata as _md
    from importlib.metadata import PackageNotFoundError
    try:
        _md.version("streamlit")
    except PackageNotFoundError:
        import types
        fake_dist = types.SimpleNamespace(version="1.64.0")
        _md.distribution = lambda name: fake_dist if name == "streamlit" else (_ for _ in ()).throw(PackageNotFoundError(name))
except Exception:
    pass

import streamlit.web.cli as stcli


def resolve_path(path):
    if getattr(sys, "_MEIPASS", False):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), path)


if __name__ == "__main__":
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.abspath(os.path.dirname(__file__))
    os.chdir(base)
    os.makedirs(os.path.join(base, "workspace", "documents"), exist_ok=True)
    os.makedirs(os.path.join(base, "workspace", "receipts"), exist_ok=True)
    os.makedirs(os.path.join(base, "workspace", "cards"), exist_ok=True)
    os.makedirs(os.path.join(base, "vault"), exist_ok=True)
    os.makedirs(os.path.join(base, "chroma_db"), exist_ok=True)

    sys.argv = [
        "streamlit", "run", resolve_path("app.py"),
        "--global.developmentMode=false",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())