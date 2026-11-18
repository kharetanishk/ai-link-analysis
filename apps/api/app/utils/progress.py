from collections.abc import Callable

# stage, percent (None = same rakho), user-friendly message
Progress = Callable[[str, int | None, str], None]


def noop(stage: str, percent: int | None, message: str) -> None:
    return None
