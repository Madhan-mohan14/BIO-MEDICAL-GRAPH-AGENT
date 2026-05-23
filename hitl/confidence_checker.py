"""HITL confidence gate — parses synthesis_agent output and emits review events."""
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

CONFIDENCE_THRESHOLD = 0.70


@dataclass
class HITLEvent:
    """An event that requires human-in-the-loop review.

    Attributes:
        type: 'low_confidence' or 'new_edge'.
        session_id: The session that triggered the event.
        answer: The draft answer text.
        reasoning: The reasoning chain from synthesis_agent.
        confidence: Confidence score (0.0–1.0).
        new_edge_data: Structured new-edge payload (for type='new_edge').
    """
    type: str
    session_id: str
    answer: str
    reasoning: str
    confidence: float = 0.0
    new_edge_data: dict = field(default_factory=dict)


_KNOWN_LABELS = {"ANSWER:", "CONFIDENCE:", "SOURCES:", "REASONING:", "NEEDS_REVIEW:", "NEW_EDGE:", "CITATIONS:"}


def _starts_known_label(line: str) -> bool:
    return any(line.startswith(lbl) for lbl in _KNOWN_LABELS)


def parse_synthesis_output(text: str) -> dict:
    """Parse the structured output from synthesis_agent.

    Handles multi-line ANSWER and REASONING fields — accumulates continuation
    lines until the next known label is encountered.

    Args:
        text: Raw text output from synthesis_agent.

    Returns:
        Dict with keys: answer, confidence, sources, reasoning,
        needs_review, new_edge, citations.
    """
    result: dict = {
        "answer": "",
        "confidence": 0.0,
        "sources": "",
        "reasoning": "",
        "needs_review": False,
        "new_edge": "",
        "citations": [],
    }
    current_field: str | None = None

    for line in text.splitlines():
        if line.startswith("ANSWER:"):
            current_field = "answer"
            result["answer"] = line[7:].strip()
        elif line.startswith("CONFIDENCE:"):
            current_field = "confidence"
            try:
                result["confidence"] = float(line[11:].strip())
            except ValueError:
                pass
        elif line.startswith("SOURCES:"):
            current_field = "sources"
            result["sources"] = line[8:].strip()
        elif line.startswith("REASONING:"):
            current_field = "reasoning"
            result["reasoning"] = line[10:].strip()
        elif line.startswith("NEEDS_REVIEW:"):
            current_field = None
            result["needs_review"] = "true" in line.lower()
        elif line.startswith("NEW_EDGE:"):
            current_field = None
            result["new_edge"] = line[9:].strip()
        elif line.startswith("CITATIONS:"):
            current_field = None
            raw = line[10:].strip()
            result["citations"] = [u.strip() for u in raw.split(",") if u.strip()]
        elif current_field in ("answer", "reasoning") and not _starts_known_label(line):
            # Accumulate continuation lines for multi-line fields.
            if line.strip():
                result[current_field] += "\n" + line

    # Fallback: unstructured response — treat raw text as-is.
    if not result["answer"] and text.strip():
        result["answer"] = text.strip()
        result["confidence"] = 0.5
        result["sources"] = "mixed"
        result["needs_review"] = True

    return result


def check_confidence(
    confidence: float,
    session_id: str,
    answer: str,
    reasoning: str,
) -> HITLEvent | None:
    """Return a HITLEvent if confidence is below threshold, else None.

    Args:
        confidence: Score from synthesis_agent (0.0–1.0).
        session_id: Current session identifier.
        answer: Draft answer text.
        reasoning: Reasoning chain text.

    Returns:
        HITLEvent with type='low_confidence' if below threshold, else None.
    """
    if confidence < CONFIDENCE_THRESHOLD:
        return HITLEvent(
            type="low_confidence",
            session_id=session_id,
            answer=answer,
            reasoning=reasoning,
            confidence=confidence,
        )
    return None
