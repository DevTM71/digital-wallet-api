"""Eventos de domínio da carteira digital.

Os eventos são a única fonte de verdade do sistema (Event Sourcing): todo
estado é reconstruído aplicando-os em ordem. Por isso são imutáveis
(dataclasses congeladas) e carregam os metadados necessários para
persistência e replay: ``aggregate_id``, ``version``, ``event_id`` e
``occurred_at``.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, ClassVar


def _agora_utc() -> datetime:
    """Retorna o instante atual em UTC."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Evento de domínio base, com os metadados comuns a todos os eventos."""

    event_type: ClassVar[str]

    aggregate_id: str
    version: int
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=_agora_utc)

    def payload(self) -> dict[str, Any]:
        """Dados específicos do evento, prontos para serialização."""
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class WalletOpened(DomainEvent):
    """Uma nova carteira foi aberta para um titular."""

    event_type: ClassVar[str] = "WalletOpened"

    owner_name: str

    def payload(self) -> dict[str, Any]:
        return {"owner_name": self.owner_name}


@dataclass(frozen=True, kw_only=True)
class FundsDeposited(DomainEvent):
    """Fundos foram depositados na carteira."""

    event_type: ClassVar[str] = "FundsDeposited"

    amount: Decimal
    description: str

    def payload(self) -> dict[str, Any]:
        return {"amount": str(self.amount), "description": self.description}


@dataclass(frozen=True, kw_only=True)
class FundsWithdrawn(DomainEvent):
    """Fundos foram sacados da carteira."""

    event_type: ClassVar[str] = "FundsWithdrawn"

    amount: Decimal
    description: str

    def payload(self) -> dict[str, Any]:
        return {"amount": str(self.amount), "description": self.description}


EVENT_REGISTRY: dict[str, type[DomainEvent]] = {
    WalletOpened.event_type: WalletOpened,
    FundsDeposited.event_type: FundsDeposited,
    FundsWithdrawn.event_type: FundsWithdrawn,
}
