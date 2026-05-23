"""Gemini-as-Judge before_model_callback — blocks personal medical advice requests.

Checks only the latest user message for direct medical advice patterns.
Does NOT scan the full conversation context (which legitimately contains clinical text).
"""
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# Patterns that indicate the USER is requesting personal medical advice.
# These are checked only in the last user message, not the full context.
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

    Only checks the most recent user message — not the full conversation context,
    which legitimately contains clinical text that would cause false positives.

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
