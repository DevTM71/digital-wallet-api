"""Exceções de domínio da carteira digital.

Todas as exceções de negócio herdam de ``DomainError``, permitindo que as
camadas externas capturem falhas de domínio de forma uniforme.
"""


class DomainError(Exception):
    """Erro base para todas as violações de regras de domínio."""


class InvalidAmountError(DomainError):
    """Valor monetário inválido (não positivo ou não numérico)."""


class InsufficientFundsError(DomainError):
    """Saque solicitado excede o saldo disponível na carteira."""


class WalletNotFoundError(DomainError):
    """Nenhuma carteira encontrada para o identificador informado."""


class ConcurrencyError(DomainError):
    """Conflito de concorrência: a versão esperada do agregado está desatualizada."""
