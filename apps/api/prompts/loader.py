from pathlib import Path

_PROMPT_CACHE: dict[str, str] = {}

def load_prompt(name: str) -> str:
    """
    Load a prompt file once and cache it.
    """
    if name in _PROMPT_CACHE:
        return _PROMPT_CACHE[name]

    base = Path(__file__).parent
    path = base / name

    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    _PROMPT_CACHE[name] = text
    return text
