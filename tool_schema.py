"""Contract for the one deterministic tool call.

Ollama on qwen2.5:1.5b / phi3 does not get a tool menu. The app detects a
fixed flashcard intent, asks for this JSON only, validates it, and then calls
create_flashcard_deck. Any other shape is rejected.

The LLM emits an INTENT (source_note, deck_name, card_count). The backend
generates the actual flashcards deterministically. This keeps the LLM output
small and the execution auditable.
"""

CREATE_FLASHCARD_DECK = {
    "name": "create_flashcard_deck",
    "description": (
        "Create a flashcard deck from a note in the vault. "
        "Emit this only when the user asks for flashcards, a deck, or a quiz."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_note", "deck_name"],
        "properties": {
            "source_note": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Filename or title of the note to base flashcards on.",
            },
            "deck_name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120,
                "description": "Name for the new flashcard deck file.",
            },
            "card_count": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "default": 10,
                "description": "Number of flashcards to generate (default 10, max 30).",
            },
        },
    },
}

TOOL_CALL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "args"],
    "properties": {
        "tool": {"const": "create_flashcard_deck"},
        "args": CREATE_FLASHCARD_DECK["parameters"],
    },
}

EXAMPLE_TOOL_CALL = {
    "tool": "create_flashcard_deck",
    "args": {
        "source_note": "quantum_notes.md",
        "deck_name": "Quantum Mechanics Flashcards",
        "card_count": 10,
    },
}
