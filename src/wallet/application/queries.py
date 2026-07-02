"""Queries do lado de leitura (CQRS): estado derivado do fluxo de eventos.

Aqui está o benefício central do Event Sourcing: o extrato da carteira é
derivado diretamente do fluxo de eventos, na ordem em que aconteceram —
auditoria completa de cada movimentação sem nenhuma tabela adicional de
histórico. O lado de leitura consome o ``EventStore`` diretamente, sem
passar pelo repositório de escrita.
"""

from decimal import Decimal
from typing import Any

from wallet.domain.aggregate import Wallet
from wallet.domain.events import DomainEvent, FundsDeposited, FundsWithdrawn, WalletOpened
from wallet.domain.exceptions import WalletNotFoundError
from wallet.infrastructure.event_store import EventStore


def _duas_casas(valor: Decimal) -> str:
    """Formata a quantia como string com exatamente 2 casas decimais."""
    return f"{valor:.2f}"


class WalletQueryService:
    """Responde consultas reconstruindo o estado a partir dos eventos."""

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def _carregar_eventos(self, wallet_id: str) -> list[DomainEvent]:
        eventos = self._event_store.load(wallet_id)
        if not eventos:
            raise WalletNotFoundError(f"Carteira não encontrada: {wallet_id}")
        return eventos

    def get_wallet(self, wallet_id: str) -> dict[str, Any]:
        """Retorna o estado atual da carteira, derivado por replay dos eventos."""
        carteira = Wallet.load_from_history(self._carregar_eventos(wallet_id))
        return {
            "id": carteira.id,
            "owner_name": carteira.owner_name,
            "balance": _duas_casas(carteira.balance),
            "version": carteira.version,
        }

    def get_statement(self, wallet_id: str) -> list[dict[str, Any]]:
        """Retorna o extrato: uma entrada por evento, com saldo acumulado.

        Cada linha traz o saldo após o evento (``balance_after``), calculado
        durante a própria travessia do histórico — o extrato inteiro é uma
        projeção do fluxo de eventos.
        """
        extrato: list[dict[str, Any]] = []
        saldo = Decimal("0.00")

        for evento in self._carregar_eventos(wallet_id):
            if isinstance(evento, WalletOpened):
                tipo = "abertura"
                quantia = Decimal("0.00")
                descricao = f"Carteira aberta para {evento.owner_name}"
            elif isinstance(evento, FundsDeposited):
                tipo = "deposito"
                quantia = evento.amount
                saldo += quantia
                descricao = evento.description or "Depósito"
            elif isinstance(evento, FundsWithdrawn):
                tipo = "saque"
                quantia = evento.amount
                saldo -= quantia
                descricao = evento.description or "Saque"
            else:
                raise ValueError(f"Evento não suportado no extrato: {type(evento).__name__}")

            extrato.append(
                {
                    "type": tipo,
                    "amount": _duas_casas(quantia),
                    "balance_after": _duas_casas(saldo),
                    "description": descricao,
                    "occurred_at": evento.occurred_at.isoformat(),
                }
            )

        return extrato
