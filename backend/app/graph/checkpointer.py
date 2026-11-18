"""LangGraph checkpointer backed by the application database.

Stores serialized checkpoints in a small `graph_checkpoints` table, so
conversation research runs survive process restarts on PostgreSQL (and work
identically on SQLite in tests) — no extra infrastructure required.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Session

from app.database.connection import Base, SessionLocal
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

logger = logging.getLogger("shopmate.checkpoint")


class GraphCheckpointRow(Base):
    __tablename__ = "graph_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String(64), index=True, nullable=False)
    checkpoint_ns = Column(String(255), default="", nullable=False)
    checkpoint_id = Column(String(64), nullable=False, index=True)
    parent_checkpoint_id = Column(String(64), nullable=True)
    type = Column(String(16), nullable=False, default="checkpoint")
    checkpoint = Column(JSON, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    blob = Column(Text, nullable=True)  # serialized payload for write records
    channel_values = Column(JSON, nullable=True)
    versions_seen = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DatabaseCheckpointSaver(BaseCheckpointSaver):
    """Persistent checkpointer using the app's SQLAlchemy session factory."""

    def __init__(self, session_factory=None):
        super().__init__()
        self._session_factory = session_factory or SessionLocal
        self._ensured = False

    # --- helpers -----------------------------------------------------------
    def _session(self) -> Session:
        return self._session_factory()

    def _ensure_table(self) -> None:
        """Create the checkpoint table on first use (no-op when it exists)."""
        if self._ensured:
            return
        try:
            session = self._session()
            try:
                GraphCheckpointRow.__table__.create(bind=session.get_bind(),
                                                    checkfirst=True)
            finally:
                session.close()
        except Exception:
            logger.exception("checkpoint_table_ensure_failed")
        self._ensured = True

    # --- sync API ----------------------------------------------------------
    def put(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        thread_id = config["configurable"]["thread_id"]
        self._ensure_table()
        session = self._session()
        try:
            checkpoint = _json_safe(checkpoint)
            metadata = _json_safe(metadata)
            row = GraphCheckpointRow(
                thread_id=thread_id,
                checkpoint_ns=config["configurable"].get("checkpoint_ns", ""),
                checkpoint_id=checkpoint["id"],
                parent_checkpoint_id=checkpoint.get("parent_checkpoint_id"),
                type="checkpoint",
                checkpoint=checkpoint,
                metadata_=dict(metadata),
                channel_values=dict(checkpoint.get("channel_values") or {}),
                versions_seen=dict(checkpoint.get("versions_seen") or {}),
            )
            session.add(row)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("checkpoint_put_failed thread=%s", thread_id)
        finally:
            session.close()
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": config["configurable"].get("checkpoint_ns", ""),
                "checkpoint_id": checkpoint["id"],
            }
        }

    def put_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        channel_versions: dict[str, Any],
        parent_checkpoint_id: Optional[str] = None,
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        self._ensure_table()
        session = self._session()
        try:
            for channel, value in writes:
                serialised = _json_safe(value)
                session.add(GraphCheckpointRow(
                    thread_id=thread_id,
                    checkpoint_ns=config["configurable"].get("checkpoint_ns", ""),
                    checkpoint_id=parent_checkpoint_id or "writes",
                    type="write",
                    checkpoint={"channel": channel},
                    metadata_={"channel": channel},
                    blob=json.dumps(serialised),
                ))
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("checkpoint_put_writes_failed thread=%s", thread_id)
        finally:
            session.close()

    def get_tuple(self, config: dict[str, Any]) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")
        self._ensure_table()
        session = self._session()
        try:
            stmt = (
                select(GraphCheckpointRow)
                .where(
                    GraphCheckpointRow.thread_id == thread_id,
                    GraphCheckpointRow.checkpoint_ns
                    == config["configurable"].get("checkpoint_ns", ""),
                    GraphCheckpointRow.type == "checkpoint",
                )
                .order_by(GraphCheckpointRow.created_at.desc(), GraphCheckpointRow.id.desc())
            )
            if checkpoint_id:
                stmt = stmt.where(GraphCheckpointRow.checkpoint_id == checkpoint_id)
            row = session.scalars(stmt.limit(1)).first()
            if row is None:
                return None
            checkpoint = dict(row.checkpoint)
            checkpoint.setdefault("channel_values", row.channel_values or {})
            checkpoint.setdefault("versions_seen", row.versions_seen or {})
            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": row.checkpoint_ns,
                        "checkpoint_id": row.checkpoint_id,
                    }
                },
                checkpoint=checkpoint,
                metadata=CheckpointMetadata(**(row.metadata_ or {})),
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": row.checkpoint_ns,
                            "checkpoint_id": row.parent_checkpoint_id,
                        }
                    }
                    if row.parent_checkpoint_id
                    else None
                ),
            )
        finally:
            session.close()

    def list(
        self, config: Optional[dict[str, Any]] = None, *, limit: int = 10,
        before: Optional[dict[str, Any]] = None,
    ):
        thread_id = (config or {}).get("configurable", {}).get("thread_id")
        self._ensure_table()
        session = self._session()
        try:
            stmt = (
                select(GraphCheckpointRow)
                .where(GraphCheckpointRow.type == "checkpoint")
                .order_by(GraphCheckpointRow.created_at.desc(), GraphCheckpointRow.id.desc())
                .limit(limit)
            )
            if thread_id:
                stmt = stmt.where(GraphCheckpointRow.thread_id == thread_id)
            rows = session.scalars(stmt).all()
            for row in rows:
                checkpoint = dict(row.checkpoint)
                checkpoint.setdefault("channel_values", row.channel_values or {})
                yield CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": row.thread_id,
                            "checkpoint_ns": row.checkpoint_ns,
                            "checkpoint_id": row.checkpoint_id,
                        }
                    },
                    checkpoint=checkpoint,
                    metadata=CheckpointMetadata(**(row.metadata_ or {})),
                )
        finally:
            session.close()

    def delete_thread(self, thread_id: str) -> None:
        self._ensure_table()
        session = self._session()
        try:
            session.query(GraphCheckpointRow).filter(
                GraphCheckpointRow.thread_id == thread_id
            ).delete()
            session.commit()
        finally:
            session.close()

    # --- async API (FastAPI runs graph.ainvoke) ----------------------------
    async def aput(self, config, checkpoint, metadata, new_versions):
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, channel_versions, parent_checkpoint_id=None):
        return self.put_writes(config, writes, channel_versions, parent_checkpoint_id)

    async def aget_tuple(self, config):
        return self.get_tuple(config)

    def alist(self, config=None, *, limit=10, before=None):
        return self.list(config, limit=limit, before=before)


def _json_safe(value: Any) -> Any:
    """Coerce arbitrary channel values into JSON-serialisable structures."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Pydantic models (e.g. ProductOut) — serialise via their own machinery.
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


_saver: Optional[DatabaseCheckpointSaver] = None


def get_checkpointer() -> DatabaseCheckpointSaver:
    global _saver
    if _saver is None:
        _saver = DatabaseCheckpointSaver()
    return _saver
