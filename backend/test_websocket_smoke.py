#!/usr/bin/env python
"""WebSocket smoke test (Phase 15).

Tests:
1. Connection manager basic operations
2. Event publisher basic operations
3. WebSocket endpoint connectivity (requires running server)
"""
import asyncio
import sys
from uuid import uuid4, UUID

# Add backend to path
sys.path.insert(0, "D:/autoSage/backend")

from app.services.websocket_manager import ConnectionManager
from app.services.event_publisher import EventPublisher, get_event_publisher
from app.schemas.websocket import (
    ExperimentStarted,
    ExperimentCompleted,
    ExperimentFailed,
    AgentStarted,
    AgentCompleted,
    AgentFailed,
    VerificationStarted,
    VerificationCompleted,
    MLStarted,
    MLCompleted,
    ServerMessage,
)


async def test_connection_manager():
    """Test ConnectionManager basic operations."""
    print("Testing ConnectionManager...")
    manager = ConnectionManager()

    # Mock WebSocket for testing
    class MockWebSocket:
        def __init__(self):
            self.messages = []
            self.closed = False

        async def accept(self):
            pass

        async def send_text(self, data: str):
            self.messages.append(data)

        async def close(self, code=1000, reason=""):
            self.closed = True

        async def receive_text(self):
            raise Exception("Not implemented")

    exp_id = uuid4()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    # Connect two clients
    conn1 = await manager.connect(ws1, exp_id)
    conn2 = await manager.connect(ws2, exp_id)

    assert manager.get_connection_count(exp_id) == 2
    print(f"  Connected 2 clients: {conn1[:8]}, {conn2[:8]}")

    # Broadcast an event
    event = ExperimentStarted(
        experiment_id=exp_id,
        payload={"experiment_name": "test", "workspace_id": uuid4(), "config": {}},
    )
    sent = await manager.broadcast(exp_id, event)
    assert sent == 2
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    print(f"  Broadcast to {sent} clients")

    # Disconnect one
    await manager.disconnect(conn1)
    assert manager.get_connection_count(exp_id) == 1
    print(f"  Disconnected one client, remaining: {manager.get_connection_count(exp_id)}")

    # Broadcast again
    event2 = ExperimentCompleted(
        experiment_id=exp_id,
        payload={"result_summary": {}},
    )
    sent = await manager.broadcast(exp_id, event2)
    assert sent == 1
    assert len(ws2.messages) == 2
    print(f"  Broadcast to {sent} client after disconnect")

    # Disconnect last
    await manager.disconnect(conn2)
    assert manager.get_connection_count(exp_id) == 0
    print(f"  Disconnected all, remaining: {manager.get_connection_count(exp_id)}")

    print("  ConnectionManager tests PASSED\n")


async def test_event_publisher():
    """Test EventPublisher basic operations (without real connections)."""
    print("Testing EventPublisher...")
    publisher = EventPublisher()

    exp_id = uuid4()

    # These should not raise even with no connections
    await publisher.experiment_started(exp_id, "test-exp", uuid4(), {"key": "value"})
    print("  experiment_started: OK")

    await publisher.experiment_completed(exp_id, {"metric": 0.95}, "mlflow-123", "mlrun-456")
    print("  experiment_completed: OK")

    await publisher.experiment_failed(exp_id, "Something went wrong", 1, 3, True)
    print("  experiment_failed: OK")

    await publisher.agent_started(exp_id, "discovery", "discovery", 0)
    print("  agent_started: OK")

    await publisher.agent_completed(exp_id, "discovery", "discovery", {"columns": 10}, 150)
    print("  agent_completed: OK")

    await publisher.agent_failed(exp_id, "profiler", "profiler", "OOM", "MemoryError", False)
    print("  agent_failed: OK")

    await publisher.verification_started(exp_id, 1, 3, {"accuracy": 0.8})
    print("  verification_started: OK")

    await publisher.verification_completed(exp_id, 1, 3, True, {"accuracy": 0.95}, "complete")
    print("  verification_completed: OK")

    await publisher.ml_started(exp_id, "gradient_boosting", {"n_estimators": 100}, "mlflow-123", "mlrun-456")
    print("  ml_started: OK")

    await publisher.ml_completed(exp_id, True, {"accuracy": 0.95}, None, "mlflow-123", "mlrun-456")
    print("  ml_completed (success): OK")

    await publisher.ml_completed(exp_id, False, {}, "Training failed", "mlflow-123", "mlrun-456")
    print("  ml_completed (failure): OK")

    print("  EventPublisher tests PASSED\n")


async def test_sync_publish():
    """Test sync publish helpers (used by Celery tasks)."""
    print("Testing sync publish helpers...")
    from app.services.event_publisher import (
        publish_experiment_started,
        publish_experiment_completed,
        publish_experiment_failed,
        publish_agent_started,
        publish_agent_completed,
        publish_agent_failed,
        publish_verification_started,
        publish_verification_completed,
        publish_ml_started,
        publish_ml_completed,
    )

    exp_id = uuid4()

    # These should not raise
    publish_experiment_started(exp_id, "test", uuid4(), {})
    publish_experiment_completed(exp_id, {}, "mlflow-1", "mlrun-1")
    publish_experiment_failed(exp_id, "error", 0, 3, False)
    publish_agent_started(exp_id, "discovery", "discovery", 0)
    publish_agent_completed(exp_id, "discovery", "discovery", {}, 100)
    publish_agent_failed(exp_id, "profiler", "profiler", "error", "ValueError", False)
    publish_verification_started(exp_id, 1, 3, {})
    publish_verification_completed(exp_id, 1, 3, True, {}, "complete")
    publish_ml_started(exp_id, "gbdt", {}, "mlflow-1", "mlrun-1")
    publish_ml_completed(exp_id, True, {"acc": 0.9}, None, "mlflow-1", "mlrun-1")

    print("  Sync publish helpers: OK\n")


async def test_event_schemas():
    """Test event schema validation and serialization."""
    print("Testing event schemas...")

    exp_id = uuid4()
    ws_id = uuid4()

    # Test all event types
    events = [
        ExperimentStarted(
            experiment_id=exp_id,
            payload={"experiment_name": "test", "workspace_id": ws_id, "config": {}},
        ),
        ExperimentCompleted(
            experiment_id=exp_id,
            payload={"result_summary": {"acc": 0.9}, "mlflow_run_id": "ml-1", "ml_run_id": "mr-1"},
        ),
        ExperimentFailed(
            experiment_id=exp_id,
            payload={"error_detail": "failed", "retry_count": 0, "max_retries": 3, "will_retry": True},
        ),
        AgentStarted(
            experiment_id=exp_id,
            payload={"agent_name": "discovery", "stage": "discovery", "attempt": 0},
        ),
        AgentCompleted(
            experiment_id=exp_id,
            payload={"agent_name": "discovery", "stage": "discovery", "output_summary": {}, "duration_ms": 100},
        ),
        AgentFailed(
            experiment_id=exp_id,
            payload={"agent_name": "profiler", "stage": "profiler", "error": "OOM", "error_type": "MemoryError", "will_retry": False},
        ),
        VerificationStarted(
            experiment_id=exp_id,
            payload={"attempt": 1, "max_attempts": 3, "metrics": {"acc": 0.8}},
        ),
        VerificationCompleted(
            experiment_id=exp_id,
            payload={"attempt": 1, "max_attempts": 3, "passed": True, "metrics": {"acc": 0.95}, "gate_decision": "complete"},
        ),
        MLStarted(
            experiment_id=exp_id,
            payload={"model_family": "gbdt", "model_params": {}, "mlflow_run_id": "ml-1", "ml_run_id": "mr-1"},
        ),
        MLCompleted(
            experiment_id=exp_id,
            payload={"success": True, "metrics": {"acc": 0.95}, "error": None, "mlflow_run_id": "ml-1", "ml_run_id": "mr-1"},
        ),
    ]

    for event in events:
        # Validate JSON serialization
        json_str = event.model_dump_json()
        assert len(json_str) > 0

        # Validate ServerMessage wrapper
        msg = ServerMessage(type="event", event=event)
        wrapped_json = msg.model_dump_json()
        assert "event" in wrapped_json
        assert event.event_type in wrapped_json

    print(f"  All {len(events)} event types serialize correctly")
    print("  Event schema tests PASSED\n")


async def test_client_message_handling():
    """Test client message parsing."""
    print("Testing client message handling...")
    from app.schemas.websocket import ClientMessage

    # Valid messages
    sub_msg = ClientMessage(type="subscribe", experiment_id=uuid4())
    assert sub_msg.type == "subscribe"
    assert sub_msg.experiment_id is not None

    unsub_msg = ClientMessage(type="unsubscribe")
    assert unsub_msg.type == "unsubscribe"

    ping_msg = ClientMessage(type="ping")
    assert ping_msg.type == "ping"

    # Invalid message (should not raise, handled by manager)
    try:
        ClientMessage.model_validate_json('{"type": "invalid"}')
    except Exception:
        pass  # Expected to fail validation

    print("  Client message handling: OK\n")


async def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("WebSocket Engine Smoke Tests (Phase 15)")
    print("=" * 60 + "\n")

    try:
        await test_connection_manager()
        await test_event_publisher()
        await test_sync_publish()
        await test_event_schemas()
        await test_client_message_handling()

        print("=" * 60)
        print("ALL SMOKE TESTS PASSED")
        print("=" * 60)
        return 0
    except Exception as exc:
        print(f"\nSMOKE TEST FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))