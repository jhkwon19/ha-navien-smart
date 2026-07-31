"""Button platform for Navien Smart."""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NavienDevice
from .const import DOMAIN
from .coordinator import NavienSmartDataUpdateCoordinator


FILTER_RESET_DESCRIPTION = ButtonEntityDescription(
    key="filter_reset",
    name="필터 초기화",
    icon="mdi:filter-sync",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navien Smart button entities."""
    coordinator: NavienSmartDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NavienSmartFilterResetButton(coordinator, device)
        for device in coordinator.devices
        if device.filters
    )


class NavienSmartFilterResetButton(
    CoordinatorEntity[NavienSmartDataUpdateCoordinator],
    ButtonEntity,
):
    """Reset filter usage counter."""

    entity_description = FILTER_RESET_DESCRIPTION

    def __init__(
        self,
        coordinator: NavienSmartDataUpdateCoordinator,
        device: NavienDevice,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device.id
        self._attr_unique_id = f"{device.id}_filter_reset"

    @property
    def device(self) -> NavienDevice | None:
        """Return the latest device snapshot."""
        return self.coordinator.device_by_id(self._device_id)

    @property
    def available(self) -> bool:
        """Return whether the reset command can be used."""
        raw = (self.device.raw if self.device else {}) or {}
        return self.device is not None and bool(raw.get("connected", True))

    async def async_press(self) -> None:
        """Reset the filter counter."""
        await self.coordinator.client.async_reset_filter(self._device_id)
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()

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
