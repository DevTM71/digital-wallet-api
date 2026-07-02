"""Value Objects do domínio da carteira digital."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from wallet.domain.exceptions import InvalidAmountError

_DUAS_CASAS = Decimal("0.01")


@dataclass(frozen=True)
class Money:
    """Quantia monetária positiva, imutável e com precisão de 2 casas decimais.

    Representa valores de transação (depósito ou saque). Valores menores ou
    iguais a zero são rejeitados com ``InvalidAmountError``, pois nenhuma
    operação da carteira admite quantia nula ou negativa.
    """

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            quantizado = Decimal(self.amount).quantize(_DUAS_CASAS, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as erro:
            raise InvalidAmountError(f"Quantia inválida: {self.amount!r}") from erro

        if quantizado <= 0:
            raise InvalidAmountError("A quantia deve ser maior que zero.")

        # dataclass congelada: atribuição direta só é possível via object.__setattr__
        object.__setattr__(self, "amount", quantizado)

    def __str__(self) -> str:
        return f"{self.amount:.2f}"
