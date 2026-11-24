"""Structural eligibility only. Semantic classification belongs to the shared n8n core.

This module must never block a message because its text does not match a
channel-specific greeting/product regex. Account authorization, handoff,
messaging window, claim and idempotency are enforced by the Central server.
"""
def prepare_decision(event):
    if not isinstance(event, dict):
        return {"action": "reject", "maySend": False, "mayCallGemini": False}
    keys = ("channel", "accountId", "senderId", "messageId", "messageText",
            "handoffState", "claimToken")
    if not all(isinstance(event.get(key), str) and event[key].strip() for key in keys):
        return {"action": "reject", "maySend": False, "mayCallGemini": False}
    if event["channel"] != "instagram" or event["accountId"] == event["senderId"]:
        return {"action": "reject", "maySend": False, "mayCallGemini": False}
    if event["handoffState"] != "bot":
        return {"action": "hold_for_human", "maySend": False, "mayCallGemini": False}
    text = event["messageText"].strip()
    if not 1 <= len(text) <= 2000:
        return {"action": "reject", "maySend": False, "mayCallGemini": False}
    # Any structurally valid text may enter the shared conversation core.
    # The core, not this channel adapter, classifies the user's intent.
    return {"action": "auto", "maySend": False, "mayCallGemini": True}
