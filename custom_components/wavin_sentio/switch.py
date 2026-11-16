"""Switches on the CCU device: standby and vacation."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOC_HOLD_STANDBY, LOC_HOLD_VACATION
from .coordinator import SentioConfigEntry, SentioCoordinator
from .entity import SentioHubEntity

PARALLEL_UPDATES = 1

SWITCHES = (
    ("standby", LOC_HOLD_STANDBY),
    ("vacation", LOC_HOLD_VACATION),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SentioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SentioFlagSwitch(coordinator, k, a) for k, a in SWITCHES)


class SentioFlagSwitch(SentioHubEntity, SwitchEntity):
    def __init__(self, coordinator: SentioCoordinator, key: str, address: int) -> None:
        super().__init__(coordinator, key)
        self.entity_description = SwitchEntityDescription(key=key, translation_key=key)
        self._key = key
        self._address = address

    @property
    def is_on(self) -> bool | None:
        return getattr(self.coordinator.data.location, self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_flag(self._address, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_flag(self._address, False)
