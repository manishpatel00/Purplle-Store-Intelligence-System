# PROMPT:
# Generate tests for app/websocket.py (ConnectionManager) covering:
#   1. connect registers client and calls accept
#   2. disconnect removes client from active list
#   3. broadcast sends message to all connected clients
#   4. broadcast with no clients does not raise
#   5. broadcast after one client disconnects still reaches remaining clients
#   6. broadcast handles send failure gracefully (removes broken client)
# CHANGES MADE: Used MockWebSocket class matching the ConnectionManager's
#   interface. broadcast sends dict (send_json), not string. Added error case.

import pytest

from app.websocket import ConnectionManager


class MockWebSocket:
    """Mock WebSocket that records all sent messages."""

    def __init__(self, *, should_fail: bool = False):
        self.sent: list = []
        self.accepted: bool = False
        self._should_fail = should_fail

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        if self._should_fail:
            raise ConnectionError("client disconnected")
        self.sent.append(data)

    async def send_text(self, data: str):
        if self._should_fail:
            raise ConnectionError("client disconnected")
        self.sent.append(data)


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect_registers_and_accepts(manager):
    ws = MockWebSocket()
    await manager.connect(ws)
    assert ws.accepted is True
    assert ws in manager.active_connections
    assert len(manager.active_connections) == 1


@pytest.mark.asyncio
async def test_disconnect_removes_client(manager):
    ws = MockWebSocket()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager.active_connections
    assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_disconnect_nonexistent_client_no_error(manager):
    ws = MockWebSocket()
    manager.disconnect(ws)  # should not raise


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(manager):
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)
    msg = {"type": "new_event", "store_id": "ST1008"}
    await manager.broadcast(msg)
    assert len(ws1.sent) == 1
    assert ws1.sent[0] == msg
    assert len(ws2.sent) == 1
    assert ws2.sent[0] == msg


@pytest.mark.asyncio
async def test_broadcast_with_no_clients_no_error(manager):
    await manager.broadcast({"type": "test"})  # should not raise


@pytest.mark.asyncio
async def test_broadcast_after_disconnect_reaches_remaining(manager):
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)
    manager.disconnect(ws1)
    await manager.broadcast({"type": "test"})
    assert len(ws1.sent) == 0  # disconnected — no message
    assert len(ws2.sent) == 1  # still connected


@pytest.mark.asyncio
async def test_broadcast_removes_broken_client(manager):
    ws_good = MockWebSocket()
    ws_bad = MockWebSocket(should_fail=True)
    await manager.connect(ws_good)
    await manager.connect(ws_bad)
    await manager.broadcast({"type": "test"})
    # Good client received the message
    assert len(ws_good.sent) == 1
    # Bad client was removed after error
    assert ws_bad not in manager.active_connections
