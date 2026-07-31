"""Diagnostics support for Navien Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN


REDACTED_KEYS = {
    "deviceId",
    "deviceSeq",
    "serial_number",
    "sensor_device_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    return {
        "entry": {
            **entry.as_dict(),
            "data": {
                **entry.data,
                CONF_USERNAME: "**REDACTED**",
                CONF_PASSWORD: "**REDACTED**",
            },
        },
        "devices": [
            _device_diagnostics(device)
            for device in getattr(coordinator, "devices", [])
        ],
        "client": (
            coordinator.client.diagnostics_snapshot()
            if coordinator is not None
            else {}
        ),
    }


def _device_diagnostics(device: Any) -> dict[str, Any]:
    """Return non-sensitive device details useful for model support."""
    raw = device.raw or {}
    return {
        "id": "**REDACTED**",
        "name": device.name,
        "type": device.type,
        "power": device.power,
        "running": device.running,
        "running_name": device.running_name,
        "error_code": device.error_code,
        "current_mode_key": device.current_mode_key,
        "current_fan_key": device.current_fan_key,
        "target_humidity": device.target_humidity,
        "air_monitor_led_brightness": device.air_monitor_led_brightness,
        "filters": _redact(device.filters),
        "model": {
            "serviceCode": raw.get("serviceCode"),
            "modelCode": raw.get("modelCode"),
            "modelName": raw.get("modelName"),
            "modelDisplayName": raw.get("modelDisplayName"),
            "connected": raw.get("connected"),
            "firmware": _firmware_summary(raw),
        },
        "sensor_profile": _redact(raw.get("sensorProfile") or device.sensor_profile or {}),
        "air_sensor_keys": sorted((device.air_sensors or {}).keys()),
        "modes": [
            {
                "key": mode.key,
                "name": mode.name,
                "mode": mode.mode,
                "option": mode.option,
                "air_volume": mode.air_volume,
                "configurable": mode.configurable,
                "humidity_min": mode.humidity_min,
                "humidity_max": mode.humidity_max,
                "fan_options": [
                    {
                        "key": fan.key,
                        "name": fan.name,
                        "option": fan.option,
                        "air_volume": fan.air_volume,
                        "configurable": fan.configurable,
                    }
                    for fan in mode.fan_options
                ],
            }
            for mode in device.modes
        ],
    }


def _firmware_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Return model/version fields from the raw device payload."""
    data = raw.get("data") or {}
    reported = ((data.get("did") or {}).get("reported") or {})
    if not isinstance(reported, dict):
        return {}
    room_controller = reported.get("roomController") or {}
    odu = reported.get("odu") or {}
    idu = reported.get("idu") or {}
    air_monitors = _list_value(reported.get("airMonitor"))
    return {
        "roomController": _model_version(room_controller),
        "odu": _model_version(odu),
        "idu": _model_version(idu),
        "airMonitor": [
            _model_version(item)
            for item in air_monitors
            if isinstance(item, dict)
        ],
    }


def _model_version(value: Any) -> dict[str, Any]:
    """Return common model/version fields."""
    if not isinstance(value, dict):
        return {}
    return {
        "modelCode": value.get("modelCode"),
        "version": value.get("version"),
        "mountedAPS": value.get("mountedAPS"),
    }


def _list_value(value: Any) -> list[Any]:
    """Return a list for values that may be encoded as a single object."""
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _redact(value: Any) -> Any:
    """Redact identifiers from diagnostics."""
    if isinstance(value, dict):
        return {
            key: "**REDACTED**" if key in REDACTED_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
