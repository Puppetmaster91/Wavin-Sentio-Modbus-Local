"""Climate entity: one per zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BLOCKING_SOURCES
from .const import MODE_MANUAL, MODE_SCHEDULE
from .coordinator import SentioConfigEntry, SentioCoordinator
from .entity import SentioZoneEntity

PARALLEL_UPDATES = 1

OVERRIDES = {0: "none", 1: "temporary", 2: "vacation_away", 3: "adjust"}

ACTIONS = {
    1: HVACAction.IDLE,
    2: HVACAction.HEATING,
    3: HVACAction.COOLING,
    4: HVACAction.IDLE,
    5: HVACAction.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SentioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SentioZoneClimate(coordinator, z) for z in coordinator.active_zones)


class SentioZoneClimate(SentioZoneEntity, ClimateEntity):
    """Room thermostat for one Sentio zone."""

    _attr_name = None  # use the device (zone) name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: SentioCoordinator, zone: int) -> None:
        super().__init__(coordinator, zone, "climate")

    @property
    def current_temperature(self) -> float | None:
        data = self.zone_data
        return data.air_temp if data else None

    @property
    def target_temperature(self) -> float | None:
        # "Desired temp" is the effective target in every mode
        # (schedule, manual, vacation, standby, temporary override).
        data = self.zone_data
        return data.desired_temp if data else None

    @property
    def hvac_mode(self) -> HVACMode | None:
        data = self.zone_data
        if data is None:
            return None
        if data.mode == MODE_MANUAL:
            return HVACMode.HEAT
        if data.mode == MODE_SCHEDULE:
            return HVACMode.AUTO
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        data = self.zone_data
        if data is None or data.state is None:
            return None
        return ACTIONS.get(data.state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.zone_data
        if data is None:
            return {}
        return {
            "zone": self.zone,
            "manual_setpoint": data.setpoint,
            "override": OVERRIDES.get(data.override, data.override),
            "blocking_source": BLOCKING_SOURCES.get(
                data.blocking_source, data.blocking_source
            ),
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        data = self.zone_data
        # The setpoint register is ignored in schedule mode, so switch the
        # zone to manual when a temperature is set from Home Assistant.
        force_manual = data is None or data.mode != MODE_MANUAL
        await self.coordinator.async_set_zone_setpoint(
            self.zone, float(temperature), force_manual
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode = MODE_MANUAL if hvac_mode == HVACMode.HEAT else MODE_SCHEDULE
        await self.coordinator.async_set_zone_mode(self.zone, mode)
