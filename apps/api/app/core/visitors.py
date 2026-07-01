from __future__ import annotations

import re
from hashlib import sha256

VISITOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


def visitor_key_for_user(user_id: object) -> str:
    """Return the privacy-preserving visitor key for an authenticated user.

    Key parameter `user_id` is the stable database user id. Return value is a
    prefixed SHA-256 digest suitable for analytics dedupe. Side effect: none.
    """

    digest = sha256(str(user_id).encode("utf-8")).hexdigest()
    return f"user:{digest}"


def visitor_key_for_anonymous(visitor_id: str | None) -> str | None:
    """Return the privacy-preserving visitor key for a browser-local visitor id.

    Key parameter `visitor_id` is the frontend-generated anonymous id. Return
    value is a prefixed SHA-256 digest, or None when the id shape is not
    trusted. Side effect: none.
    """

    normalized_visitor_id = (visitor_id or "").strip()
    if not VISITOR_ID_PATTERN.fullmatch(normalized_visitor_id):
        return None
    digest = sha256(normalized_visitor_id.encode("utf-8")).hexdigest()
    return f"anon:{digest}"
