"""Config flow for Wavin Sentio."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .api import (
    SentioClient,
    SentioConnectionError,
    SentioModbusError,
    async_read_device_info,
)
from .const import (
    CONF_FLOW_SENSOR,
    CONF_HCCS,
    CONF_RETURN_SENSOR,
    CONF_UNIT_ID,
    CONF_ZONES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
)

CONF_SCAN_INTERVAL = "scan_interval"


class SentioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup from the UI."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> SentioOptionsFlow:
        return SentioOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SentioClient(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_UNIT_ID]
            )
            info = None
            try:
                info = await async_read_device_info(
                    client, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except SentioConnectionError:
                errors["base"] = "cannot_connect"
            except SentioModbusError:
                errors["base"] = "modbus_error"
            finally:
                await client.close()

            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )
                return self.async_create_entry(title=info.title, data=user_input)

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): cv.port,
                vol.Required(
                    CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class SentioOptionsFlow(OptionsFlow):
    """Options: which zones to create and polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is None:
            return self.async_abort(reason="not_loaded")

        if user_input is not None:
            data = {
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                CONF_ZONES: sorted(int(z) for z in user_input[CONF_ZONES]),
                CONF_FLOW_SENSOR: user_input[CONF_FLOW_SENSOR],
                CONF_RETURN_SENSOR: user_input[CONF_RETURN_SENSOR],
            }
            if CONF_HCCS in user_input:
                data[CONF_HCCS] = sorted(int(h) for h in user_input[CONF_HCCS])
            return self.async_create_entry(data=data)

        choices = {
            str(n): f"{n}: {name}" for n, name in coordinator.available_zones.items()
        }
        current = [str(z) for z in coordinator.active_zones]
        thermistors = {"none": "-"} | {str(i): f"T{i}" for i in range(1, 6)}
        pair = coordinator.delta_pair()
        flow_default = str(pair[0]) if pair else "none"
        return_default = str(pair[1]) if pair else "none"
        fields: dict = {
            vol.Required(CONF_ZONES, default=current): cv.multi_select(choices),
        }
        if coordinator.available_hccs:
            hcc_choices = {
                str(n): f"HCC{n}: {name}" if name != f"HCC{n}" else f"HCC{n}"
                for n, name in coordinator.available_hccs.items()
            }
            fields[
                vol.Required(CONF_HCCS, default=[str(h) for h in coordinator.hccs])
            ] = cv.multi_select(hcc_choices)
        fields[vol.Required(CONF_FLOW_SENSOR, default=flow_default)] = vol.In(thermistors)
        fields[vol.Required(CONF_RETURN_SENSOR, default=return_default)] = vol.In(
            thermistors
        )
        schema = vol.Schema(
            {
                **fields,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
