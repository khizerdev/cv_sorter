from sentence_transformers import SentenceTransformer

# Loaded once when the module is imported — model stays in memory
# all-MiniLM-L6-v2 produces 384-dimensional vectors, fast and good quality
_model = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text: str) -> list[float]:
    """
    Converts text into a 384-dimensional vector.
    Used for both candidate profiles and job descriptions —
    they must use the SAME model to be comparable.
    """
    embedding = _model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def build_candidate_text(candidate) -> str:
    """
    Combines the structured fields into one text blob for embedding.
    This is what actually gets converted to a vector — so it matters
    what we include here. Skills + role + summary capture the essence
    of a candidate better than raw CV text (which has noise: formatting,
    addresses, etc).
    """
    import json
    skills = json.loads(candidate.skills) if candidate.skills else []

    parts = [
        f"Role: {candidate.current_role or ''}",
        f"Skills: {', '.join(skills)}",
        f"Experience: {candidate.years_experience or 0} years",
        f"Education: {candidate.education or ''}",
        f"Summary: {candidate.summary or ''}",
    ]
    return "\n".join(parts)