"""Event Store: persistência append-only dos eventos de domínio.

Única forma de escrita é o ``append``; não existe UPDATE nem DELETE. A
restrição de unicidade ``(aggregate_id, version)`` implementa a concorrência
otimista: se duas transações tentarem gravar a mesma versão do mesmo
agregado, a segunda viola a restrição e falha com ``ConcurrencyError``.

A serialização é responsabilidade exclusiva deste módulo: ``Decimal`` vira
string no JSON gravado e volta a ser ``Decimal`` na leitura, mantendo o
domínio intocado por preocupações de persistência.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence, get_type_hints

from sqlalchemy import DateTime, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from wallet.domain.events import EVENT_REGISTRY, DomainEvent
from wallet.domain.exceptions import ConcurrencyError

_URL_PADRAO = "sqlite:///./wallet_events.db"
_URLS_SQLITE_MEMORIA = ("sqlite://", "sqlite:///:memory:")


class Base(DeclarativeBase):
    """Base declarativa dos modelos de persistência."""


class EventRecord(Base):
    """Linha da tabela ``events``: um evento de domínio serializado."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "version", name="uq_events_aggregate_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _serializar_payload(evento: DomainEvent) -> str:
    """Serializa o payload do evento em JSON, convertendo ``Decimal`` em string."""
    return json.dumps(evento.payload(), ensure_ascii=False, default=str)


def _desserializar_payload(
    classe_evento: type[DomainEvent], payload: dict[str, Any]
) -> dict[str, Any]:
    """Converte de volta para ``Decimal`` os campos tipados como ``Decimal`` no evento."""
    tipos = get_type_hints(classe_evento)
    return {
        chave: Decimal(valor) if tipos.get(chave) is Decimal else valor
        for chave, valor in payload.items()
    }


def _evento_para_registro(evento: DomainEvent) -> EventRecord:
    """Mapeia um evento de domínio para a linha da tabela ``events``."""
    return EventRecord(
        event_id=str(evento.event_id),
        aggregate_id=evento.aggregate_id,
        version=evento.version,
        event_type=evento.event_type,
        payload=_serializar_payload(evento),
        occurred_at=evento.occurred_at,
    )


def _registro_para_evento(registro: EventRecord) -> DomainEvent:
    """Reconstrói o evento de domínio a partir da linha, via ``EVENT_REGISTRY``."""
    classe_evento = EVENT_REGISTRY.get(registro.event_type)
    if classe_evento is None:
        raise ValueError(f"Tipo de evento desconhecido no event store: {registro.event_type}")

    occurred_at = registro.occurred_at
    if occurred_at.tzinfo is None:
        # SQLite não preserva o fuso horário; os eventos são sempre gravados em UTC
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    payload = _desserializar_payload(classe_evento, json.loads(registro.payload))
    return classe_evento(
        aggregate_id=registro.aggregate_id,
        version=registro.version,
        event_id=uuid.UUID(registro.event_id),
        occurred_at=occurred_at,
        **payload,
    )


class EventStore:
    """Armazém append-only de eventos com controle de concorrência otimista."""

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or os.environ.get("DATABASE_URL", _URL_PADRAO)

        argumentos: dict[str, Any] = {}
        if url.startswith("sqlite"):
            argumentos["connect_args"] = {"check_same_thread": False}
            if url in _URLS_SQLITE_MEMORIA:
                # Sem StaticPool, cada conexão nova ao SQLite em memória
                # enxergaria um banco vazio recém-criado
                argumentos["poolclass"] = StaticPool

        self._engine = create_engine(url, **argumentos)
        Base.metadata.create_all(self._engine)

    def append(self, events: Sequence[DomainEvent]) -> None:
        """Grava os eventos numa única transação, em ordem.

        Levanta ``ConcurrencyError`` se alguma ``(aggregate_id, version)``
        já existir — sinal de que outra transação salvou o agregado antes.
        """
        if not events:
            return

        registros = [_evento_para_registro(evento) for evento in events]
        with Session(self._engine) as sessao:
            try:
                sessao.add_all(registros)
                sessao.commit()
            except IntegrityError as erro:
                sessao.rollback()
                raise ConcurrencyError(
                    "Conflito de concorrência ao gravar eventos: a versão do "
                    "agregado já foi persistida por outra transação."
                ) from erro

    def load(self, aggregate_id: str) -> list[DomainEvent]:
        """Carrega os eventos do agregado ordenados por versão, prontos para replay."""
        consulta = (
            select(EventRecord)
            .where(EventRecord.aggregate_id == aggregate_id)
            .order_by(EventRecord.version)
        )
        with Session(self._engine) as sessao:
            registros = sessao.scalars(consulta).all()
        return [_registro_para_evento(registro) for registro in registros]
