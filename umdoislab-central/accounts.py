"""Identidade interna e contexto imutável; não provisiona contas por HTTP."""
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from collections.abc import Mapping
import hmac
import re
import threading

DEFAULT_ACCOUNT_ID = "acct_001"
CHOICE_PROMPT = ("Ainda não conseguimos iniciar o atendimento pessoal. "
                 "Você prefere aguardar ou quer continuar com o atendimento automático? "
                 "Responda 1 para aguardar ou 2 para continuar.")
HUMAN_OFFER_PROMPT = "Quer que eu encaminhe sua dúvida para um atendente? Responda SIM ou NÃO."
HANDOFF_PROMPT = ("Não consegui resolver sua solicitação agora. "
                  "Vou encaminhar seu atendimento para uma pessoa da Umdoislab. "
                  "Assim que possível, alguém entra em contato. 😊")


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", value) is not None


def database_path(base, account_id):
    """Caminho gerado internamente; nunca aceitar caminho enviado pelo cliente."""
    if not valid_id(account_id):
        raise ValueError("Identidade de conta inválida")
    base = Path(base).resolve()
    path = base / "central.sqlite3" if account_id == DEFAULT_ACCOUNT_ID else base / "accounts" / account_id / "central.sqlite3"
    if path.resolve() != path or not path.resolve().is_relative_to(base):
        raise ValueError("Diretório de conta inválido")
    return path


@dataclass(frozen=True)
class Account:
    account_id: str
    instance: str
    display_name: str
    business_id: str
    database: Path = field(repr=False)
    config: Mapping = field(repr=False)
    enabled: bool = True
    lock: object = field(default_factory=threading.RLock, repr=False, compare=False)

    def __post_init__(self):
        if (not valid_id(self.account_id) or not valid_id(self.business_id) or
                not isinstance(self.instance, str) or
                not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.instance) or
                type(self.enabled) is not bool):
            raise ValueError("Registro de conta inválido")
        cfg = dict(self.config)
        if cfg.get("evolution_instance", self.instance) != self.instance:
            raise ValueError("Instância incompatível com a conta")
        cfg["evolution_instance"] = self.instance
        object.__setattr__(self, "config", MappingProxyType(cfg))
        object.__setattr__(self, "database", Path(self.database))

    def authenticate(self, authorization, key="bridge_secret"):
        secret = self.config.get(key)
        return (isinstance(secret, str) and len(secret) >= 24 and
                isinstance(authorization, str) and authorization.isascii() and
                hmac.compare_digest(authorization.encode(), ("Bearer " + secret).encode()))

    def public(self):
        return {"account_id": self.account_id, "display_name": self.display_name,
                "business_id": self.business_id, "instance": self.instance}

    def prompt(self, kind):
        defaults = {"choice": CHOICE_PROMPT, "handoff": HANDOFF_PROMPT,
                    "human_offer": HUMAN_OFFER_PROMPT}
        if kind == "handoff" and self.account_id != DEFAULT_ACCOUNT_ID:
            defaults[kind] = HANDOFF_PROMPT.replace("Umdoislab", self.display_name)
        return self.config.get("prompt_" + kind, defaults[kind])


class AccountRegistry:
    """Registro validado, somente leitura. Segredos e bancos não podem ser comuns."""
    def __init__(self, accounts):
        by_id, by_instance, databases, credentials = {}, {}, set(), set()
        for account in accounts:
            path = account.database.resolve()
            if (account.account_id in by_id or account.instance in by_instance or path in databases):
                raise ValueError("Identidade, instância ou banco duplicado")
            for key in ("bridge_secret", "evolution_webhook_secret"):
                secret = account.config.get(key)
                if secret:
                    if secret in credentials:
                        raise ValueError("Credencial de entrada reutilizada")
                    credentials.add(secret)
            by_id[account.account_id] = account
            by_instance[account.instance] = account
            databases.add(path)
        self.by_id = MappingProxyType(by_id)
        self.by_instance = MappingProxyType(by_instance)

    def resolve(self, *, account_id=None, instance=None):
        if account_id is not None and not valid_id(account_id):
            return None
        if instance is not None and not isinstance(instance, str):
            return None
        account = self.by_id.get(account_id) if account_id is not None else self.by_instance.get(instance)
        if not account or not account.enabled or (instance is not None and account.instance != instance):
            return None
        return account

    def available(self):
        return [a.public() for a in self.by_id.values() if a.enabled]


def require_database(db, account):
    """Impedir que um worker use contexto A com conexão de B."""
    if account is not None and getattr(db, "account", None) is not account:
        raise ValueError("Conexão incompatível com a conta")
