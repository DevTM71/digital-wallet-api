"""Agregado Wallet — raiz de agregação da carteira digital.

O agregado nunca persiste estado diretamente: cada comando valida as regras
de negócio e registra um evento de domínio. O estado em memória é sempre
derivado dos eventos, seja ao executar um comando, seja no replay do
histórico via ``load_from_history``.
"""

import uuid
from decimal import Decimal
from typing import Sequence

from wallet.domain.events import (
    DomainEvent,
    FundsDeposited,
    FundsWithdrawn,
    WalletOpened,
)
from wallet.domain.exceptions import InsufficientFundsError
from wallet.domain.value_objects import Money


class Wallet:
    """Carteira digital reconstruída a partir de seus eventos de domínio."""

    def __init__(self) -> None:
        self.id: str | None = None
        self.owner_name: str | None = None
        self.balance: Decimal = Decimal("0.00")
        self.version: int = 0
        self._uncommitted_events: list[DomainEvent] = []

    @classmethod
    def open(cls, owner_name: str) -> "Wallet":
        """Abre uma nova carteira, registrando o evento ``WalletOpened``."""
        carteira = cls()
        evento = WalletOpened(
            aggregate_id=str(uuid.uuid4()),
            version=1,
            owner_name=owner_name,
        )
        carteira._registrar(evento)
        return carteira

    def deposit(self, amount: Money, description: str = "") -> None:
        """Deposita fundos na carteira, registrando ``FundsDeposited``."""
        assert self.id is not None, "Carteira ainda não foi aberta."
        evento = FundsDeposited(
            aggregate_id=self.id,
            version=self.version + 1,
            amount=amount.amount,
            description=description,
        )
        self._registrar(evento)

    def withdraw(self, amount: Money, description: str = "") -> None:
        """Saca fundos da carteira, registrando ``FundsWithdrawn``.

        Levanta ``InsufficientFundsError`` se a quantia exceder o saldo.
        """
        assert self.id is not None, "Carteira ainda não foi aberta."
        if amount.amount > self.balance:
            raise InsufficientFundsError(
                f"Saldo insuficiente: saldo atual {self.balance:.2f}, "
                f"saque solicitado {amount.amount:.2f}."
            )
        evento = FundsWithdrawn(
            aggregate_id=self.id,
            version=self.version + 1,
            amount=amount.amount,
            description=description,
        )
        self._registrar(evento)

    @classmethod
    def load_from_history(cls, eventos: Sequence[DomainEvent]) -> "Wallet":
        """Reconstrói a carteira aplicando o histórico de eventos em ordem (replay)."""
        carteira = cls()
        for evento in eventos:
            carteira._apply(evento)
        return carteira

    def pull_uncommitted_events(self) -> list[DomainEvent]:
        """Retorna e limpa os eventos ainda não persistidos no event store."""
        eventos = list(self._uncommitted_events)
        self._uncommitted_events.clear()
        return eventos

    def _registrar(self, evento: DomainEvent) -> None:
        """Aplica o evento ao estado e o retém como pendente de persistência."""
        self._apply(evento)
        self._uncommitted_events.append(evento)

    def _apply(self, evento: DomainEvent) -> None:
        """Muta o estado da carteira a partir de um evento de domínio."""
        if isinstance(evento, WalletOpened):
            self.id = evento.aggregate_id
            self.owner_name = evento.owner_name
        elif isinstance(evento, FundsDeposited):
            self.balance += evento.amount
        elif isinstance(evento, FundsWithdrawn):
            self.balance -= evento.amount
        else:
            raise TypeError(f"Evento não suportado pelo agregado: {type(evento).__name__}")
        self.version = evento.version
