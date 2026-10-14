from functools import lru_cache

import chromadb


@lru_cache(maxsize=2)
def _get_client(path):
    return chromadb.PersistentClient(path=path)


@lru_cache(maxsize=8)
def get_collection(path="./chroma_db", name="gyansutr"):
    return _get_client(path).get_or_create_collection(name=name)