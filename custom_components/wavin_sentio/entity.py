"""Base entities."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HccData, SentioCoordinator, SourceData, ZoneData


class SentioHubEntity(CoordinatorEntity[SentioCoordinator]):
    """Entity on the CCU device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SentioCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.hub_identifier}_{key}"
        self._attr_device_info = coordinator.hub_device_info()


class SentioZoneEntity(CoordinatorEntity[SentioCoordinator]):
    """Entity on a zone device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SentioCoordinator, zone: int, key: str) -> None:
        super().__init__(coordinator)
        self.zone = zone
        self._attr_unique_id = f"{coordinator.hub_identifier}_zone{zone}_{key}"
        self._attr_device_info = coordinator.zone_device_info(zone)

    @property
    def zone_data(self) -> ZoneData | None:
        return self.coordinator.data.zones.get(self.zone)

    @property
    def available(self) -> bool:
        return super().available and self.zone_data is not None


class SentioHccEntity(CoordinatorEntity[SentioCoordinator]):
    """Entity on a heating/cooling controller (HCC) device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SentioCoordinator, hcc: int, key: str) -> None:
        super().__init__(coordinator)
        self.hcc = hcc
        self._attr_unique_id = f"{coordinator.hub_identifier}_hcc{hcc}_{key}"
        self._attr_device_info = coordinator.hcc_device_info(hcc)

    @property
    def hcc_data(self) -> HccData | None:
        return self.coordinator.data.hccs.get(self.hcc)

    @property
    def available(self) -> bool:
        return super().available and self.hcc_data is not None


class SentioSourceEntity(CoordinatorEntity[SentioCoordinator]):
    """Entity on the heat source device (H/C source + boiler/heat pump)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SentioCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.hub_identifier}_source_{key}"
        self._attr_device_info = coordinator.source_device_info()

    @property
    def source_data(self) -> SourceData | None:
        return self.coordinator.data.source

    @property
    def available(self) -> bool:
        return super().available and self.source_data is not None
