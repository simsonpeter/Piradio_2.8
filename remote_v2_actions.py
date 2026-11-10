"""Strict device-independent input validation for PiRadio Smart Remote 2.0.

Flask merely enqueues validated commands. The Pygame main thread owns the
Tamil Bible player and station favourites. Avoid mutating these from workers.
"""

BIBLE_ACTIONS = frozenset({
    "select", "play", "pause", "next", "prev", "stop", "bookmark"
})
FAVORITE_ACTIONS = frozenset({"toggle", "play"})


def validate_bible_command(payload, chapter_counts):
    """Return a sanitized command for the existing BiblePlayer."""
    if not isinstance(payload, dict):
        raise ValueError("Expected a command object")
    action = payload.get("action")
    if action not in BIBLE_ACTIONS or not isinstance(action, str):
        raise ValueError("Unsupported Bible action")
    if action == "select":
        book = payload.get("book")
        chapter = payload.get("chapter")
        if type(book) is not int or not (0 <= book < len(chapter_counts)):
            raise ValueError("Choose a valid Bible book")
        if type(chapter) is not int or not (1 <= chapter <= chapter_counts[book]):
            raise ValueError("Choose a valid Bible chapter")
        autoplay = payload.get("autoplay", False)
        if type(autoplay) is not bool:
            raise ValueError("Invalid autoplay setting")
        return {"action": action, "book": book, "chapter": chapter,
                "autoplay": autoplay}
    return {"action": action}


def validate_favorite_command(payload, station_count):
    """Validate index without wrapping into unrelated stations."""
    if not isinstance(payload, dict):
        raise ValueError("Expected a command object")
    action = payload.get("action")
    if action not in FAVORITE_ACTIONS or not isinstance(action, str):
        raise ValueError("Unsupported favourite action")
    index = payload.get("index")
    if type(index) is not int or not (0 <= index < station_count):
        raise ValueError("Choose a valid station")
    return {"action": action, "index": index}
