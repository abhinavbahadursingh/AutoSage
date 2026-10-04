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

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_current_user_ws
from app.models.experiment import Experiment
from app.models.workspace import Workspace
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
    session: DbSession,
    token: str = Query(default=None),
) -> None:
    """WebSocket endpoint for real-time experiment events.

    Authentication via query param `token` (for browser EventSource compatibility)
    or Authorization header. Falls back to cookie/session if configured.
    """
    # Accept first so auth/workspace failures surface as a WS close (1008),
    # not an HTTP 403 handshake rejection (browsers report that as "failed").
    await websocket.accept()

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

    # Explicit workspace query: relationships are lazy now, and the
    # pooled connection is released below before the socket loop.
    ws_rows = await session.execute(
        select(Workspace.id).where(Workspace.owner_id == user.id)
    )
    user_workspace_ids = set(ws_rows.scalars().all())
    if experiment.workspace_id not in user_workspace_ids:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
        return

    # Release the pooled DB connection BEFORE entering the long-lived
    # receive loop below. Holding DbSession for the socket lifetime pins one
    # pool connection per open tab (pool_size=5) and leaks it on unclean
    # disconnects (closed tab, sleep, HMR reload), starving every DB-backed
    # request — including future WS handshakes. The loop needs no DB
    # (manager is in-memory), so close eagerly; the dependency's own
    # finally-close is idempotent and remains as a safety net.
    user_id = user.id
    await session.close()

    # Connect to the experiment channel (already accepted above)
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
            "user_id": str(user_id),
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
    session: DbSession,
    token: str = Query(default=None),
) -> None:
    """Root WebSocket endpoint — client must send subscribe message with experiment_id.

    Useful for clients that want a single persistent connection and switch experiments.
    """
    await websocket.accept()

    user = None
    try:
        user = await get_current_user_ws(token, session)
    except Exception as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        logger.warning("ws_root_auth_failed", extra={"error": str(exc)})
        return

    # Same as above: release the pooled connection now — auth is done and
    # the socket loop below is pure in-memory. Capture what the subscribe
    # handler needs first (lazy relationships can't load after close).
    from uuid import uuid4 as _uuid4

    ws_rows = await session.execute(
        select(Workspace.id).where(Workspace.owner_id == user.id)
    )
    workspace_ids = list(ws_rows.scalars().all())
    user_id = user.id
    await session.close()

    manager = get_connection_manager()
    connection_id = str(_uuid4())

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

    logger.info("ws_root_connected", extra={"user_id": str(user_id), "connection_id": connection_id})

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

                # Verify access with a fresh short-lived session: the
                # endpoint-level session was closed after auth (see above)
                # so a subscribe never pins a pooled connection.
                from app.db import session as _db_session

                _db_session.init_engine()
                assert _db_session.AsyncSessionLocal is not None
                async with _db_session.AsyncSessionLocal() as sub_session:
                    repo = ExperimentRepository(sub_session)
                    experiment = await repo.get_by_id(msg.experiment_id)
                if experiment is None:
                    await websocket.send_text(
                        ServerMessage(type="error", message="Experiment not found").model_dump_json()
                    )
                    continue

                if experiment.workspace_id not in workspace_ids:
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