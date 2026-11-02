"""Simple tenant / role access control. Demo users only - no passwords."""

USERS = {
    "alice": {"tenant": "tenantA", "role": "user"},
    "bob": {"tenant": "tenantB", "role": "user"},
    "carol": {"tenant": "tenantC", "role": "user"},
    "admin": {"tenant": None, "role": "admin"},
}

AUDIT_LOG = []


class AccessDenied(Exception):
    pass


def login(username):
    """Return a user dict (with name) or None."""
    info = USERS.get(username)
    if info is None:
        return None
    return {"name": username, **info}


def can_access(user, tenant):
    return user["role"] == "admin" or user["tenant"] == tenant


def log_access(user, action, target, allowed):
    AUDIT_LOG.append({"user": user["name"], "tenant": user["tenant"],
                      "action": action, "target": target,
                      "result": "ALLOWED" if allowed else "DENIED"})
