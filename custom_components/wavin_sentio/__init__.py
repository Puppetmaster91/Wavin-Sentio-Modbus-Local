"""Wavin Sentio (local Modbus TCP) integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .api import SentioClient, SentioConnectionError, SentioModbusError, decode_fp100
from .const import CONF_UNIT_ID, DEFAULT_UNIT_ID, DOMAIN
from .coordinator import SentioConfigEntry, SentioCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


READ_SCHEMA = vol.Schema(
    {
        vol.Required("type", default="input"): vol.In(["input", "holding", "discrete"]),
        vol.Required("address"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        vol.Optional("count", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
        vol.Optional("individually", default=True): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the register-probe action."""

    async def read_registers(call: ServiceCall) -> dict:
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        if not entries:
            raise HomeAssistantError("No loaded Wavin Sentio entry")
        client = entries[0].runtime_data.client
        kind = call.data["type"]
        address = call.data["address"]
        count = call.data["count"]

        async def read(addr: int, n: int) -> list:
            if kind == "discrete":
                return [int(b) for b in await client.read_discrete(addr, n)]
            if kind == "holding":
                return await client.read_holding(addr, n)
            return await client.read_input(addr, n)

        result: list[dict] = []
        try:
            if call.data["individually"]:
                for addr in range(address, address + count):
                    try:
                        raw = (await read(addr, 1))[0]
                        item = {"address": addr, "raw": raw}
                        if kind != "discrete":
                            item["fp100"] = decode_fp100(raw)
                        result.append(item)
                    except SentioModbusError as err:
                        result.append({"address": addr, "error": f"exception {err.code}"})
            else:
                for i in range(0, count, 32):
                    n = min(32, count - i)
                    for j, raw in enumerate(await read(address + i, n)):
                        item = {"address": address + i + j, "raw": raw}
                        if kind != "discrete":
                            item["fp100"] = decode_fp100(raw)
                        result.append(item)
        except SentioModbusError as err:
            raise HomeAssistantError(f"Sentio returned Modbus exception {err.code}") from err
        except SentioConnectionError as err:
            raise HomeAssistantError(f"Cannot reach Sentio: {err}") from err
        return {"type": kind, "registers": result}

    hass.services.async_register(
        DOMAIN,
        "read_registers",
        read_registers,
        schema=READ_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SentioConfigEntry) -> bool:
    """Set up from a config entry."""
    client = SentioClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
    )
    coordinator = SentioCoordinator(hass, entry, client)
    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await client.close()
        raise

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def _async_reload_on_update(hass: HomeAssistant, entry: SentioConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SentioConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.close()
    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: SentioConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deleting zone/HCC/source devices that are not in use.

    The CCU device and every device that is currently active stay protected.
    """
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return False
    hub = coordinator.hub_identifier
    active = {hub}
    active.update(f"{hub}_zone_{z}" for z in coordinator.active_zones)
    active.update(f"{hub}_hcc_{n}" for n in coordinator.hccs)
    if coordinator.has_source or coordinator.has_boiler:
        active.add(f"{hub}_source")
    return not any(
        domain == DOMAIN and ident in active for domain, ident in device_entry.identifiers
    )
