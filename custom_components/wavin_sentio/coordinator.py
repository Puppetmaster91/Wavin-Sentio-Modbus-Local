"""Data update coordinator for Wavin Sentio."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EXC_ILLEGAL_ADDRESS,
    SentioClient,
    SentioConnectionError,
    SentioInfo,
    SentioModbusError,
    async_read_device_info,
    decode_fp100,
    decode_string,
    decode_u1,
    encode_fp100,
)
from .const import (
    CONF_FLOW_SENSOR,
    CONF_HCCS,
    CONF_RETURN_SENSOR,
    CONF_ZONES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOC_HOLD_STANDBY,
    LOC_HOLD_VACATION,
    LOC_IN_HC_MODE,
    MAX_ZONES,
    MODE_MANUAL,
    OUTDOOR_IN_TEMP,
    THERMISTOR_IN_FIRST,
    THERMISTOR_COUNT,
    BOILER_HOLD_NAME,
    BOILER_IN_FIRST,
    HCC_BASES,
    SOURCE_IN_STATE,
    ZONE_DISC_FIRST,
    ZONE_HOLD_MODE,
    ZONE_HOLD_NAME,
    ZONE_HOLD_SETPOINT,
    ZONE_IN_DESIRED,
    ZONE_IN_ROOM_TYPE,
)

_LOGGER = logging.getLogger(__name__)

type SentioConfigEntry = ConfigEntry["SentioCoordinator"]


@dataclass
class ZoneData:
    """Values for one zone."""

    desired_temp: float | None
    state: int | None
    blocking_source: int | None
    air_temp: float | None
    floor_temp: float | None
    humidity: float | None
    dew_point: float | None
    mode: int | None
    override: int | None
    setpoint: float | None
    warning: bool
    error: bool
    low_battery: bool
    peripheral_lost: bool


@dataclass
class LocationData:
    """Values for the controller itself."""

    warning: bool
    error: bool
    hc_mode: int | None
    standby: bool | None
    vacation: bool | None
    outdoor_temp: float | None
    thermistors: list[float | None]


@dataclass
class HccData:
    """Heating/cooling controller (e.g. the floor heating loop with pump P1)."""

    state: int | None
    blocking_source: int | None
    pump_demand: bool | None
    pump_running: bool | None
    inlet_temp: float | None
    desired_inlet_temp: float | None
    desired_room_temp: float | None
    warning: bool | None
    error: bool | None
    inlet_sensor_failure: bool | None
    high_temp_cutoff: bool | None


@dataclass
class SourceData:
    """Heat source: H/C source and boiler / heat pump."""

    hc_state: int | None
    source_warning: bool | None
    source_error: bool | None
    source_failure: bool | None
    boiler_state: int | None
    boiler_blocking_source: int | None
    boiler_inlet_temp: float | None
    boiler_requested_temp: float | None
    boiler_warning: bool | None
    boiler_error: bool | None
    boiler_inlet_sensor_failure: bool | None
    boiler_failure: bool | None


@dataclass
class SentioData:
    """Everything read in one update."""

    location: LocationData
    zones: dict[int, ZoneData | None]
    hccs: dict[int, HccData | None]
    source: SourceData | None


class SentioCoordinator(DataUpdateCoordinator[SentioData]):
    """Polls the Sentio CCU."""

    config_entry: SentioConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SentioConfigEntry, client: SentioClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.info: SentioInfo
        self.available_zones: dict[int, str] = {}
        self.active_zones: list[int] = []
        self._default_zones: list[int] = []
        self.hccs: dict[int, str] = {}  # active HCCs
        self.available_hccs: dict[int, str] = {}  # all that answered
        self._default_hccs: list[int] = []
        self.has_source = False
        self.has_boiler = False
        self.source_name = ""
        self._unsupported: set[str] = set()

    # ------------------------------------------------------------- setup
    async def async_setup(self) -> None:
        """Read device info and discover zones."""
        entry = self.config_entry
        try:
            self.info = await async_read_device_info(
                self.client, entry.data["host"], entry.data["port"]
            )
            await self._discover_zones()
            await self._discover_heating()
        except SentioConnectionError as err:
            raise ConfigEntryNotReady(f"Cannot reach Sentio: {err}") from err
        except SentioModbusError as err:
            raise ConfigEntryNotReady(f"Sentio returned an error: {err}") from err

        selected = entry.options.get(CONF_ZONES)
        if selected is None:
            self.active_zones = list(self._default_zones)
        else:
            self.active_zones = sorted(
                int(z) for z in selected if int(z) in self.available_zones
            )
        selected_hccs = entry.options.get(CONF_HCCS)
        if selected_hccs is None:
            active_hccs = list(self._default_hccs)
        else:
            active_hccs = sorted(
                int(h) for h in selected_hccs if int(h) in self.available_hccs
            )
        self.hccs = {n: self.available_hccs[n] for n in active_hccs}
        _LOGGER.debug(
            "Sentio zones discovered: %s, active: %s",
            self.available_zones,
            self.active_zones,
        )

    async def _discover_zones(self) -> None:
        for zone in range(1, MAX_ZONES + 1):
            base = zone * 100
            try:
                room_type = decode_u1(
                    (await self.client.read_input(base + ZONE_IN_ROOM_TYPE, 1))[0]
                )
            except SentioModbusError as err:
                _LOGGER.debug("Zone %s not present (exception %s)", zone, err.code)
                continue
            if room_type != 0:
                _LOGGER.info(
                    "Zone %s is a dummy room or unknown type (%s); skipping", zone, room_type
                )
                continue
            try:
                desired = (await self.client.read_input(base + ZONE_IN_DESIRED, 1))[0]
                name = decode_string(
                    await self.client.read_holding(base + ZONE_HOLD_NAME, 16)
                )
            except SentioModbusError as err:
                _LOGGER.debug("Zone %s unreadable (exception %s)", zone, err.code)
                continue
            self.available_zones[zone] = name or f"Zone {zone}"
            # A zone with no valid desired temperature is most likely unused.
            if decode_fp100(desired) is not None:
                self._default_zones.append(zone)

    async def _discover_heating(self) -> None:
        """Find HCCs, H/C source and boiler (controllers that answer)."""
        for n, base in HCC_BASES.items():
            try:
                probe = await self.client.read_input(base + 1, 6)
            except SentioModbusError:
                continue
            name = ""
            try:
                name = decode_string(await self.client.read_holding(base + 1, 16))
            except SentioModbusError:
                pass
            self.available_hccs[n] = name or f"HCC{n}"
            # An HCC without a valid flow temperature is most likely unused.
            if decode_fp100(probe[4]) is not None:
                self._default_hccs.append(n)

        try:
            await self.client.read_input(SOURCE_IN_STATE, 1)
            self.has_source = True
        except SentioModbusError:
            pass
        try:
            await self.client.read_input(BOILER_IN_FIRST, 4)
            self.has_boiler = True
            try:
                self.source_name = decode_string(
                    await self.client.read_holding(BOILER_HOLD_NAME, 16)
                )
            except SentioModbusError:
                pass
        except SentioModbusError:
            pass
        _LOGGER.debug(
            "Heating: hccs=%s source=%s boiler=%s",
            self.available_hccs,
            self.has_source,
            self.has_boiler,
        )

    # ------------------------------------------------------ device info
    @property
    def hub_identifier(self) -> str:
        return self.info.unique_id

    def hub_device_info(self) -> DeviceInfo:
        info = self.info
        return DeviceInfo(
            identifiers={(DOMAIN, self.hub_identifier)},
            name=info.title,
            manufacturer="Wavin",
            model=f"Sentio {info.model}",
            sw_version=f"{info.sw_version}.{info.sw_minor}",
            hw_version=str(info.hw_version),
            serial_number=(
                f"{info.serial_prefix}-{info.serial}" if info.serial is not None else None
            ),
        )

    def zone_name(self, zone: int) -> str:
        name = self.available_zones.get(zone, f"Zone {zone}")
        names = [self.available_zones.get(z) for z in self.active_zones]
        if names.count(name) > 1:
            return f"{name} (zone {zone})"
        return name

    def zone_device_info(self, zone: int) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.hub_identifier}_zone_{zone}")},
            name=self.zone_name(zone),
            manufacturer="Wavin",
            model="Sentio zone",
            via_device=(DOMAIN, self.hub_identifier),
        )

    def hcc_device_info(self, n: int) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.hub_identifier}_hcc_{n}")},
            name=self.hccs.get(n, f"HCC{n}"),
            manufacturer="Wavin",
            model="Sentio HCC",
            via_device=(DOMAIN, self.hub_identifier),
        )

    def source_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.hub_identifier}_source")},
            name=self.source_name or "Heat source",
            manufacturer="Wavin",
            model="Sentio heat source",
            via_device=(DOMAIN, self.hub_identifier),
        )

    def delta_pair(self) -> tuple[int, int] | None:
        """Thermistor numbers (1-5) used for flow and return, or None."""
        opts = self.config_entry.options
        flow = opts.get(CONF_FLOW_SENSOR)
        ret = opts.get(CONF_RETURN_SENSOR)
        if flow is None and ret is None:
            # Default: T2 = flow, T3 = return, if both are connected.
            therm = self.data.location.thermistors
            if therm[1] is not None and therm[2] is not None:
                return (2, 3)
            return None
        if flow in (None, "none") or ret in (None, "none"):
            return None
        return (int(flow), int(ret))

    def supports(self, key: str) -> bool:
        """False once an optional register was found to be missing."""
        return key not in self._unsupported

    # ----------------------------------------------------------- update
    async def _optional_input(self, key: str, address: int) -> int | None:
        if key in self._unsupported:
            return None
        try:
            return (await self.client.read_input(address, 1))[0]
        except SentioModbusError as err:
            if err.code == EXC_ILLEGAL_ADDRESS:
                _LOGGER.debug("Register %s (%s) not supported", address, key)
                self._unsupported.add(key)
            return None

    async def _optional_input_block(
        self, key: str, address: int, count: int
    ) -> list[int] | None:
        if key in self._unsupported:
            return None
        try:
            return await self.client.read_input(address, count)
        except SentioModbusError as err:
            if err.code == EXC_ILLEGAL_ADDRESS:
                _LOGGER.debug("Registers %s+%s (%s) not supported", address, count, key)
                self._unsupported.add(key)
            return None

    async def _async_update_data(self) -> SentioData:
        try:
            location = await self._read_location()
            zones: dict[int, ZoneData | None] = {}
            for zone in self.active_zones:
                try:
                    zones[zone] = await self._read_zone(zone)
                except SentioModbusError as err:
                    _LOGGER.debug("Zone %s read failed: %s", zone, err)
                    zones[zone] = None
            hccs: dict[int, HccData | None] = {}
            for n in self.hccs:
                try:
                    hccs[n] = await self._read_hcc(n)
                except SentioModbusError as err:
                    _LOGGER.debug("HCC%s read failed: %s", n, err)
                    hccs[n] = None
            source: SourceData | None = None
            if self.has_source or self.has_boiler:
                try:
                    source = await self._read_source()
                except SentioModbusError as err:
                    _LOGGER.debug("Heat source read failed: %s", err)
        except SentioConnectionError as err:
            raise UpdateFailed(f"Communication error: {err}") from err
        except SentioModbusError as err:
            raise UpdateFailed(f"Sentio error: {err}") from err
        return SentioData(location=location, zones=zones, hccs=hccs, source=source)

    async def _optional_discrete(self, address: int, count: int) -> list[bool | None]:
        try:
            return list(await self.client.read_discrete(address, count))
        except SentioModbusError:
            return [None] * count

    async def _read_hcc(self, n: int) -> HccData:
        base = HCC_BASES[n]
        inp = await self.client.read_input(base + 1, 6)  # 7701..7706
        room_raw = await self._optional_input(f"hcc{n}_room", base + 8)  # 7708
        disc = await self._optional_discrete(base + 1, 4)

        def pump(raw: int) -> bool | None:
            value = decode_u1(raw)
            return None if value is None else value == 2

        return HccData(
            state=decode_u1(inp[0]),
            blocking_source=decode_u1(inp[1]),
            pump_demand=pump(inp[2]),
            pump_running=pump(inp[3]),
            inlet_temp=decode_fp100(inp[4]),
            desired_inlet_temp=decode_fp100(inp[5]),
            desired_room_temp=None if room_raw is None else decode_fp100(room_raw),
            warning=disc[0],
            error=disc[1],
            inlet_sensor_failure=disc[2],
            high_temp_cutoff=disc[3],
        )

    async def _read_source(self) -> SourceData:
        hc_state = None
        src_flags: list[bool | None] = [None, None, None]
        if self.has_source:
            hc_state = decode_u1((await self.client.read_input(SOURCE_IN_STATE, 1))[0])
            src_flags = await self._optional_discrete(SOURCE_IN_STATE, 3)
        boiler = [None, None, None, None]
        boiler_flags: list[bool | None] = [None, None, None, None]
        if self.has_boiler:
            boiler = await self.client.read_input(BOILER_IN_FIRST, 4)
            boiler_flags = await self._optional_discrete(BOILER_IN_FIRST, 4)
        return SourceData(
            hc_state=hc_state,
            source_warning=src_flags[0],
            source_error=src_flags[1],
            source_failure=src_flags[2],
            boiler_state=None if boiler[0] is None else decode_u1(boiler[0]),
            boiler_blocking_source=None if boiler[1] is None else decode_u1(boiler[1]),
            boiler_inlet_temp=None if boiler[2] is None else decode_fp100(boiler[2]),
            boiler_requested_temp=None if boiler[3] is None else decode_fp100(boiler[3]),
            boiler_warning=boiler_flags[0],
            boiler_error=boiler_flags[1],
            boiler_inlet_sensor_failure=boiler_flags[2],
            boiler_failure=boiler_flags[3],
        )

    async def _read_location(self) -> LocationData:
        warn_err = await self.client.read_discrete(1, 2)
        hold = await self.client.read_holding(LOC_HOLD_STANDBY, 2)
        hc_raw = await self._optional_input("hc_mode", LOC_IN_HC_MODE)
        out_raw = await self._optional_input("outdoor", OUTDOOR_IN_TEMP)
        therm_raw = await self._optional_input_block(
            "thermistors", THERMISTOR_IN_FIRST, THERMISTOR_COUNT
        )
        return LocationData(
            warning=warn_err[0],
            error=warn_err[1],
            hc_mode=None if hc_raw is None else decode_u1(hc_raw),
            standby=None if hold[0] in (0xFF, 0xFFFF) else bool(hold[0]),
            vacation=None if hold[1] in (0xFF, 0xFFFF) else bool(hold[1]),
            outdoor_temp=None if out_raw is None else decode_fp100(out_raw),
            thermistors=(
                [None] * THERMISTOR_COUNT
                if therm_raw is None
                else [decode_fp100(r) for r in therm_raw]
            ),
        )

    async def _read_zone(self, zone: int) -> ZoneData:
        base = zone * 100
        inp = await self.client.read_input(base + 1, 7)  # 101..107
        hold = await self.client.read_holding(base + ZONE_HOLD_MODE, 6)  # 117..122
        disc = await self.client.read_discrete(base + ZONE_DISC_FIRST, 4)
        return ZoneData(
            desired_temp=decode_fp100(inp[0]),
            state=decode_u1(inp[1]),
            blocking_source=decode_u1(inp[2]),
            air_temp=decode_fp100(inp[3]),
            floor_temp=decode_fp100(inp[4]),
            humidity=decode_fp100(inp[5]),
            dew_point=decode_fp100(inp[6]),
            mode=decode_u1(hold[0]),
            override=decode_u1(hold[1]),
            setpoint=decode_fp100(hold[2]),
            warning=disc[0],
            error=disc[1],
            low_battery=disc[2],
            peripheral_lost=disc[3],
        )

    # ----------------------------------------------------------- writes
    async def _write(self, address: int, value: int) -> None:
        try:
            await self.client.write_register(address, value)
        except SentioModbusError as err:
            raise HomeAssistantError(
                f"Sentio rejected the write to register {address} "
                f"(Modbus exception {err.code}). Check that Modbus TCP is set to "
                "Read/write on the controller."
            ) from err
        except SentioConnectionError as err:
            raise HomeAssistantError(f"Cannot reach Sentio: {err}") from err

    async def async_set_zone_setpoint(
        self, zone: int, temperature: float, force_manual: bool
    ) -> None:
        base = zone * 100
        await self._write(base + ZONE_HOLD_SETPOINT, encode_fp100(temperature))
        if force_manual:
            await self._write(base + ZONE_HOLD_MODE, MODE_MANUAL)
        await self.async_request_refresh()

    async def async_set_zone_mode(self, zone: int, mode: int) -> None:
        await self._write(zone * 100 + ZONE_HOLD_MODE, mode)
        await self.async_request_refresh()

    async def async_set_flag(self, address: int, on: bool) -> None:
        await self._write(address, 1 if on else 0)
        await self.async_request_refresh()
