"""Pure local triage rules. No network requests, no Meta credentials, no AI calls."""
import re

_GREETING = re.compile(r"^(?:oi+|ol[aá]+|opa|bom dia|boa tarde|boa noite)[\s!.?]*$", re.I)
_PRODUCT = re.compile(
    r"\b(?:pre[çc]o|valor|quanto|comprar|produto|cat[aá]logo|t[eê]m|dispon[ií]vel|"
    r"entrega|frete|link|modelo|tamanho|estoque)\b", re.I
)


def classify(message):
    """A greeting alone can never trigger a product offer."""
    if not isinstance(message, str):
        return "human_review"
    text = message.strip()
    if not text or len(text) > 2000:
        return "human_review"
    if _GREETING.fullmatch(text):
        return "greeting"
    if _PRODUCT.search(text):
        return "commercial_question"
    return "human_review"


def prepare_decision(event):
    """Return an inert decision; sending and Gemini access remain disabled."""
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
    return {"action": classify(event["messageText"]), "maySend": False,
            "mayCallGemini": False}
