# -*- mode: python ; coding: utf-8 -*-
"""
GyanSutr.spec — PyInstaller spec for GyanSutr.exe

Key fixes:
- copy_metadata('streamlit')   → fixes PackageNotFoundError on startup
- copy_metadata('chromadb')    → ChromaDB uses importlib.metadata internally
- copy_metadata('pymupdf')     → also uses version lookups
- collect_all('chromadb')      → grabs dynamic submodules ChromaDB needs
- Streamlit static assets      → bundled via collect_data_files
- .streamlit/ config           → bundled so Streamlit can read theme + CORS settings
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

# ChromaDB — bundles code, data, binaries, and hidden submodules
chromadb_datas, chromadb_binaries, chromadb_hiddenimports = collect_all("chromadb")

# Streamlit static assets (frontend HTML/JS/CSS, healthz page, etc.)
streamlit_datas = collect_data_files("streamlit")

# Package metadata (fixes importlib.metadata.version() calls)
metadata_datas = (
    copy_metadata("streamlit")
    + copy_metadata("chromadb")
    + copy_metadata("pymupdf")
    + copy_metadata("python-docx")
    + copy_metadata("pillow")
    + copy_metadata("requests")
    + copy_metadata("ollama")
    + copy_metadata("numpy")
)

# Your app's Python files — bundled so Streamlit can find app.py at runtime
app_datas = [
    ("app.py", "."),
    ("database.py", "."),
    ("embeddings.py", "."),
    ("flashcard_actions.py", "."),
    ("ingest.py", "."),
    ("personas.py", "."),
    ("query.py", "."),
    ("receipts.py", "."),
    ("tool_schema.py", "."),
    ("vector_store.py", "."),
    ("run_app.py", "."),
    (".streamlit", ".streamlit"),
]

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=chromadb_binaries,
    datas=chromadb_datas + streamlit_datas + metadata_datas + app_datas,
    hiddenimports=chromadb_hiddenimports + [
        # Streamlit
        "streamlit",
        "streamlit.web.cli",
        "streamlit.runtime.scriptrunner.magic_funcs",
        "streamlit.runtime.scriptrunner.script_runner",
        # Document parsing
        "docx",
        "docx.opc",
        "docx.oxml",
        "docx.oxml.ns",
        "docx.shared",
        "pymupdf",
        "fitz",
        "pytesseract",
        "PIL",
        "PIL.Image",
        # Stdlib / native
        "sqlite3",
        "_ssl",
        "_hashlib",
        # ML / vector deps
        "onnxruntime",
        "tokenizers",
        "tqdm",
        "hnswlib",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "venv",
        "__pycache__",
        ".cache",
        "tests",
        ".pytest_cache",
        "matplotlib",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GyanSutr",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GyanSutr",
)