"""Keep TC Radio station navigation separate from temporary YouTube tracks.

Small pure helpers also prevent radio navigation from accidentally entering a
previous YouTube track or an unrelated direct-link source.
"""

def radio_indices(stations):
    """Indices of actual selectable TC Radio streams, in server list order."""
    return [
        index
        for index, station in enumerate(stations)
        if isinstance(station, dict)
        and station.get("url")
        and not station.get("youtube_id")
        and not station.get("direct_link_id")
        and not station.get("language")
    ]


def index_for_url(stations, saved_url):
    if not saved_url:
        return None
    for i in radio_indices(stations):
        if stations[i].get("url") == saved_url:
            return i
    return None


def radio_resume_index(stations, current_idx, saved_url):
    """Reopen remembered real radio; never resume a YouTube queue entry."""
    choices = radio_indices(stations)
    if not choices:
        return None
    saved_index = index_for_url(stations, saved_url)
    if saved_index is not None:
        return saved_index
    if current_idx in choices:
        return current_idx
    return choices[0]


def radio_step_index(stations, current_idx, direction, saved_url=None):
    """Next/previous only within TC Radio; wrap without visiting YouTube."""
    choices = radio_indices(stations)
    if not choices:
        return None
    if current_idx not in choices:
        current_idx = radio_resume_index(stations, current_idx, saved_url)
    if current_idx not in choices:
        return choices[0]
    step = 1 if direction >= 0 else -1
    return choices[(choices.index(current_idx) + step) % len(choices)]
