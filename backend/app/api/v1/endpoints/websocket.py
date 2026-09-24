"""WebSocket API endpoints (Phase 15).

Real-time experiment execution events via WebSocket.

Endpoint: GET /api/v1/experiments/{experiment_id}/ws

Client protocol:
- Connect: WebSocket handshake with experiment_id in path
- Subscribe: {"type": "subscribe", "experiment_id": "uuid"} (optional, path is primary)
- Unsubscribe: {"type": "unsubscribe"} (closes connection)
- Ping: {"type": "ping"} -> {"type": "pong"}

Server messages:
- Event: {"type": "event", "event": {...}}
- Ack: {"type": "ack", "message": "..."}
- Error: {"type": "error", "message": "..."}
- Pong: {"type": "pong"}

Event types (see app.schemas.websocket):
- experiment.started, experiment.completed, experiment.failed
- agent.started, agent.completed, agent.failed
- verification.started, verification.completed
- ml.started, ml.completed

Authentication: token via query param ?token= or Authorization header.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, get_current_user_ws
from app.models.experiment import Experiment
from app.repositories.experiment_repository import ExperimentRepository
from app.services.event_publisher import get_event_publisher
from app.services.websocket_manager import get_connection_manager
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter()
logger = logging.getLogger("autosage.websocket")


@router.websocket("/experiments/{experiment_id}/ws")
async def experiment_websocket(
    websocket: WebSocket,
    experiment_id: UUID,
    token: str = Query(default=None),
    session: AsyncSession = Depends(DbSession),
) -> None:
    """WebSocket endpoint for real-time experiment events.

    Authentication via query param `token` (for browser EventSource compatibility)
    or Authorization header. Falls back to cookie/session if configured.
    """
    # Authenticate the user
    user = None
    try:
        user = await get_current_user_ws(token, session)
    except Exception as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        logger.warning("ws_auth_failed", extra={"experiment_id": str(experiment_id), "error": str(exc)})
        return

    # Verify experiment exists and user has access
    repo = ExperimentRepository(session)
    experiment = await repo.get_by_id(experiment_id)
    if experiment is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Experiment not found")
        return

    if experiment.workspace_id not in [ws.id for ws in user.workspaces]:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
        return

    # Connect to the experiment channel
    manager = get_connection_manager()
    connection_id = await manager.connect(websocket, experiment_id)

    # Send initial ack
    from app.schemas.websocket import ServerMessage
    await websocket.send_text(
        ServerMessage(
            type="ack",
            message=f"Connected to experiment {experiment_id}",
            request_id=connection_id,
        ).model_dump_json()
    )

    logger.info(
        "ws_experiment_connected",
        extra={
            "experiment_id": str(experiment_id),
            "user_id": str(user.id),
            "connection_id": connection_id,
        },
    )

    try:
        while True:
            # Wait for client messages (subscribe/unsubscribe/ping)
            raw_message = await websocket.receive_text()

            response = await manager.handle_client_message(connection_id, raw_message)
            if response:
                await websocket.send_text(response.model_dump_json())

    except WebSocketDisconnect:
        logger.info("ws_client_disconnect", extra={"connection_id": connection_id})
    except Exception as exc:
        logger.exception("ws_error", extra={"connection_id": connection_id, "error": str(exc)})
    finally:
        await manager.disconnect(connection_id)


@router.websocket("/ws")
async def websocket_root(
    websocket: WebSocket,
    token: str = Query(default=None),
    session: AsyncSession = Depends(DbSession),
) -> None:
    """Root WebSocket endpoint — client must send subscribe message with experiment_id.

    Useful for clients that want a single persistent connection and switch experiments.
    """
    user = None
    try:
        user = await get_current_user_ws(token, session)
    except Exception as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        logger.warning("ws_root_auth_failed", extra={"error": str(exc)})
        return

    manager = get_connection_manager()
    connection_id = str(__import__("uuid").uuid4())

    # Accept but don't subscribe yet — wait for subscribe message
    await websocket.accept()

    # Register connection without experiment (will be set on subscribe)
    async with manager._lock:
        manager._connection_experiment[connection_id] = None  # type: ignore

    await websocket.send_text(
        ServerMessage(
            type="ack",
            message="Connected. Send {'type': 'subscribe', 'experiment_id': '...'} to join an experiment.",
            request_id=connection_id,
        ).model_dump_json()
    )

    logger.info("ws_root_connected", extra={"user_id": str(user.id), "connection_id": connection_id})

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                from app.schemas.websocket import ClientMessage
                msg = ClientMessage.model_validate_json(raw_message)
            except Exception as exc:
                await websocket.send_text(
                    ServerMessage(type="error", message=f"Invalid message: {exc}").model_dump_json()
                )
                continue

            if msg.type == "subscribe":
                if not msg.experiment_id:
                    await websocket.send_text(
                        ServerMessage(type="error", message="subscribe requires experiment_id").model_dump_json()
                    )
                    continue

                # Verify access
                repo = ExperimentRepository(session)
                experiment = await repo.get_by_id(msg.experiment_id)
                if experiment is None:
                    await websocket.send_text(
                        ServerMessage(type="error", message="Experiment not found").model_dump_json()
                    )
                    continue

                if experiment.workspace_id not in [ws.id for ws in user.workspaces]:
                    await websocket.send_text(
                        ServerMessage(type="error", message="Forbidden").model_dump_json()
                    )
                    continue

                # Switch channel
                await manager._switch_channel(connection_id, msg.experiment_id)
                await websocket.send_text(
                    ServerMessage(type="ack", message=f"Subscribed to experiment {msg.experiment_id}").model_dump_json()
                )

            elif msg.type == "unsubscribe":
                await manager.disconnect(connection_id)
                await websocket.send_text(ServerMessage(type="ack", message="Unsubscribed").model_dump_json())
                # Stay connected at root — can subscribe again
                async with manager._lock:
                    manager._connection_experiment[connection_id] = None  # type: ignore

            elif msg.type == "ping":
                await websocket.send_text(ServerMessage(type="pong").model_dump_json())

    except WebSocketDisconnect:
        logger.info("ws_root_disconnect", extra={"connection_id": connection_id})
    except Exception as exc:
        logger.exception("ws_root_error", extra={"connection_id": connection_id, "error": str(exc)})
    finally:
        await manager.disconnect(connection_id)