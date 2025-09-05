from typing import Tuple, Any

def resolve_role(cam: Any, role: str) -> Tuple[Any, Any, Any, bool]:
    """Return defaults indicating the role should not run."""
    return None, None, None, False
