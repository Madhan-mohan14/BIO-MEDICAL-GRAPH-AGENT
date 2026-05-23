"""Model Armor plugin loader — gated behind MODEL_ARMOR_ENDPOINT env var."""
import os
from dotenv import load_dotenv

load_dotenv()


def get_model_armor_plugin():
    """Return a configured Model Armor plugin, or None if not configured.

    Gated behind MODEL_ARMOR_ENDPOINT env var so local dev works without GCP.

    Returns:
        Model Armor plugin instance, or None if env var is not set.
    """
    endpoint = os.getenv("MODEL_ARMOR_ENDPOINT")
    if not endpoint:
        return None

    try:
        from google.adk.safety import ModelArmorPlugin
        return ModelArmorPlugin(
            endpoint=endpoint,
            mode="inspect_and_block",
        )
    except ImportError:
        print(
            "Warning: MODEL_ARMOR_ENDPOINT is set but google.adk.safety is not "
            "available in this ADK version. Model Armor disabled."
        )
        return None
