"""Comandos do lado de escrita (CQRS): intenções de mudança de estado.

São apenas estruturas de dados imutáveis, sem comportamento. ``amount``
chega como string — é assim que virá do JSON da API — e a conversão para o
tipo do domínio acontece no handler, nunca aqui.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenWallet:
    """Intenção de abrir uma nova carteira para um titular."""

    owner_name: str


@dataclass(frozen=True)
class DepositFunds:
    """Intenção de depositar fundos numa carteira existente."""

    wallet_id: str
    amount: str
    description: str = ""


@dataclass(frozen=True)
class WithdrawFunds:
    """Intenção de sacar fundos de uma carteira existente."""

    wallet_id: str
    amount: str
    description: str = ""
