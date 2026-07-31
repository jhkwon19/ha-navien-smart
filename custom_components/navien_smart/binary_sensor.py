"""Binary sensor platform for Navien Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NavienDevice
from .const import DOMAIN
from .coordinator import NavienSmartDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navien Smart binary sensor entities."""
    coordinator: NavienSmartDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NavienSmartErrorBinarySensor(coordinator, device)
        for device in coordinator.devices
        if device.modes
    )


class NavienSmartErrorBinarySensor(
    CoordinatorEntity[NavienSmartDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Problem sensor based on Navien room controller or ODU error code."""

    _attr_name = "오류 감지"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: NavienSmartDataUpdateCoordinator,
        device: NavienDevice,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device.id
        self._attr_unique_id = f"{device.id}_problem"

    @property
    def device(self) -> NavienDevice | None:
        """Return the latest device snapshot."""
        return self.coordinator.device_by_id(self._device_id)

    @property
    def is_on(self) -> bool | None:
        """Return true when the device reports an error."""
        device = self.device
        if device is None or device.error_code is None:
            return None
        return device.error_code != 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return error metadata."""
        device = self.device
        if device is None:
            return None
        attrs: dict[str, Any] = {
            "error_code": device.error_code,
            "error_text": device.error_text,
        }
        return {key: value for key, value in attrs.items() if value is not None} or None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device registry information."""
        if self.device is None:
            return None
        raw = self.device.raw or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            manufacturer="KyungDong Navien",
            name=self.device.name,
            model=str(raw.get("modelDisplayName") or raw.get("modelCode"))
            if raw.get("modelDisplayName") or raw.get("modelCode")
            else None,
            serial_number=str(raw.get("deviceId")) if raw.get("deviceId") else None,
        )
