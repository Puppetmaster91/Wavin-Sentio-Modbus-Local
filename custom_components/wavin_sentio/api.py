"""Minimal async Modbus TCP client and decoders for the Wavin Sentio CCU.

No Home Assistant imports here so the module can be tested standalone.
Register numbers are used exactly as printed in the Wavin Sentio Modbus
manual (no +/-1 offset).
"""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

# Modbus function codes supported by Sentio
FC_READ_DISCRETE = 0x02
FC_READ_HOLDING = 0x03
FC_READ_INPUT = 0x04
FC_WRITE_SINGLE = 0x06
FC_WRITE_MULTIPLE = 0x10

# Exception codes
EXC_ILLEGAL_FUNCTION = 1
EXC_ILLEGAL_ADDRESS = 2
EXC_ILLEGAL_VALUE = 3
EXC_DEVICE_FAILURE = 4
EXC_BUSY = 6

MAX_REGISTERS = 32  # manual: max 32 registers (or 256 bits) per read
BUSY_RETRIES = 3

INVALID_FP100 = 0x7FFF

# Zone state (input register base+2)
ZONE_STATES = {
    1: "idle",
    2: "heating",
    3: "cooling",
    4: "blocked_heating",
    5: "blocked_cooling",
}

# Boiler / heat pump state (input register 8201)
BOILER_STATES = {
    1: "idle",
    2: "heating_prepare",
    3: "heating_active",
    4: "heating_terminate",
    5: "cooling_prepare",
    6: "cooling_active",
    7: "cooling_terminate",
    8: "blocked_heating",
    9: "blocked_cooling",
    10: "failure",
}

# General blocking sources (manual, table 1)
BLOCKING_SOURCES = {
    0: "none",
    1: "unknown",
    2: "contact",
    3: "floor_temp",
    4: "low_energy",
    5: "air_temp",
    6: "dew_point",
    7: "outdoor_temp",
    8: "fault",
    9: "fault_htco",
    10: "periodic_activation",
    11: "bms",
    12: "deadband",
    13: "drying",
    14: "heating_cooling_mode",
    15: "insufficient_demand",
    16: "cooldown_period",
    17: "hcw_source_not_released",
    18: "room_mode",
    19: "system_initializing",
    20: "system_shutting_down",
    21: "no_output",
    22: "first_open_activation",
    23: "room_with_no_temperature",
}

DEVICE_TYPES = {1: "CCU-208", 2: "DHW-201"}


class SentioError(Exception):
    """Base error."""


class SentioConnectionError(SentioError):
    """Could not talk to the controller (network, timeout, protocol)."""


class SentioModbusError(SentioError):
    """The controller answered with a Modbus exception."""

    def __init__(self, code: int, function: int) -> None:
        super().__init__(f"Modbus exception {code} for function 0x{function:02X}")
        self.code = code
        self.function = function


# ---------------------------------------------------------------- decoders
def decode_fp100(raw: int) -> float | None:
    """val_d2_fp100: signed 16 bit / 100, 0x7FFF = invalid."""
    if raw == INVALID_FP100:
        return None
    if raw >= 0x8000:
        raw -= 0x10000
    return raw / 100


def encode_fp100(value: float) -> int:
    """Encode a float as unsigned register value (two's complement)."""
    raw = round(value * 100)
    if not -32768 <= raw <= 32767:
        raise ValueError(f"Value {value} out of range")
    return raw & 0xFFFF


def decode_u1(raw: int) -> int | None:
    """val_u1 / val_enum: 0..255, 0xFF = invalid."""
    if raw in (0xFF, 0xFFFF):
        return None
    return raw


def decode_string(registers: list[int]) -> str:
    """val_utf8: bytes packed big-endian into registers, NULL terminated."""
    data = b"".join(r.to_bytes(2, "big") for r in registers)
    data = data.split(b"\x00", 1)[0]
    return data.decode("utf-8", errors="replace").strip()


# ------------------------------------------------------------------ client
class SentioClient:
    """Tiny Modbus TCP client (one request in flight at a time)."""

    def __init__(
        self, host: str, port: int = 502, unit_id: int = 1, timeout: float = 5.0
    ) -> None:
        self._host = host
        self._port = port
        self._unit = unit_id
        self._timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._tid = 0

    # -- connection handling
    async def _ensure_connected(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), self._timeout
            )
        except (OSError, TimeoutError) as err:
            self._reader = self._writer = None
            raise SentioConnectionError(
                f"Cannot connect to {self._host}:{self._port}: {err}"
            ) from err

    async def _disconnect(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def close(self) -> None:
        """Close the connection."""
        async with self._lock:
            await self._disconnect()

    # -- low level
    async def _transact(self, function: int, data: bytes) -> bytes:
        await self._ensure_connected()
        assert self._reader is not None and self._writer is not None

        self._tid = (self._tid + 1) & 0xFFFF
        pdu = bytes([function]) + data
        frame = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self._unit) + pdu

        try:
            self._writer.write(frame)
            await self._writer.drain()
            header = await asyncio.wait_for(
                self._reader.readexactly(7), self._timeout
            )
            tid, proto, length, _unit = struct.unpack(">HHHB", header)
            if proto != 0 or not 2 <= length <= 260:
                raise SentioConnectionError("Invalid Modbus TCP header")
            body = await asyncio.wait_for(
                self._reader.readexactly(length - 1), self._timeout
            )
        except SentioConnectionError:
            await self._disconnect()
            raise
        except (OSError, TimeoutError, asyncio.IncompleteReadError) as err:
            await self._disconnect()
            raise SentioConnectionError(f"Communication error: {err!r}") from err

        if tid != self._tid:
            await self._disconnect()
            raise SentioConnectionError("Transaction id mismatch")

        fc = body[0]
        if fc & 0x80:
            raise SentioModbusError(body[1] if len(body) > 1 else 0, fc & 0x7F)
        if fc != function:
            await self._disconnect()
            raise SentioConnectionError("Unexpected function code in response")
        return body[1:]

    async def _request(self, function: int, data: bytes) -> bytes:
        async with self._lock:
            for attempt in range(BUSY_RETRIES + 1):
                try:
                    return await self._transact(function, data)
                except SentioModbusError as err:
                    # 06 = server busy (start-up or saving configuration)
                    if err.code == EXC_BUSY and attempt < BUSY_RETRIES:
                        _LOGGER.debug("Sentio busy, retrying (%s)", attempt + 1)
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    raise
        raise SentioConnectionError("unreachable")  # pragma: no cover

    # -- reads
    async def read_discrete(self, address: int, count: int) -> list[bool]:
        """Read discrete inputs (FC 02)."""
        if not 1 <= count <= 256:
            raise ValueError("count out of range")
        resp = await self._request(
            FC_READ_DISCRETE, struct.pack(">HH", address, count)
        )
        nbytes = resp[0]
        if len(resp) < 1 + nbytes or nbytes * 8 < count:
            raise SentioConnectionError("Short discrete response")
        bits = int.from_bytes(resp[1 : 1 + nbytes], "little")
        return [bool(bits >> i & 1) for i in range(count)]

    async def _read_regs(self, function: int, address: int, count: int) -> list[int]:
        if not 1 <= count <= MAX_REGISTERS:
            raise ValueError("count out of range (max 32)")
        resp = await self._request(function, struct.pack(">HH", address, count))
        if len(resp) < 1 + count * 2 or resp[0] != count * 2:
            raise SentioConnectionError("Short register response")
        return list(struct.unpack(f">{count}H", resp[1 : 1 + count * 2]))

    async def read_input(self, address: int, count: int = 1) -> list[int]:
        """Read input registers (FC 04)."""
        return await self._read_regs(FC_READ_INPUT, address, count)

    async def read_holding(self, address: int, count: int = 1) -> list[int]:
        """Read holding registers (FC 03)."""
        return await self._read_regs(FC_READ_HOLDING, address, count)

    # -- writes
    async def write_register(self, address: int, value: int) -> None:
        """Write one holding register (FC 06)."""
        await self._request(FC_WRITE_SINGLE, struct.pack(">HH", address, value & 0xFFFF))

    async def write_registers(self, address: int, values: list[int]) -> None:
        """Write several holding registers (FC 16)."""
        if not 1 <= len(values) <= 16:
            raise ValueError("too many registers")
        payload = struct.pack(">HHB", address, len(values), len(values) * 2)
        payload += struct.pack(f">{len(values)}H", *[v & 0xFFFF for v in values])
        await self._request(FC_WRITE_MULTIPLE, payload)


# ------------------------------------------------------------ device info
@dataclass(frozen=True)
class SentioInfo:
    """Static information about the controller."""

    dev_type: int
    hw_version: int
    sw_version: int
    sw_minor: int
    serial_prefix: int
    serial: int | None
    host: str
    port: int

    @property
    def model(self) -> str:
        return DEVICE_TYPES.get(self.dev_type, "CCU")

    @property
    def unique_id(self) -> str:
        if self.serial is None:
            return f"{self.host}_{self.port}"
        return f"{self.serial_prefix}{self.serial}"

    @property
    def short_serial(self) -> str:
        """Last four digits, as used by Wavin for the DHCP hostname."""
        if self.serial is None:
            return "????"
        return f"{self.serial % 10000:04d}"

    @property
    def title(self) -> str:
        return f"Wavin Sentio CCU#{self.short_serial}"


async def async_read_device_info(client: SentioClient, host: str, port: int) -> SentioInfo:
    """Read dev type, versions and serial (input registers 10-16)."""
    regs = await client.read_input(10, 7)
    serial = (regs[5] << 16) | regs[6]
    return SentioInfo(
        dev_type=regs[0],
        hw_version=regs[1],
        sw_version=regs[2],
        sw_minor=regs[3],
        serial_prefix=regs[4],
        serial=None if serial == 0xFFFFFFFF else serial,
        host=host,
        port=port,
    )
