"""Repositório do agregado Wallet, apoiado no Event Store."""

from wallet.domain.aggregate import Wallet
from wallet.domain.exceptions import WalletNotFoundError
from wallet.infrastructure.event_store import EventStore


class WalletRepository:
    """Repositório orientado a eventos — não é um repositório CRUD.

    Num repositório CRUD, salvar significa sobrescrever o registro atual
    (UPDATE) e carregar significa ler uma linha de estado. Aqui não existe
    UPDATE: ``save`` apenas **anexa** os eventos ainda não persistidos ao
    event store, e ``get`` **reconstrói** o agregado fazendo replay do
    histórico completo de eventos. O estado nunca é gravado — só derivado.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def get(self, wallet_id: str) -> Wallet:
        """Reconstrói a carteira por replay; lança ``WalletNotFoundError`` se não houver eventos."""
        eventos = self._event_store.load(wallet_id)
        if not eventos:
            raise WalletNotFoundError(f"Carteira não encontrada: {wallet_id}")
        return Wallet.load_from_history(eventos)

    def save(self, wallet: Wallet) -> None:
        """Anexa ao event store os eventos pendentes do agregado."""
        self._event_store.append(wallet.pull_uncommitted_events())
