"""Select platform for Navien Smart."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NRT530_AIR_MONITOR_MODEL_NAMES, NavienDevice, NavienFanOption, NavienMode
from .const import DOMAIN
from .coordinator import NavienSmartDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navien Smart select entities."""
    coordinator: NavienSmartDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []
    for device in coordinator.devices:
        if device.modes:
            entities.append(NavienSmartModeSelect(coordinator, device))
            entities.append(NavienSmartFanSelect(coordinator, device))
        if _has_air_monitor_led(device):
            entities.append(NavienSmartAirMonitorLedSelect(coordinator, device))
    async_add_entities(entities)


class NavienSmartSelectBase(
    CoordinatorEntity[NavienSmartDataUpdateCoordinator],
    SelectEntity,
):
    """Base select entity for Navien Smart."""

    def __init__(
        self,
        coordinator: NavienSmartDataUpdateCoordinator,
        device: NavienDevice,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device.id
        self._attr_unique_id = f"{device.id}_{key}"
        self._attr_name = name

    @property
    def device(self) -> NavienDevice | None:
        """Return the latest device snapshot."""
        return self.coordinator.device_by_id(self._device_id)

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        raw = (self.device.raw if self.device else {}) or {}
        return self.device is not None and bool(raw.get("connected", True))

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


class NavienSmartModeSelect(NavienSmartSelectBase):
    """Operation mode selector."""

    def __init__(
        self,
        coordinator: NavienSmartDataUpdateCoordinator,
        device: NavienDevice,
    ) -> None:
        super().__init__(coordinator, device, "operation_mode", "운전모드")

    @property
    def options(self) -> list[str]:
        """Return available mode names."""
        return [mode.name for mode in (self.device.modes if self.device else ())]

    @property
    def current_option(self) -> str | None:
        """Return selected mode."""
        device = self.device
        if device is None or device.current_mode_key is None:
            return None
        mode = _mode_by_key(device, device.current_mode_key)
        return mode.name if mode else None

    async def async_select_option(self, option: str) -> None:
        """Select a mode."""
        device = self.device
        if device is None:
            return
        mode = _mode_by_name(device, option)
        if mode is None:
            return
        await self.coordinator.client.async_set_mode(self._device_id, mode.key)
        await self.coordinator.async_request_refresh()


class NavienSmartFanSelect(NavienSmartSelectBase):
    """Fan option selector."""

    def __init__(
        self,
        coordinator: NavienSmartDataUpdateCoordinator,
        device: NavienDevice,
    ) -> None:
        super().__init__(coordinator, device, "fan", "풍량")

    @property
    def options(self) -> list[str]:
        """Return fan options for the current mode."""
        mode = self._current_mode()
        if mode is None:
            return []
        if not _mode_has_selectable_fan(mode):
            default_fan = _default_fan_for_mode(mode)
            return [default_fan.name] if default_fan else []
        return [fan.name for fan in mode.fan_options]

    @property
    def current_option(self) -> str | None:
        """Return selected fan option."""
        mode = self._current_mode()
        device = self.device
        if mode is None or device is None:
            return None
        fan_key = device.current_fan_key
        for fan in mode.fan_options:
            if fan.key == fan_key:
                return fan.name
        default_fan = _default_fan_for_mode(mode)
        return default_fan.name if default_fan else None

    async def async_select_option(self, option: str) -> None:
        """Select a fan option."""
        mode = self._current_mode()
        if mode is None or not _mode_has_selectable_fan(mode):
            return
        for fan in mode.fan_options:
            if fan.name == option:
                await self.coordinator.client.async_set_fan(self._device_id, fan.key)
                await self.coordinator.async_request_refresh()
                return

    def _current_mode(self) -> NavienMode | None:
        """Return the current mode, or the first supported mode before a command is sent."""
        device = self.device
        if device is None or not device.modes:
            return None
        if device.current_mode_key is not None:
            return _mode_by_key(device, device.current_mode_key)
        return device.modes[0]


class NavienSmartAirMonitorLedSelect(NavienSmartSelectBase):
    """External air monitor LED brightness selector."""

    _attr_icon = "mdi:brightness-6"

    def __init__(
        self,
        coordinator: NavienSmartDataUpdateCoordinator,
        device: NavienDevice,
    ) -> None:
        super().__init__(coordinator, device, "air_monitor_led_brightness", "LED 밝기")

    @property
    def options(self) -> list[str]:
        """Return brightness steps shown by the Navien app."""
        return ["1단계", "2단계", "3단계", "4단계"]

    @property
    def current_option(self) -> str | None:
        """Return selected brightness step."""
        device = self.device
        if device is None or device.air_monitor_led_brightness is None:
            return None
        return f"{device.air_monitor_led_brightness + 1}단계"

    async def async_select_option(self, option: str) -> None:
        """Select LED brightness."""
        if option not in self.options:
            return
        level = self.options.index(option)
        await self.coordinator.client.async_set_air_monitor_led_brightness(
            self._device_id,
            level,
        )
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Group LED brightness under the air monitor device when possible."""
        device = self.device
        if device is None:
            return None
        profile = device.sensor_profile or {}
        raw = device.raw or {}
        sensor_device_id = str(profile.get("deviceId") or raw.get("deviceId") or device.id)
        if profile.get("source") == "external_air_monitor":
            model = profile.get("modelName") or "Air Monitor"
            model_code = profile.get("modelCode")
            if model_code:
                model = f"{model} ({model_code})"
            return DeviceInfo(
                identifiers={(DOMAIN, f"{device.id}_air_monitor_{sensor_device_id}")},
                manufacturer="KyungDong Navien",
                name="에어모니터",
                model=str(model) if model else None,
                serial_number=sensor_device_id,
            )
        return super().device_info


def _mode_by_key(device: NavienDevice, key: str) -> NavienMode | None:
    """Find a mode by key."""
    return next((mode for mode in device.modes if mode.key == key), None)


def _mode_by_name(device: NavienDevice, name: str) -> NavienMode | None:
    """Find a mode by display name."""
    return next((mode for mode in device.modes if mode.name == name), None)


def _default_fan_for_mode(mode: NavienMode) -> NavienFanOption | None:
    """Return the mode's configured default fan option."""
    for fan in mode.fan_options:
        if fan.option == mode.option and fan.air_volume == mode.air_volume:
            return fan
    return mode.fan_options[0] if mode.fan_options else None


def _mode_has_selectable_fan(mode: NavienMode) -> bool:
    """Return whether users can change fan options in this mode."""
    return any(fan.configurable for fan in mode.fan_options)


def _has_air_monitor_led(device: NavienDevice) -> bool:
    """Return whether the device exposes an external air monitor LED capability."""
    profile = device.sensor_profile or {}
    return (
        profile.get("source") == "external_air_monitor"
        and bool(profile.get("deviceId"))
        and str(profile.get("modelCode") or "") in NRT530_AIR_MONITOR_MODEL_NAMES
    )
