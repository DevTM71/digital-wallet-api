"""Handlers de comandos: orquestração entre domínio e persistência.

Esta camada NÃO contém regra de negócio — as regras (saldo suficiente,
quantia positiva etc.) vivem no agregado e nos value objects. O papel do
handler é apenas coordenar o fluxo: carregar o agregado → executar o
comportamento de domínio → salvar os eventos resultantes.
"""

from decimal import Decimal, InvalidOperation

from wallet.application.commands import DepositFunds, OpenWallet, WithdrawFunds
from wallet.domain.aggregate import Wallet
from wallet.domain.exceptions import InvalidAmountError
from wallet.domain.value_objects import Money
from wallet.infrastructure.repository import WalletRepository


def _converter_para_money(valor: str) -> Money:
    """Converte a quantia recebida como string para o value object do domínio.

    Falhas de conversão são relançadas como ``InvalidAmountError`` para que a
    API trate qualquer quantia inválida (não numérica ou <= 0) uniformemente.
    """
    try:
        return Money(Decimal(valor))
    except InvalidOperation as erro:
        raise InvalidAmountError(f"Quantia inválida: {valor!r}") from erro


class WalletCommandHandler:
    """Executa os comandos de escrita coordenando agregado e repositório."""

    def __init__(self, repository: WalletRepository) -> None:
        self._repository = repository

    def handle_open(self, command: OpenWallet) -> str:
        """Abre uma nova carteira e retorna o identificador gerado."""
        carteira = Wallet.open(command.owner_name)
        assert carteira.id is not None
        self._repository.save(carteira)
        return carteira.id

    def handle_deposit(self, command: DepositFunds) -> None:
        """Deposita fundos na carteira indicada pelo comando."""
        carteira = self._repository.get(command.wallet_id)
        carteira.deposit(_converter_para_money(command.amount), command.description)
        self._repository.save(carteira)

    def handle_withdraw(self, command: WithdrawFunds) -> None:
        """Saca fundos da carteira indicada pelo comando."""
        carteira = self._repository.get(command.wallet_id)
        carteira.withdraw(_converter_para_money(command.amount), command.description)
        self._repository.save(carteira)
