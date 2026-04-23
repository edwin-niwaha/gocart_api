from __future__ import annotations


GUEST_SESSION_FLAG = "guest_session_initialized"


def get_guest_session_key(request) -> str | None:
    session = getattr(request, "session", None)
    if session is None:
        return None
    return session.session_key


def ensure_guest_session(request) -> str:
    session = request.session
    if session.session_key is None:
        session[GUEST_SESSION_FLAG] = True
        session.save()
    elif GUEST_SESSION_FLAG not in session:
        session[GUEST_SESSION_FLAG] = True
    return session.session_key


def get_request_guest_session_key(request, *, create: bool = False) -> str | None:
    if getattr(getattr(request, "user", None), "is_authenticated", False):
        return None
    if create:
        return ensure_guest_session(request)
    return get_guest_session_key(request)
