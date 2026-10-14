"""A profile-sensitive cache identity; a timestamp alone can collide within a second."""
from __future__ import annotations

import hashlib
import json


def profile_digest(profile: dict) -> str:
    if not isinstance(profile, dict):
        raise ValueError('invalid_research_profile')
    raw = json.dumps(profile, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    # Not authentication or attestation; used only after per-user cache scoping.
    return hashlib.sha256(raw).hexdigest()
