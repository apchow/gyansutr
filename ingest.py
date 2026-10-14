import hashlib
import io
import os
import re

import chromadb
import docx
import pymupdf
import pytesseract
from PIL import Image

from embeddings import get_embedding
from vector_store import get_collection

WORKSPACE_DOCS = "workspace/documents"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "gyansutr"


def compute_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as afile:
        for chunk in iter(lambda: afile.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def clean_text(text):
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


HEADING_PATTERN = re.compile(r"^\s*(?:Course Code:|Unit\s+[IVX]+\b|#{1,4}\s+|\d+\.\d+\b).*$", re.IGNORECASE)


def chunk_text(text, max_words=500, overlap=80, section_hint="General"):
    cleaned = clean_text(text)
    if not cleaned:
        return []

    chunks = []
    sections = []
    current_section = section_hint or "General"
    current_lines = []

    for line in cleaned.splitlines():
        if HEADING_PATTERN.match(line):
            if current_lines:
                sections.append((current_section, "\n".join(current_lines)))
            current_section = line.strip().lstrip("# ")
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_section, "\n".join(current_lines)))

    step = max(1, max_words - overlap)
    for section, section_text in sections:
        words = section_text.split()
        for start in range(0, len(words), step):
            chunk = " ".join(words[start:start + max_words])
            if len(chunk.strip()) > 50:
                chunks.append({"text": chunk, "section": section})
    return chunks


def _page_section(text, fallback):
    for line in text.splitlines():
        if HEADING_PATTERN.match(line):
            return line.strip().lstrip("# ")
    return fallback


def extract_pdf_text(file_path):
    all_pages = []
    doc = pymupdf.open(file_path)
    active_section = "General"

    for page_num, page in enumerate(doc):
        page_text = clean_text(page.get_text("text"))

        if len(page_text.split()) < 40:
            try:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                image = image.convert("L")
                page_text = clean_text(pytesseract.image_to_string(image, config="--psm 6"))
            except Exception:
                page_text = ""

        if not page_text:
            try:
                page_text = clean_text("\n".join(str(block[4]) for block in page.get_text("blocks")))
            except Exception:
                page_text = ""

        if page_text:
            active_section = _page_section(page_text, active_section)
            all_pages.append({
                "page": str(page_num + 1),
                "section_hint": active_section,
                "text": page_text,
            })

    doc.close()
    return all_pages


def ingest_file(filename, progress_callback=None, collection=None):
    file_path = os.path.join(WORKSPACE_DOCS, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_hash = compute_hash(file_path)
    collection = collection or get_collection(CHROMA_PATH, COLLECTION_NAME)

    existing = collection.get(where={"source_hash": file_hash}, limit=1, include=[])
    if existing and existing["ids"]:
        return {"status": "duplicate", "chunks": 0, "source_hash": file_hash, "filename": filename}

    ext = os.path.splitext(filename)[1].lower()
    chunks_data = []

    if progress_callback:
        progress_callback(f"Parsing {filename}...")

    if ext == ".pdf":
        for page_data in extract_pdf_text(file_path):
            page_num = page_data["page"]
            for i, chunk in enumerate(chunk_text(page_data["text"], section_hint=page_data["section_hint"])):
                chunks_data.append({
                    "text": chunk["text"],
                    "meta": {
                        "source_hash": file_hash,
                        "filename": filename,
                        "page": page_num,
                        "section": chunk["section"],
                        "chunk_id": f"p{page_num}_c{i}",
                    },
                })

    elif ext == ".docx":
        doc = docx.Document(file_path)
        full_text = "\n".join([para.text for para in doc.paragraphs])
        for i, chunk in enumerate(chunk_text(full_text)):
            chunks_data.append({
            "text": chunk["text"],
            "meta": {"source_hash": file_hash, "filename": filename, "page": "1", "section": chunk["section"], "chunk_id": f"sec_c{i}"},
            })

    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
            for i, chunk in enumerate(chunk_text(text)):
                chunks_data.append({
                    "text": chunk["text"],
                    "meta": {"source_hash": file_hash, "filename": filename, "page": "1", "section": chunk["section"], "chunk_id": f"sec_c{i}"},
                })

    if not chunks_data:
        return {"status": "empty", "chunks": 0, "source_hash": file_hash, "filename": filename}

    for i in range(0, len(chunks_data), 25):
        batch = chunks_data[i:i + 25]
        if progress_callback:
            progress_callback(f"Embedding batch {i // 25 + 1}...")
        texts = [b["text"] for b in batch]
        metas = [b["meta"] for b in batch]
        ids = [f"{file_hash}_{b['meta']['chunk_id']}" for b in batch]
        embeddings = [get_embedding(t) for t in texts]
        collection.add(documents=texts, embeddings=embeddings, metadatas=metas, ids=ids)

    return {"status": "success", "chunks": len(chunks_data), "source_hash": file_hash, "filename": filename}


def ingest_note(note_id, title, text, collection=None):
    """Embeds a user note into ChromaDB, replacing any previous version."""
    collection = collection or get_collection(CHROMA_PATH, COLLECTION_NAME)

    try:
        collection.delete(where={"note_id": str(note_id)})
    except Exception:
        pass

    full_text = f"Title: {title}\n\n{text}"
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    texts, metas, ids = [], [], []
    for i, chunk in enumerate(chunks):
        texts.append(chunk["text"])
        metas.append({
            "filename": f"Note: {title}",
            "note_id": str(note_id),
            "chunk_id": f"n{note_id}_c{i}",
            "section": chunk["section"],
        })
        ids.append(f"note_{note_id}_c{i}")

    embeddings = [get_embedding(t) for t in texts]
    collection.add(documents=texts, embeddings=embeddings, metadatas=metas, ids=ids)
    return len(chunks)
