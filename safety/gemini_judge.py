"""Gemini-as-Judge — blocks medical advice requests + scores answer faithfulness.

Two entry points:
  gemini_judge_callback   — ADK before_model_callback, blocks bad user inputs
  score_faithfulness      — async function, dimensional scoring of synthesis output
"""
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# ── Input blocking ─────────────────────────────────────────────────────────────

# Patterns that indicate the USER is requesting personal medical advice.
# Checked only in the last user message — NOT the full context (which legitimately
# contains clinical text that would trigger false positives).
BLOCK_PATTERNS = [
    "should i take",
    "can i take",
    "am i sick",
    "do i have",
    "diagnose me",
    "is my symptom",
    "what medicine should i",
    "stop taking my",
]

SAFE_FALLBACK = (
    "I can provide information about biomedical research data, but I cannot "
    "give personal medical advice. Please consult a healthcare professional."
)


def gemini_judge_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    """Block the model if the user is asking for personal medical advice.

    Only checks the most recent user message — not the full conversation context.

    Args:
        callback_context: ADK callback context.
        llm_request: The pending LLM request.

    Returns:
        LlmResponse with safe fallback if a block pattern is found, else None.
    """
    user_messages = [
        c for c in (llm_request.contents or []) if c.role == "user"
    ]
    if not user_messages:
        return None

    last_user = user_messages[-1]
    for part in last_user.parts or []:
        text = getattr(part, "text", "") or ""
        if any(pattern in text.lower() for pattern in BLOCK_PATTERNS):
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=SAFE_FALLBACK)],
                )
            )
    return None


# ── Output faithfulness scoring ────────────────────────────────────────────────

_JUDGE_PROMPT = """\
You are a strict factual judge for a biomedical RAG system.

Question: {question}

Retrieved context (graph + semantic search results):
{context}

Generated answer:
{answer}

Score this answer on three dimensions:

1. faithfulness (0.0-1.0)
   What fraction of factual claims in the answer are directly supported by the
   retrieved context? 1.0 = every claim is grounded; 0.0 = no claims are grounded.

2. hallucination (true/false)
   Does the answer assert any biomedical fact that is NOT present in the retrieved
   context? A claim is hallucinated if the judge cannot locate its source in the
   context, even loosely.

3. relevance (0.0-1.0)
   Does the answer actually address what the question asked?
   1.0 = fully on-topic; 0.0 = completely off-topic.

Reply with ONLY valid JSON — no markdown fences, no explanation:
{{"faithfulness": <float>, "hallucination": <bool>, "relevance": <float>}}"""

# Gemini Flash used as judge — cheaper + faster than the synthesis model.
_JUDGE_MODEL = os.environ.get("GOOGLE_ADK_MODEL", "gemini-2.0-flash")


async def score_faithfulness(
    question: str,
    context: str,
    answer: str,
) -> dict[str, float | bool]:
    """Score synthesis output faithfulness using Gemini as judge.

    Calls Gemini asynchronously — invoke AFTER synthesis_agent completes,
    before returning the final response to the user.

    Args:
        question: The original user question.
        context: Combined retrieval context (cypher + semantic + web results).
        answer: The synthesis_agent ANSWER field text.

    Returns:
        Dict with keys:
          faithfulness  (float 0-1): fraction of claims grounded in context
          hallucination (bool): True if any claim is ungrounded
          relevance     (float 0-1): how well answer addresses the question
          block         (bool): True if faithfulness < 0.70 OR hallucination is True
    """
    from google import genai  # lazy import — not all entry points need the client

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _JUDGE_PROMPT.format(
        question=question,
        context=context[:4000],  # cap to avoid token overflow
        answer=answer,
    )

    response = await client.aio.models.generate_content(
        model=_JUDGE_MODEL,
        contents=prompt,
    )

    raw = (response.text or "").strip()
    # Strip markdown fences if the model ignores the no-fence instruction
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {
            "faithfulness": 0.0,
            "hallucination": True,
            "relevance": 0.0,
            "block": True,
            "parse_error": raw[:200],
        }

    try:
        scores: dict = json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "faithfulness": 0.0,
            "hallucination": True,
            "relevance": 0.0,
            "block": True,
            "parse_error": match.group()[:200],
        }

    scores["block"] = (
        float(scores.get("faithfulness", 1.0)) < 0.70
        or bool(scores.get("hallucination", False))
    )
    return scores
