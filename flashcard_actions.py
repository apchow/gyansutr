import hashlib
import os
import re

from database import save_note
from ingest import ingest_note
from receipts import log_action, read_actions


CARDS_DIR = os.path.join("workspace", "cards")
VAULT_DIR = "vault"


def _existing_action(preview_id):
    return next((item for item in read_actions() if item.get("preview_id") == preview_id), None)


def _render_cards(preview):
    lines = [f"# Flashcards: {preview.get('topic', 'Reviewed preview')}", "", f"<!-- preview_id:{preview['preview_id']} -->", ""]
    for index, card in enumerate(preview.get("cards", []), start=1):
        lines.extend([f"## Card {index}", "", f"**Q: {card['front']}**", ""])
        if card.get("back"):
            lines.extend([f"A: {card['back']}", ""])
        source = card.get("source")
        if source:
            lines.append(f"Source: {source.get('filename', 'Indexed Document')} (page {source.get('page') or 'unknown'}, chunk {source.get('chunk_id', 'unknown')})")
            lines.append("")
            lines.append(f"> {source.get('excerpt', '')}")
            lines.append("")
        lines.extend(["---", ""])
    return "\n".join(lines).rstrip() + "\n"


def _append_obsidian_cards(preview, title, vault_dir):
    safe_title = re.sub(r'[<>:"/\\|?*]+', "_", title).strip(" .") or "Untitled"
    export_path = os.path.join(vault_dir, f"{safe_title}_cards.md")
    os.makedirs(vault_dir, exist_ok=True)
    marker = f"<!-- preview_id:{preview['preview_id']} -->"
    if os.path.exists(export_path):
        with open(export_path, "r", encoding="utf-8") as export_file:
            if marker in export_file.read():
                return export_path
    with open(export_path, "a", encoding="utf-8") as export_file:
        export_file.write("\n" + _render_cards(preview))
    return export_path


def approve_flashcards(preview, note_id, title, content, export_obsidian=False, cards_dir=None, vault_dir=None):
    if not preview.get("cards"):
        return {"status": "invalid", "result": "This preview contains no parseable cards."}
    preview_id = preview["preview_id"]
    existing = _existing_action(preview_id)
    if existing:
        return {"status": "already_resolved", "action": existing}

    cards_dir = cards_dir or CARDS_DIR
    vault_dir = vault_dir or VAULT_DIR
    os.makedirs(cards_dir, exist_ok=True)
    artifact_path = os.path.join(cards_dir, f"{preview_id}.md")
    artifact = _render_cards(preview)
    with open(artifact_path, "w", encoding="utf-8", newline="\n") as artifact_file:
        artifact_file.write(artifact)
        artifact_file.flush()
        os.fsync(artifact_file.fileno())
    artifact_hash = hashlib.sha256(artifact.encode("utf-8")).hexdigest()

    marker = f"<!-- preview_id:{preview_id} -->"
    if marker not in content:
        content = content.rstrip() + "\n\n" + artifact
    saved_note_id = save_note(note_id, title, content)
    ingest_note(saved_note_id, title, content)

    result = "approved"
    obsidian_path = None
    if export_obsidian:
        try:
            obsidian_path = _append_obsidian_cards(preview, title, vault_dir)
            result = "approved; Obsidian sidecar exported"
        except Exception as error:
            result = f"approved; Obsidian export failed: {error}"

    receipt = log_action(
        preview_id=preview_id,
        approval="approved",
        artifact_path=artifact_path,
        artifact_hash=artifact_hash,
        obsidian_path=obsidian_path,
        result=result,
    )
    return {"status": "approved", "note_id": saved_note_id, "artifact_path": artifact_path, "artifact_hash": artifact_hash, "result": result, "receipt": receipt}


def cancel_flashcards(preview_id):
    existing = _existing_action(preview_id)
    if existing:
        return {"status": "already_resolved", "action": existing}
    receipt = log_action(preview_id=preview_id, approval="cancelled", artifact_path=None, artifact_hash=None, result="cancelled")
    return {"status": "cancelled", "receipt": receipt}