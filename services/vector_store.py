import chromadb
from services.embeddings import get_embedding, build_candidate_text

# Persistent client — saves vectors to disk in ./chroma_data
# so they survive server restarts
_client = chromadb.PersistentClient(path="./chroma_data")

_collection = _client.get_or_create_collection(
    name="candidates",
    metadata={"hnsw:space": "cosine"}  # use cosine similarity for matching
)


def upsert_candidate(candidate):
    """
    Adds or updates a candidate's vector in ChromaDB.
    'upsert' = update if exists, insert if new — keyed by candidate ID.
    """
    text = build_candidate_text(candidate)
    vector = get_embedding(text)

    _collection.upsert(
        ids=[str(candidate.id)],
        embeddings=[vector],
        metadatas=[{
            "name": candidate.name or "Unknown",
            "current_role": candidate.current_role or "",
            "years_experience": candidate.years_experience or 0,
        }],
        documents=[text]
    )


def search_candidates(job_description: str, top_n: int = 5):
    """
    Embeds a job description and finds the top_n most similar candidates.
    Returns a list of dicts with candidate_id, score, and metadata.
    """
    query_vector = get_embedding(job_description)

    results = _collection.query(
        query_embeddings=[query_vector],
        n_results=top_n
    )

    matches = []
    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]

    for i in range(len(ids)):
        # ChromaDB returns distance (lower = more similar)
        # we convert to similarity score (higher = more similar) for readability
        similarity = 1 - distances[i]
        matches.append({
            "candidate_id": int(ids[i]),
            "similarity_score": round(similarity, 4),
            "name": metadatas[i]["name"],
            "current_role": metadatas[i]["current_role"],
            "years_experience": metadatas[i]["years_experience"],
        })

    return matches