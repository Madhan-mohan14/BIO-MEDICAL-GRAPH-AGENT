"""HITL feedback handler — stores thumbs-up/down to Firestore (prod) or local JSONL (dev)."""
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def store_feedback(
    session_id: str,
    query: str,
    answer: str,
    rating: str,
    user_id: str = "anonymous",
) -> dict:
    """Store a user feedback signal.

    Writes to Firestore collection 'feedback' when GOOGLE_CLOUD_PROJECT is set,
    falls back to local JSONL file for local dev.

    Args:
        session_id: The session that produced the answer.
        query: The original user query.
        answer: The answer that was rated.
        rating: 'up' or 'down'.
        user_id: Optional user identifier.

    Returns:
        Dict with keys: session_id, rating, stored_at.
    """
    stored_at = datetime.utcnow().isoformat()
    record = {
        "session_id": session_id,
        "user_id": user_id,
        "query": query,
        "answer": answer,
        "rating": rating,
        "stored_at": stored_at,
    }

    if os.getenv("GOOGLE_CLOUD_PROJECT"):
        _store_firestore(record)
    else:
        _store_file(record)

    return {"session_id": session_id, "rating": rating, "stored_at": stored_at}


def _store_firestore(record: dict) -> None:
    from google.cloud import firestore
    db = firestore.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])
    db.collection("feedback").add(record)


def _store_file(record: dict) -> None:
    import json
    from pathlib import Path
    log_dir = Path(os.getenv("FEEDBACK_DIR", "./feedback_logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
