import json
import os
import re
import uuid

import requests

from database import get_note, get_notes_list
from embeddings import get_embedding
from personas import get_persona
from receipts import log_query, log_action
from vector_store import get_collection

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "gyansutr"


def get_available_models():
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=20)
        res.raise_for_status()
        models = [m["name"] for m in res.json().get("models", []) if "embed" not in m["name"].lower()]
        return models if models else ["qwen2.5:1.5b"]
    except Exception:
        return ["qwen2.5:1.5b"]


def query_llm(question, model_name, domain, collection=None):
    collection = collection or get_collection(CHROMA_PATH, COLLECTION_NAME)
    query_emb = get_embedding(question)

    results = collection.query(query_embeddings=[query_emb], n_results=5)
    documents = results["documents"][0] if results.get("documents") and results["documents"] else []
    metadatas = results["metadatas"][0] if results.get("metadatas") and results["metadatas"] else []
    chunk_ids = results.get("ids", [[]])[0] if results.get("ids") else []

    if not documents:
        answer = "No evidence supports this."
        log_query(question=question, model=model_name, retrieved_chunk_ids=chunk_ids, cited_answer_preview=answer)
        return answer, [], chunk_ids

    persona = get_persona(domain)
    sources = []
    context_blocks = []

    for i, doc in enumerate(documents):
        meta = metadatas[i] if (i < len(metadatas) and isinstance(metadatas[i], dict)) else {}
        citation = persona.format_citation(meta.get("filename", "Indexed Document"), meta.get("page"))
        excerpt = (doc[:120].replace("\n", " ") + "...") if doc else "No content available."
        sources.append(f"{citation}: {excerpt}")
        context_blocks.append(f"Source {citation}:\n{doc}\n")

    context = "\n".join(context_blocks)
    prompt = f"{persona.instructions()}\n\nContext Evidence:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=120,
        )
        res.raise_for_status()
        answer = res.json().get("response", "Error generating response.")
    except requests.exceptions.Timeout:
        answer = "The local model timed out. Try again or select a smaller model."
    except requests.exceptions.ConnectionError:
        answer = "Could not connect to Ollama at localhost:11434. Start Ollama and try again."
    except requests.exceptions.RequestException:
        answer = "Ollama could not complete this request. Please try again."
    # Check for tool call
    tool_call = try_parse_tool_call(answer)
    if tool_call and tool_call.get("tool") == "create_flashcard_deck":
        result = execute_create_flashcard_deck(tool_call["args"], model_name)
        log_query(question=question, model=model_name, retrieved_chunk_ids=chunk_ids, cited_answer_preview=result["user_message"][:500])
        log_action(tool="create_flashcard_deck", status=result["status"], details=result["user_message"])
        return result["user_message"], sources, chunk_ids

    log_query(question=question, model=model_name, retrieved_chunk_ids=chunk_ids, cited_answer_preview=answer[:500])
    return answer, sources, chunk_ids


def try_parse_tool_call(text: str):
    """Extract JSON tool call from LLM output. Returns None if not a tool call."""
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and obj.get("tool"):
            return obj
    except json.JSONDecodeError:
        pass
    return None


def execute_create_flashcard_deck(args: dict, model_name: str):
    """Validate and execute the create_flashcard_deck tool call deterministically."""
    source = args.get("source_note", "").strip()
    deck_name = args.get("deck_name", "Flashcards").strip()
    count = min(int(args.get("card_count", 10)), 30)

    # Find the note by title
    note = None
    for n in get_notes_list():
        if n["title"].lower() == source.lower() or n["title"].lower() == source.replace(".md", "").lower():
            note = get_note(n["id"])
            break

    if not note:
        return {
            "status": "failed",
            "user_message": f"⚠️ Could not find '{source}' in your vault. Tool call aborted."
        }

    # Generate flashcards from the note content
    note_content = note["content"]
    filename = f"{note['title'].replace(' ', '_')}.md"

    rules = f"""Generate exactly {count} concise Q&A pairs based ONLY on the note content below. For each, cite the source.
Format each exactly as:
**Q: [Question]**
A: [Answer]
Source: [Note: {filename}]
---"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model_name, "prompt": f"{rules}\n\nNote content:\n{note_content}", "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        raw_output = response.json().get("response", "Failed to generate.")
    except requests.exceptions.RequestException:
        return {
            "status": "failed",
            "user_message": "⚠️ Could not connect to Ollama to generate flashcards. Try again."
        }

    # Parse the cards
    cards = _parse_cards(raw_output, "student", [])

    if not cards:
        return {
            "status": "failed",
            "user_message": "⚠️ The model did not produce parseable flashcards. Try again."
        }

    # Write the deck to the vault
    os.makedirs("vault", exist_ok=True)
    out_filename = f"{deck_name.replace(' ', '_')}_flashcards.md"
    out_path = os.path.join("vault", out_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {deck_name}\n\n")
        f.write(f"_Generated from: {note['title']}_\n\n")
        for i, card in enumerate(cards, 1):
            f.write(f"## Card {i}\n**Q:** {card['front']}\n\n**A:** {card['back']}\n\n---\n\n")

    return {
        "status": "success",
        "user_message": f"✅ Created **{out_filename}** with {len(cards)} flashcards in your Obsidian vault."
    }


def _parse_cards(raw_output, domain, sources):
    cards = []
    for block in re.split(r"\n\s*---+\s*\n", raw_output):
        source_match = re.search(r"(?:Source|Sources)\s*:\s*\[(\d+)\]", block, re.IGNORECASE)
        source_index = int(source_match.group(1)) - 1 if source_match else 0
        source = sources[source_index] if 0 <= source_index < len(sources) else None

        if "student" in domain.lower():
            front_match = re.search(r"\*\*Q:\s*(.+?)\*\*", block, re.IGNORECASE | re.DOTALL)
            if not front_match:
                front_match = re.search(r"(?:^|\n)Q:\s*(.+?)(?=\n)", block, re.IGNORECASE)
            back_match = re.search(r"(?:^|\n)A:\s*(.+?)(?=\n\s*(?:Source\s*:|$))", block, re.IGNORECASE | re.DOTALL)
            if front_match and back_match:
                cards.append({"front": front_match.group(1).strip(), "back": back_match.group(1).strip(), "source": source})
        else:
            headline_match = re.search(r"(?:📰\s*)?HEADLINE:\s*(.+?)(?=\n|$)", block, re.IGNORECASE)
            if headline_match:
                cards.append({"front": headline_match.group(1).strip(), "back": "", "source": source})
    return cards


def generate_flashcards(topic, model_name, domain, collection=None):
    collection = collection or get_collection(CHROMA_PATH, COLLECTION_NAME)
    query_emb = get_embedding(topic)

    results = collection.query(query_embeddings=[query_emb], n_results=5)
    documents = results["documents"][0] if results.get("documents") and results["documents"] else []
    metadatas = results["metadatas"][0] if results.get("metadatas") and results["metadatas"] else []
    chunk_ids = results.get("ids", [[]])[0] if results.get("ids") else []
    sources = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        sources.append({
            "filename": metadata.get("filename", "Indexed Document"),
            "page": metadata.get("page"),
            "chunk_id": metadata.get("chunk_id", chunk_ids[index] if index < len(chunk_ids) else f"chunk_{index + 1}"),
            "section": metadata.get("section"),
            "excerpt": document[:400].replace("\n", " "),
        })

    if not documents:
        raw_output = "No relevant information found in the local workspace."
        preview = {"preview_id": str(uuid.uuid4()), "cards": [], "sources": [], "raw_model_output": raw_output, "retrieved_chunk_ids": chunk_ids}
        log_query(topic=topic, model=model_name, retrieved_chunk_ids=chunk_ids, cited_answer_preview=raw_output[:500])
        return preview

    context = "\n\n".join(
        f"[{index + 1}] {source['filename']} (page {source['page']}, chunk {source['chunk_id']}):\n{document}"
        for index, (source, document) in enumerate(zip(sources, documents))
    )

    rules = (
        "Generate exactly 5 concise Q&A pairs based ONLY on the context. For each, cite one context source. "
        "Format each exactly as:\n**Q: [Question]**\nA: [Answer]\nSource: [1]\n---"
        if "Student" in domain
        else "Generate exactly 5 headlines (max 12 words each) based ONLY on the context. Cite one source per headline. "
        "Format each exactly as:\n📰 HEADLINE: [text]\nSource: [1]\n---"
    )

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model_name, "prompt": f"{rules}\n\nContext:\n{context}", "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    raw_output = response.json().get("response", "Failed to generate.")
    preview = {
        "preview_id": str(uuid.uuid4()),
        "cards": _parse_cards(raw_output, domain, sources),
        "sources": sources,
        "raw_model_output": raw_output,
        "retrieved_chunk_ids": chunk_ids,
    }
    log_query(topic=topic, model=model_name, retrieved_chunk_ids=chunk_ids, cited_answer_preview=raw_output[:500])
    return preview