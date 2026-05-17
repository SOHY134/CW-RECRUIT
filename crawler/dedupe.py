from rapidfuzz import fuzz


def is_duplicate(title: str, existing_titles: list[str], threshold: int = 86) -> bool:
    clean = (title or "").strip()
    if not clean:
        return True
    return any(fuzz.ratio(clean, old) >= threshold for old in existing_titles)
