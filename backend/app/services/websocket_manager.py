"""WebSocket connection manager (Phase 15).

Manages experiment-scoped WebSocket connections with:
- Per-experiment channels (multiple clients per experiment)
- Connection lifecycle (connect, disconnect, heartbeat)
- Reconnection-safe behavior (client can resume with same experiment_id)
- Graceful shutdown
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Dict, Optional, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from app.schemas.websocket import ClientMessage, ExperimentEvent, ServerMessage

logger = logging.getLogger("autosage.websocket")


class ConnectionManager:
    """Manages WebSocket connections grouped by experiment_id.

    Design:
    - Each experiment has a set of active WebSocket connections
    - Clients subscribe/unsubscribe via JSON messages
    - Events are broadcast to all connections for an experiment
    - Heartbeat (ping/pong) keeps idle connections alive
    - Reconnection: new connection with same experiment_id joins the channel
    """

    def __init__(self) -> None:
        # experiment_id -> set of (connection_id, WebSocket)
        self._channels: Dict[UUID, Dict[str, WebSocket]] = defaultdict(dict)
        # connection_id -> experiment_id (reverse lookup for cleanup)
        self._connection_experiment: Dict[str, UUID] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, experiment_id: UUID) -> str:
        """Accept a new WebSocket connection for an experiment.

        Returns a unique connection_id for this session.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())

        async with self._lock:
            self._channels[experiment_id][connection_id] = websocket
            self._connection_experiment[connection_id] = experiment_id

        logger.info(
            "ws_connected",
            extra={
                "connection_id": connection_id,
                "experiment_id": str(experiment_id),
                "channel_size": len(self._channels[experiment_id]),
            },
        )
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Remove a connection (client disconnect or server-initiated)."""
        async with self._lock:
            experiment_id = self._connection_experiment.pop(connection_id, None)
            if experiment_id is not None:
                self._channels[experiment_id].pop(connection_id, None)
                # Clean up empty channels
                if not self._channels[experiment_id]:
                    del self._channels[experiment_id]

        logger.info(
            "ws_disconnected",
            extra={
                "connection_id": connection_id,
                "experiment_id": str(experiment_id) if experiment_id else None,
            },
        )

    async def broadcast(self, experiment_id: UUID, event: ExperimentEvent) -> int:
        """Send an event to all connections subscribed to an experiment.

        Returns the number of connections that received the event.
        Dead connections are cleaned up automatically.
        """
        async with self._lock:
            connections = dict(self._channels.get(experiment_id, {}))

        if not connections:
            return 0

        message = ServerMessage(type="event", event=event)
        data = message.model_dump_json()

        sent = 0
        dead: Set[str] = set()

        for conn_id, ws in connections.items():
            try:
                await ws.send_text(data)
                sent += 1
            except Exception:
                dead.add(conn_id)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for conn_id in dead:
                    exp_id = self._connection_experiment.pop(conn_id, None)
                    if exp_id:
                        self._channels[exp_id].pop(conn_id, None)
                        if not self._channels[exp_id]:
                            del self._channels[exp_id]

        logger.debug(
            "ws_broadcast",
            extra={
                "experiment_id": str(experiment_id),
                "event_type": event.event_type,
                "sent": sent,
                "dead_cleaned": len(dead),
            },
        )
        return sent

    async def send_personal(
        self, connection_id: str, message: ServerMessage
    ) -> bool:
        """Send a message to a specific connection (ack, error, pong)."""
        async with self._lock:
            experiment_id = self._connection_experiment.get(connection_id)
            if not experiment_id:
                return False
            ws = self._channels[experiment_id].get(connection_id)

        if not ws:
            return False

        try:
            await ws.send_text(message.model_dump_json())
            return True
        except Exception:
            await self.disconnect(connection_id)
            return False

    async def handle_client_message(
        self, connection_id: str, raw_message: str
    ) -> Optional[ServerMessage]:
        """Process a client message (subscribe/unsubscribe/ping).

        Returns a ServerMessage to send back (ack/error/pong), or None.
        """
        try:
            msg = ClientMessage.model_validate_json(raw_message)
        except Exception as exc:
            return ServerMessage(
                type="error",
                message=f"Invalid message format: {exc}",
            )

        if msg.type == "ping":
            return ServerMessage(type="pong")

        if msg.type == "subscribe":
            if not msg.experiment_id:
                return ServerMessage(
                    type="error", message="subscribe requires experiment_id"
                )
            # Switch this connection to a new experiment channel
            await self._switch_channel(connection_id, msg.experiment_id)
            return ServerMessage(
                type="ack",
                message=f"Subscribed to experiment {msg.experiment_id}",
            )

        if msg.type == "unsubscribe":
            await self.disconnect(connection_id)
            return ServerMessage(
                type="ack", message="Unsubscribed and disconnected"
            )

        return ServerMessage(type="error", message=f"Unknown message type: {msg.type}")

    async def _switch_channel(self, connection_id: str, new_experiment_id: UUID) -> None:
        """Move a connection from its current experiment channel to a new one."""
        async with self._lock:
            old_experiment_id = self._connection_experiment.get(connection_id)
            if old_experiment_id:
                self._channels[old_experiment_id].pop(connection_id, None)
                if not self._channels[old_experiment_id]:
                    del self._channels[old_experiment_id]

            self._channels[new_experiment_id][connection_id] = (
                self._channels.get(old_experiment_id, {}).get(connection_id)
            )
            self._connection_experiment[connection_id] = new_experiment_id

    def get_connection_count(self, experiment_id: UUID) -> int:
        """Number of active connections for an experiment."""
        return len(self._channels.get(experiment_id, {}))

    def get_total_connections(self) -> int:
        """Total connections across all experiments."""
        return len(self._connection_experiment)

    async def shutdown(self) -> None:
        """Close all connections gracefully."""
        async with self._lock:
            all_connections = []
            for exp_conns in self._channels.values():
                all_connections.extend(exp_conns.values())
            self._channels.clear()
            self._connection_experiment.clear()

        for ws in all_connections:
            try:
                await ws.close(code=1001, reason="Server shutdown")
            except Exception:
                pass

        logger.info("ws_shutdown_complete")


# Global instance (singleton pattern for FastAPI lifespan)
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


async def close_connection_manager() -> None:
    """Shutdown the global connection manager."""
    global _manager
    if _manager is not None:
        await _manager.shutdown()
        _manager = None