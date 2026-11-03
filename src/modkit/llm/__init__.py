from modkit.config import get_settings
from modkit.llm.client import complete, structured


def model_options() -> list[str]:
    """Models for canvas dropdowns: the deployment default first, then MODKIT_MODEL_CHOICES."""
    s = get_settings()
    return list(dict.fromkeys([s.default_model, *s.model_choices]))


__all__ = ["complete", "structured", "model_options"]
