from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent
POLICY_FILE = BASE_DIR / "policies.md"

CHROMA_DIR = BASE_DIR / "chroma_db"

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(
    path=str(CHROMA_DIR)
)

collection = client.get_or_create_collection(
    name="citycare_policies"
)


def load_policy_chunks():
    """Read policies.md and split it into simple chunks."""

    text = POLICY_FILE.read_text(encoding="utf-8")

    sections = [
        section.strip()
        for section in text.split("\n## ")
        if section.strip()
    ]

    return sections


def index_policies():
    """Store policy chunks and their embeddings in ChromaDB."""

    chunks = load_policy_chunks()

    if not chunks:
        return

    embeddings = model.encode(chunks).tolist()

    ids = [
        f"policy_{i}"
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
    )


def search_policies(query: str, top_k: int = 3):
    """Search the clinic policies and return the most relevant chunks."""

    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    documents = results.get("documents", [[]])[0]

    return documents