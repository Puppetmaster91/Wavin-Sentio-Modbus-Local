"""Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BLOCKING_SOURCES, BOILER_STATES, ZONE_STATES
from .coordinator import (
    HccData,
    LocationData,
    SourceData,
    SentioConfigEntry,
    SentioCoordinator,
    ZoneData,
)
from .entity import (
    SentioHccEntity,
    SentioHubEntity,
    SentioSourceEntity,
    SentioZoneEntity,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ZoneSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ZoneData], Any]


@dataclass(frozen=True, kw_only=True)
class HubSensorDescription(SensorEntityDescription):
    value_fn: Callable[[LocationData], Any]
    supported_key: str | None = None


ZONE_SENSORS: tuple[ZoneSensorDescription, ...] = (
    ZoneSensorDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.air_temp,
    ),
    ZoneSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.humidity,
    ),
    ZoneSensorDescription(
        key="floor_temperature",
        translation_key="floor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.floor_temp,
    ),
    ZoneSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.dew_point,
    ),
    ZoneSensorDescription(
        key="desired_temperature",
        translation_key="desired_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.desired_temp,
    ),
    ZoneSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=list(ZONE_STATES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: ZONE_STATES.get(d.state) if d.state is not None else None,
    ),
    ZoneSensorDescription(
        key="blocking_source",
        translation_key="blocking_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            BLOCKING_SOURCES.get(d.blocking_source, f"unknown_{d.blocking_source}")
            if d.blocking_source is not None
            else None
        ),
    ),
)

# Sensors that are only enabled by default when the controller reports a value
# at setup time (e.g. no floor sensor -> no floor temperature entity enabled).
AUTO_ENABLE = {"air_temperature", "humidity", "floor_temperature"}

HUB_SENSORS: tuple[HubSensorDescription, ...] = (
    HubSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        supported_key="outdoor",
        value_fn=lambda d: d.outdoor_temp,
    ),
    HubSensorDescription(
        key="hc_mode",
        translation_key="hc_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["heating", "cooling"],
        supported_key="hc_mode",
        value_fn=lambda d: {0: "heating", 1: "cooling"}.get(d.hc_mode),
    ),
)


def _blocking(value: int | None) -> str | None:
    if value is None:
        return None
    return BLOCKING_SOURCES.get(value, f"unknown_{value}")


@dataclass(frozen=True, kw_only=True)
class HccSensorDescription(SensorEntityDescription):
    value_fn: Callable[[HccData], Any]


@dataclass(frozen=True, kw_only=True)
class SourceSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SourceData], Any]


def _temp(key: str, fn, **kw):
    return dict(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=fn,
        **kw,
    )


HCC_SENSORS: tuple[HccSensorDescription, ...] = (
    HccSensorDescription(**_temp("inlet_temperature", lambda d: d.inlet_temp)),
    HccSensorDescription(
        **_temp("desired_inlet_temperature", lambda d: d.desired_inlet_temp)
    ),
    HccSensorDescription(
        **_temp(
            "desired_room_temperature",
            lambda d: d.desired_room_temp,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    ),
    HccSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=list(ZONE_STATES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: ZONE_STATES.get(d.state) if d.state is not None else None,
    ),
    HccSensorDescription(
        key="blocking_source",
        translation_key="blocking_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _blocking(d.blocking_source),
    ),
)

SOURCE_SENSORS: tuple[SourceSensorDescription, ...] = (
    SourceSensorDescription(
        key="hc_state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=list(ZONE_STATES.values()),
        value_fn=lambda d: ZONE_STATES.get(d.hc_state) if d.hc_state is not None else None,
    ),
    SourceSensorDescription(
        key="boiler_state",
        translation_key="boiler_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(BOILER_STATES.values()),
        value_fn=lambda d: (
            BOILER_STATES.get(d.boiler_state) if d.boiler_state is not None else None
        ),
    ),
    SourceSensorDescription(
        key="boiler_blocking_source",
        translation_key="blocking_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _blocking(d.boiler_blocking_source),
    ),
    SourceSensorDescription(
        **_temp("boiler_requested_temperature", lambda d: d.boiler_requested_temp)
    ),
    SourceSensorDescription(
        **_temp("boiler_inlet_temperature", lambda d: d.boiler_inlet_temp)
    ),
)
SOURCE_BOILER_ONLY = {
    "boiler_state",
    "boiler_blocking_source",
    "boiler_requested_temperature",
    "boiler_inlet_temperature",
}
SOURCE_AUTO_ENABLE = {"boiler_inlet_temperature"}

THERMISTOR_SENSORS: tuple[HubSensorDescription, ...] = tuple(
    HubSensorDescription(
        key=f"thermistor_{i + 1}",
        translation_key="thermistor",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        supported_key="thermistors",
        value_fn=lambda d, i=i: d.thermistors[i],
    )
    for i in range(5)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SentioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for zone in coordinator.active_zones:
        zdata = coordinator.data.zones.get(zone)
        for desc in ZONE_SENSORS:
            enabled = desc.entity_registry_enabled_default
            if desc.key in AUTO_ENABLE:
                enabled = zdata is not None and desc.value_fn(zdata) is not None
            entities.append(SentioZoneSensor(coordinator, zone, desc, enabled))

    for hcc in coordinator.hccs:
        hdata = coordinator.data.hccs.get(hcc)
        for hdesc2 in HCC_SENSORS:
            enabled = hdesc2.entity_registry_enabled_default
            if hdesc2.key == "desired_room_temperature":
                enabled = hdata is not None and hdesc2.value_fn(hdata) is not None
            entities.append(SentioHccSensor(coordinator, hcc, hdesc2, enabled))

    sdata = coordinator.data.source
    if sdata is not None:
        for sdesc in SOURCE_SENSORS:
            if sdesc.key in SOURCE_BOILER_ONLY and not coordinator.has_boiler:
                continue
            if sdesc.key == "hc_state" and not coordinator.has_source:
                continue
            enabled = True
            if sdesc.key in SOURCE_AUTO_ENABLE:
                enabled = sdesc.value_fn(sdata) is not None
            entities.append(SentioSourceSensor(coordinator, sdesc, enabled))

    for hdesc in HUB_SENSORS:
        if hdesc.supported_key and not coordinator.supports(hdesc.supported_key):
            continue
        enabled = hdesc.value_fn(coordinator.data.location) is not None
        entities.append(SentioHubSensor(coordinator, hdesc, enabled))

    for tdesc in THERMISTOR_SENSORS:
        if not coordinator.supports("thermistors"):
            break
        # Only enabled by default when a sensor is actually connected.
        enabled = tdesc.value_fn(coordinator.data.location) is not None
        entities.append(SentioHubSensor(coordinator, tdesc, enabled))

    pair = coordinator.delta_pair()
    if pair is not None and coordinator.supports("thermistors"):
        flow_i, ret_i = pair[0] - 1, pair[1] - 1
        entities.append(
            SentioHubSensor(
                coordinator,
                HubSensorDescription(
                    key="delta_t",
                    translation_key="delta_t",
                    # No device class on purpose: a temperature *difference*
                    # must not be unit-converted like a temperature.
                    native_unit_of_measurement=UnitOfTemperature.KELVIN,
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_display_precision=1,
                    supported_key="thermistors",
                    value_fn=lambda d, f=flow_i, r=ret_i: (
                        None
                        if d.thermistors[f] is None or d.thermistors[r] is None
                        else round(d.thermistors[f] - d.thermistors[r], 2)
                    ),
                ),
                True,
            )
        )

    async_add_entities(entities)


class SentioZoneSensor(SentioZoneEntity, SensorEntity):
    entity_description: ZoneSensorDescription

    def __init__(
        self,
        coordinator: SentioCoordinator,
        zone: int,
        description: ZoneSensorDescription,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator, zone, description.key)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def native_value(self) -> Any:
        data = self.zone_data
        return self.entity_description.value_fn(data) if data else None


class SentioHubSensor(SentioHubEntity, SensorEntity):
    entity_description: HubSensorDescription

    def __init__(
        self,
        coordinator: SentioCoordinator,
        description: HubSensorDescription,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = enabled_default
        if description.key.startswith("thermistor_"):
            self._attr_translation_placeholders = {
                "n": description.key.rsplit("_", 1)[1]
            }

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data.location)


class SentioHccSensor(SentioHccEntity, SensorEntity):
    entity_description: HccSensorDescription

    def __init__(
        self,
        coordinator: SentioCoordinator,
        hcc: int,
        description: HccSensorDescription,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator, hcc, description.key)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def native_value(self) -> Any:
        data = self.hcc_data
        return self.entity_description.value_fn(data) if data else None


class SentioSourceSensor(SentioSourceEntity, SensorEntity):
    entity_description: SourceSensorDescription

    def __init__(
        self,
        coordinator: SentioCoordinator,
        description: SourceSensorDescription,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def native_value(self) -> Any:
        data = self.source_data
        return self.entity_description.value_fn(data) if data else None
