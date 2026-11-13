"""Reusable fake BLE client objects for integration tests."""

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
    ) -> None:
        """Create a mock client."""
        self.ble_device = ble_device() if callable(ble_device) else ble_device
        self.mode = mode
        self.name = name
        self.state_callback = state_callback
        self.disconnect_callback = disconnect_callback
        self.state = state
        self.start_error: GattLinkError | None = None
        self.start_calls = 0
        self.poll_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        """Simulate starting a push connection."""
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error
        if self.state_callback is not None:
            self.state_callback(self.state)

    async def poll(self) -> GattDeviceState:
        """Simulate one poll-and-disconnect cycle."""
        self.poll_calls += 1
        return self.state

    async def stop(self) -> None:
        """Simulate stopping the push connection."""
        self.stop_calls += 1

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
        )
        client.start_error = self.start_error
        self.clients.append(client)
        return client
