"""Reusable fake BLE client objects for integration tests."""

import asyncio
from collections.abc import Callable

from bleak.backends.device import BLEDevice
from gatt_link_ble import ConnectionMode, GattDeviceState, GattSensorData
from gatt_link_ble.const import (
    BATTERY_LEVEL_CHAR_UUID,
    HUMIDITY_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
    THINGY_GAS_CHAR_UUID,
)
from gatt_link_ble.exceptions import GattLinkError

DEFAULT_STATE = GattDeviceState(
    address="AA:BB:CC:DD:EE:FF",
    name="Thingy",
    sensors=GattSensorData(
        temperature=20.0,
        humidity=40.0,
        pressure=1000.0,
        eco2=500,
        tvoc=100,
        battery=90,
    ),
    supported_features=frozenset(
        {
            TEMPERATURE_CHAR_UUID,
            HUMIDITY_CHAR_UUID,
            PRESSURE_CHAR_UUID,
            THINGY_GAS_CHAR_UUID,
            BATTERY_LEVEL_CHAR_UUID,
        }
    ),
)


class FakeGattLinkClient:
    """Mock the BLE library client at the integration boundary."""

    def __init__(
        self,
        ble_device: BLEDevice | Callable[[], BLEDevice],
        mode: ConnectionMode,
        *,
        name: str | None = None,
        state_callback: Callable[[GattDeviceState], None] | None = None,
        disconnect_callback: Callable[[], None] | None = None,
        state: GattDeviceState,
        start_gate: asyncio.Event | None = None,
    ) -> None:
        """Create a mock client."""
        self.ble_device = ble_device() if callable(ble_device) else ble_device
        self.mode = mode
        self.name = name
        self.state_callback = state_callback
        self.disconnect_callback = disconnect_callback
        self.state = state
        self.start_gate = start_gate
        self.start_entered = asyncio.Event()
        self.poll_gate: asyncio.Event | None = None
        self.poll_entered = asyncio.Event()
        self.stop_gate: asyncio.Event | None = None
        self.stop_entered = asyncio.Event()
        self.active = False
        self.start_in_progress = False
        self.poll_in_progress = False
        self.stop_in_progress = False
        self.start_error: GattLinkError | None = None
        self.poll_error: GattLinkError | None = None
        self.start_calls = 0
        self.poll_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        """Simulate starting a push connection."""
        self.start_calls += 1
        self.start_entered.set()
        self.start_in_progress = True
        try:
            if self.start_gate is not None:
                await self.start_gate.wait()
            if self.start_error is not None:
                raise self.start_error
            self.active = True
            if self.state_callback is not None:
                self.state_callback(self.state)
        finally:
            self.start_in_progress = False

    async def poll(self) -> GattDeviceState:
        """Simulate one poll-and-disconnect cycle."""
        self.poll_calls += 1
        self.poll_entered.set()
        self.poll_in_progress = True
        self.active = True
        try:
            if self.poll_gate is not None:
                await self.poll_gate.wait()
            if self.poll_error is not None:
                raise self.poll_error
            return self.state
        finally:
            self.poll_in_progress = False
            self.active = False

    async def stop(self) -> None:
        """Simulate stopping the push connection."""
        self.stop_calls += 1
        self.stop_entered.set()
        self.stop_in_progress = True
        try:
            if self.stop_gate is not None:
                await self.stop_gate.wait()
            self.active = False
        finally:
            self.stop_in_progress = False

    def publish(self, state: GattDeviceState) -> None:
        """Simulate a library state callback."""
        self.state = state
        if self.state_callback is not None:
            self.state_callback(state)

    def disconnect(self) -> None:
        """Simulate a library disconnect callback."""
        if self.disconnect_callback is not None:
            self.disconnect_callback()


class FakeGattLinkClientFactory:
    """Factory recording mock BLE clients created by the integration."""

    def __init__(self) -> None:
        """Initialize the factory."""
        self.state = DEFAULT_STATE
        self.start_error: GattLinkError | None = None
        self.poll_error: GattLinkError | None = None
        self.start_gate: asyncio.Event | None = None
        self.poll_gate: asyncio.Event | None = None
        self.stop_gate: asyncio.Event | None = None
        self.client_created = asyncio.Event()
        self.clients: list[FakeGattLinkClient] = []

    def __call__(
        self,
        ble_device: BLEDevice | Callable[[], BLEDevice],
        mode: ConnectionMode,
        *,
        name: str | None = None,
        state_callback: Callable[[GattDeviceState], None] | None = None,
        disconnect_callback: Callable[[], None] | None = None,
    ) -> FakeGattLinkClient:
        """Create and record a mock client."""
        client = FakeGattLinkClient(
            ble_device,
            mode,
            name=name,
            state_callback=state_callback,
            disconnect_callback=disconnect_callback,
            state=self.state,
            start_gate=self.start_gate,
        )
        client.start_error = self.start_error
        client.poll_error = self.poll_error
        client.poll_gate = self.poll_gate
        client.stop_gate = self.stop_gate
        self.clients.append(client)
        self.client_created.set()
        return client

    @property
    def active_clients(self) -> tuple[FakeGattLinkClient, ...]:
        """Return clients with an active simulated BLE operation."""
        return tuple(client for client in self.clients if client.active)

    @property
    def outstanding_operations(self) -> int:
        """Return the number of client operations currently in progress."""
        return sum(
            client.start_in_progress + client.poll_in_progress + client.stop_in_progress
            for client in self.clients
        )
