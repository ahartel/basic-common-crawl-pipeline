from typing import Optional
from trafilatura import extract

def extract_text(content: str) -> Optional[str]:
    text = extract(content, include_comments=False,
                   include_tables=False, deduplicate=True)
    # also return None if utf-8 decoding failed
    if text is None or isinstance(text, bytes):
        return None
    return text