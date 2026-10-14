import requests


def get_embedding(text):
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["embedding"]