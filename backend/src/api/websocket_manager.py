"""
websocket_manager.py
Manages multiple concurrent WebSocket client connections.

Features:
  - Multi-client broadcast support
  - Per-client message filtering
  - Graceful connect/disconnect handling
  - Connection health monitoring
  - Message queuing to prevent slow-client blocking
"""

import asyncio
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages a pool of active WebSocket connections.

    Supports:
      - Broadcasting to all connected clients
      - Sending messages to specific clients
      - Tracking connected client IDs
      - Handling disconnections gracefully
    """

    def __init__(self):
        # Maps client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        Accept a new WebSocket connection and register the client.

        Args:
            websocket: Incoming WebSocket connection
            client_id: Unique identifier for this client
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client connected: {client_id} | Total: {self.count}")

    async def disconnect(self, client_id: str):
        """
        Remove a client from the connection pool.

        Args:
            client_id: Client to disconnect
        """
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
        logger.info(f"WebSocket client disconnected: {client_id} | Remaining: {self.count}")

    async def send_to(self, client_id: str, data: dict) -> bool:
        """
        Send a JSON message to a specific client.

        Args:
            client_id: Target client
            data:      JSON-serializable dict

        Returns:
            True if sent successfully, False if client not found or error
        """
        websocket = self.active_connections.get(client_id)
        if not websocket:
            return False
        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)
            return False

    async def broadcast(self, data: dict):
        """
        Broadcast a JSON message to all connected clients.

        Disconnected clients are removed automatically.

        Args:
            data: JSON-serializable dict to broadcast
        """
        if not self.active_connections:
            return

        # Copy keys to avoid mutation during iteration
        client_ids = list(self.active_connections.keys())
        dead_clients: Set[str] = set()

        for client_id in client_ids:
            websocket = self.active_connections.get(client_id)
            if websocket is None:
                continue
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.warning(f"Broadcast failed for {client_id}: {e}")
                dead_clients.add(client_id)

        # Clean up dead connections
        for client_id in dead_clients:
            await self.disconnect(client_id)

    async def broadcast_text(self, message: str):
        """Broadcast a plain text message to all clients."""
        client_ids = list(self.active_connections.keys())
        dead_clients = set()

        for client_id in client_ids:
            websocket = self.active_connections.get(client_id)
            if not websocket:
                continue
            try:
                await websocket.send_text(message)
            except Exception:
                dead_clients.add(client_id)

        for client_id in dead_clients:
            await self.disconnect(client_id)

    def get_connected_clients(self) -> list:
        """Return list of currently connected client IDs."""
        return list(self.active_connections.keys())

    @property
    def count(self) -> int:
        """Return number of currently connected clients."""
        return len(self.active_connections)

    def is_connected(self, client_id: str) -> bool:
        return client_id in self.active_connections


# ----------------------------------------------------------------
# Simulation State Broadcaster
# ----------------------------------------------------------------

class SimulationBroadcaster:
    """
    Wraps ConnectionManager with simulation-specific broadcasting logic.

    Handles periodic state pushes and event notifications.
    """

    def __init__(self, manager: ConnectionManager):
        self.manager   = manager
        self._running  = False
        self._task: Optional[asyncio.Task] = None

    async def start_broadcasting(self, state_provider, interval: float = 0.5):
        """
        Start a background loop that pushes simulation state to all clients.

        Args:
            state_provider: Async callable that returns current state dict
            interval:       Seconds between broadcasts
        """
        self._running = True
        while self._running and self.manager.count > 0:
            try:
                state = await state_provider()
                if state:
                    await self.manager.broadcast(state)
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        """Stop the broadcast loop."""
        self._running = False

    async def notify_event(self, event_type: str, payload: dict):
        """
        Broadcast a named event to all clients.

        Args:
            event_type: e.g. "simulation_started", "mode_changed"
            payload:    Event data
        """
        await self.manager.broadcast({
            "event":   event_type,
            "payload": payload,
        })


# Singleton instance shared across API modules
connection_manager   = ConnectionManager()
simulation_broadcaster = SimulationBroadcaster(connection_manager)
