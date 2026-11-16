"""Binary sensors (warnings and errors)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
class ZoneBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[ZoneData], bool]


@dataclass(frozen=True, kw_only=True)
class HubBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[LocationData], bool]


ZONE_BINARY: tuple[ZoneBinaryDescription, ...] = (
    ZoneBinaryDescription(
        key="warning",
        translation_key="warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.warning,
    ),
    ZoneBinaryDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.error,
    ),
    ZoneBinaryDescription(
        key="low_battery",
        translation_key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.low_battery,
    ),
    ZoneBinaryDescription(
        key="peripheral_lost",
        translation_key="peripheral_lost",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.peripheral_lost,
    ),
)

HUB_BINARY: tuple[HubBinaryDescription, ...] = (
    HubBinaryDescription(
        key="warning",
        translation_key="warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.warning,
    ),
    HubBinaryDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.error,
    ),
)


@dataclass(frozen=True, kw_only=True)
class HccBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[HccData], bool | None]


@dataclass(frozen=True, kw_only=True)
class SourceBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[SourceData], bool | None]
    boiler: bool = False


_DIAG = EntityCategory.DIAGNOSTIC
_PROBLEM = BinarySensorDeviceClass.PROBLEM

HCC_BINARY: tuple[HccBinaryDescription, ...] = (
    HccBinaryDescription(
        key="pump",
        translation_key="pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.pump_running,
    ),
    HccBinaryDescription(
        key="pump_demand",
        translation_key="pump_demand",
        entity_category=_DIAG,
        value_fn=lambda d: d.pump_demand,
    ),
    HccBinaryDescription(
        key="warning", translation_key="warning", device_class=_PROBLEM,
        entity_category=_DIAG, value_fn=lambda d: d.warning,
    ),
    HccBinaryDescription(
        key="error", translation_key="error", device_class=_PROBLEM,
        entity_category=_DIAG, value_fn=lambda d: d.error,
    ),
    HccBinaryDescription(
        key="inlet_sensor_failure", translation_key="inlet_sensor_failure",
        device_class=_PROBLEM, entity_category=_DIAG,
        value_fn=lambda d: d.inlet_sensor_failure,
    ),
    HccBinaryDescription(
        key="high_temp_cutoff", translation_key="high_temp_cutoff",
        device_class=_PROBLEM, entity_category=_DIAG,
        value_fn=lambda d: d.high_temp_cutoff,
    ),
)

SOURCE_BINARY: tuple[SourceBinaryDescription, ...] = (
    SourceBinaryDescription(
        key="source_warning", translation_key="warning", device_class=_PROBLEM,
        entity_category=_DIAG, value_fn=lambda d: d.source_warning,
    ),
    SourceBinaryDescription(
        key="source_error", translation_key="error", device_class=_PROBLEM,
        entity_category=_DIAG, value_fn=lambda d: d.source_error,
    ),
    SourceBinaryDescription(
        key="source_failure", translation_key="general_failure", device_class=_PROBLEM,
        entity_category=_DIAG, value_fn=lambda d: d.source_failure,
    ),
    SourceBinaryDescription(
        key="boiler_warning", translation_key="boiler_warning", device_class=_PROBLEM,
        entity_category=_DIAG, boiler=True, value_fn=lambda d: d.boiler_warning,
    ),
    SourceBinaryDescription(
        key="boiler_error", translation_key="boiler_error", device_class=_PROBLEM,
        entity_category=_DIAG, boiler=True, value_fn=lambda d: d.boiler_error,
    ),
    SourceBinaryDescription(
        key="boiler_inlet_sensor_failure",
        translation_key="boiler_inlet_sensor_failure", device_class=_PROBLEM,
        entity_category=_DIAG, boiler=True,
        value_fn=lambda d: d.boiler_inlet_sensor_failure,
    ),
    SourceBinaryDescription(
        key="boiler_failure", translation_key="boiler_failure", device_class=_PROBLEM,
        entity_category=_DIAG, boiler=True, value_fn=lambda d: d.boiler_failure,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SentioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        SentioHubBinary(coordinator, d) for d in HUB_BINARY
    ]
    for zone in coordinator.active_zones:
        entities.extend(SentioZoneBinary(coordinator, zone, d) for d in ZONE_BINARY)
    for hcc in coordinator.hccs:
        entities.extend(SentioHccBinary(coordinator, hcc, d) for d in HCC_BINARY)
    if coordinator.has_source or coordinator.has_boiler:
        for sd in SOURCE_BINARY:
            if sd.boiler and not coordinator.has_boiler:
                continue
            if not sd.boiler and not coordinator.has_source:
                continue
            entities.append(SentioSourceBinary(coordinator, sd))
    async_add_entities(entities)


class SentioZoneBinary(SentioZoneEntity, BinarySensorEntity):
    entity_description: ZoneBinaryDescription

    def __init__(
        self, coordinator: SentioCoordinator, zone: int, description: ZoneBinaryDescription
    ) -> None:
        super().__init__(coordinator, zone, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.zone_data
        return self.entity_description.value_fn(data) if data else None


class SentioHubBinary(SentioHubEntity, BinarySensorEntity):
    entity_description: HubBinaryDescription

    def __init__(
        self, coordinator: SentioCoordinator, description: HubBinaryDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data.location)


class SentioHccBinary(SentioHccEntity, BinarySensorEntity):
    entity_description: HccBinaryDescription

    def __init__(
        self, coordinator: SentioCoordinator, hcc: int, description: HccBinaryDescription
    ) -> None:
        super().__init__(coordinator, hcc, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.hcc_data
        return self.entity_description.value_fn(data) if data else None


class SentioSourceBinary(SentioSourceEntity, BinarySensorEntity):
    entity_description: SourceBinaryDescription

    def __init__(
        self, coordinator: SentioCoordinator, description: SourceBinaryDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.source_data
        return self.entity_description.value_fn(data) if data else None
