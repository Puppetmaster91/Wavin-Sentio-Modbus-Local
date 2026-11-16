# Wavin Sentio (Local Modbus) for Home Assistant

**English** · [Dansk](README.da.md)

Local, cloud-free integration for the **Wavin Sentio** central control unit (CCU-208)
using **Modbus TCP**. Set up from the UI, no YAML needed.

> ## ⚠️ Read this first: AI-written software
>
> This integration was **written by an AI assistant (Claude, by Anthropic)** in a
> conversation with the repository owner, who directed the work and tested it on his own
> installation. It was **not** written or reviewed by a professional developer or by Wavin.
>
> - **It may contain bugs and wrong assumptions.** Register meanings come from Wavin's public
>   Modbus manual, not from Wavin's source code.
> - It has been tested on **one real installation** (see [Tested setup](#tested-setup)) and
>   otherwise only against a simulator. Your setup may behave differently.
> - Parts of the Home Assistant side were never run in a CI environment. Expect rough edges.
> - **This integration can write to your heating controller** (setpoints, modes, standby,
>   vacation). Wrong values can affect comfort and energy use. Start with the controller in
>   *Read only* mode if you are unsure.
> - Provided "as is" under the MIT license, **without any warranty**. Do not rely on it for
>   anything safety-critical (frost protection, flood prevention, and so on). Your controller's
>   own safety functions keep working independently of Home Assistant.
> - **Unofficial.** Not affiliated with, endorsed by, or supported by Wavin or Orbia. Do not
>   contact Wavin support about problems with this integration.
>
> Bug reports and pull requests are very welcome, see [Contributing](#contributing).

## Contents

- [Features](#features)
- [Tested setup](#tested-setup)
- [Requirements](#requirements)
- [Enable Modbus TCP on the Sentio](#enable-modbus-tcp-on-the-sentio)
- [Installation](#installation)
- [Setup](#setup)
- [Devices and entities](#devices-and-entities)
- [Using the integration](#using-the-integration)
- [Options](#options)
- [Removing unused devices](#removing-unused-devices)
- [Reading raw registers (debug action)](#reading-raw-registers-debug-action)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Safety and security](#safety-and-security)
- [Contributing](#contributing)
- [How it was built](#how-it-was-built)
- [License](#license)

## Features

- Fully **local** over Modbus TCP (port 502). No Wavin account, no internet access needed.
- Devices are organised like your installation:
  - one device for the **controller** (`Wavin Sentio CCU#xxxx`),
  - one device **per zone** (named from the zone name stored in the Sentio),
  - one device per **heating circuit (HCC)** that is in use,
  - one device for the **heat source** (boiler / heat pump).
- Zones, circuits and the heat source are **discovered automatically**. Unused ones are not
  created by default and can be switched on or off in the options.
- **Climate entity per zone** with current temperature, target temperature and
  Schedule/Manual mode.
- Thermistor inputs **T1–T5**, outdoor temperature, and a **flow/return ΔT** sensor.
- Pump state, flow temperature, boiler state and error flags.
- Reads are batched, "device busy" answers are retried, and invalid values show as
  *unavailable* instead of strange numbers.
- A debug action to read raw registers, useful for bug reports.
- English and Danish translations.

## Tested setup

The author's installation, for reference:

- Sentio CCU-208, firmware **TM60018.4**, Modbus TCP set to *Slave Read/write*
- 8 zones (two zones share one room sensor, two zones unused), no floor sensors
- Gas boiler with a 3-way valve and a heat exchanger for the floor heating
- Floor heating circuit with its own pump on output P1 (seen by the integration as **HCC1**)
- Flow sensor on **T2**, return sensor on **T3**
- Home Assistant OS

Everything else in the Wavin manual (ITC controllers, domestic hot water, buffer tank,
ventilation, dehumidifiers, cooling) is **not tested** and mostly not implemented, see
[Limitations](#limitations).

## Requirements

- Sentio firmware **TM60014 or newer** (needed for Modbus TCP, according to Wavin's manual).
- Modbus TCP enabled on the controller, see below.
- The controller reachable on your network. Use a **fixed IP** (DHCP reservation in your router).
- Home Assistant **2025.3 or newer**. This minimum is an estimate and has not been verified
  against older releases.
- Optional: [HACS](https://hacs.xyz/) for installation and updates.

## Enable Modbus TCP on the Sentio

Modbus is **off by default**. On the Sentio display:

1. Go to **System → Installer settings → Modbus settings → Modbus TCP**.
2. Choose a mode:
   - **Read only**: monitoring only. Writes from Home Assistant are rejected.
   - **Read/write**: needed to change setpoints, modes, standby and vacation.
   - *Write with password* is **not supported** by this integration (it never sends the
     password), so writes will fail in that mode.
3. Note the controller's IP address (or reserve one in your router). The DHCP hostname is
   `Wavin Sentio CCU#` followed by the last four digits of the serial number.

## Installation

### HACS (custom repository)

1. In Home Assistant open **HACS**, then the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/puppetmaster91/Wavin-Sentio-Modbus-Local` with category **Integration**.
3. Find **Wavin Sentio** in HACS, install it, and **restart Home Assistant**.

### Manual

1. Download this repository.
2. Copy the folder `custom_components/wavin_sentio` into `/config/custom_components/` on
   your Home Assistant (so you get `/config/custom_components/wavin_sentio/`).
3. Restart Home Assistant.

## Setup

1. **Settings → Devices & services → Add integration**, search for **Wavin Sentio**.
2. Enter:
   - **IP address** of the controller,
   - **Port**: `502`,
   - **Modbus unit ID**: `1` (the manual also mentions `255` "if needed", so try that if `1`
     does not answer).
3. The integration reads the controller's serial number, discovers zones and circuits, and
   creates the devices. The title becomes `Wavin Sentio CCU#xxxx`.

Only one entry per controller is allowed. If the IP address changes, adding the same
controller again updates the stored address.

## Devices and entities

Entity IDs are built from the device name and entity name, so yours will differ from the
examples. Entities marked *diagnostic* are hidden from the default dashboard cards; entities
marked *off by default* are created disabled and can be enabled in the entity settings.

### Controller: `Wavin Sentio CCU#xxxx`

| Entity | Type | Notes |
|---|---|---|
| Standby | switch | Controller-wide standby. Writes the Standby register. |
| Vacation | switch | Controller-wide vacation mode. |
| Outdoor temperature | sensor | From the Sentio's outdoor input. |
| Heating/cooling mode | sensor | `heating` or `cooling`. |
| Thermistor input T1–T5 | sensor | Raw temperatures. Only inputs with a connected sensor are enabled by default. Rename them (for example T2 → "Flow"). |
| Flow/return difference | sensor | ΔT in K. Default is **T2 minus T3**. Choose other inputs in the options. |
| Warning / Error | binary sensor, diagnostic | Aggregated flags for the whole system. |

### Zone devices (one per zone)

| Entity | Type | Notes |
|---|---|---|
| *(zone name)* | climate | See [Climate](#climate). |
| Air temperature | sensor | Enabled by default only if the zone reports a value. |
| Humidity | sensor | Same. |
| Floor temperature | sensor | Same. Not created as enabled if you have no floor sensor. |
| Dew point | sensor, diagnostic | |
| Desired temperature | sensor, diagnostic, off by default | The controller's effective target. |
| State | sensor, diagnostic | `idle`, `heating`, `cooling`, `blocked_heating`, `blocked_cooling`. |
| Blocking source | sensor, diagnostic | Why the zone is blocked, for example `contact`, `outdoor_temp`, `deadband`. |
| Warning, Error, Low battery, Peripheral lost | binary sensor, diagnostic | |

Zones that share a room sensor (two zones in one room, for example) each get their own
device. A zone without its own sensor may have *unavailable* air temperature and humidity.
If two zones have the same name, the zone number is added to the device name.

### Heating circuit devices (HCC1–HCC3, only those in use)

| Entity | Type | Notes |
|---|---|---|
| Pump | binary sensor (running) | Pump state as reported by the controller. |
| Pump demand | binary sensor, diagnostic | |
| Flow temperature | sensor | Measured flow temperature of the circuit. |
| Desired flow temperature | sensor | The controller's calculated target (heat curve). |
| Highest desired room temperature | sensor, diagnostic | Enabled only if reported. |
| State, Blocking source | sensor, diagnostic | |
| Warning, Error, Flow sensor failure, High temperature cut-off | binary sensor, diagnostic | |

The Wavin manual has **no registers for the physical pump outputs (P1/P2)**. Pump state is
taken from the heating circuit the pump belongs to.

### Heat source device

Created when the controller reports an H/C source or a boiler/heat pump.

| Entity | Type | Notes |
|---|---|---|
| State (H/C source) | sensor | |
| Boiler state | sensor | `idle`, `heating_active`, `blocked_heating`, `failure` and so on. |
| Requested boiler temperature | sensor | |
| Boiler inlet temperature | sensor | Enabled only if a sensor reports a value. |
| Blocking source | sensor, diagnostic | |
| Warning / Error / Failure flags | binary sensor, diagnostic | Flags the firmware does not provide show as *unknown*. |

## Using the integration

### Climate

Each zone has a climate entity.

- **HVAC modes:** `Heat` = **Manual** mode on the Sentio, `Auto` = **Schedule** mode.
- **Current temperature:** the zone's air temperature.
- **Target temperature:** the controller's **effective** desired temperature. It follows the
  schedule, vacation, standby or temporary override, so it can change by itself.
- **Setting a temperature** from Home Assistant writes the manual setpoint **and switches the
  zone to Manual (Heat)**, because the Sentio ignores the manual setpoint in Schedule mode.
  Switch the zone back to **Auto** to return to the schedule.
- **Step** is 0.5 °C, range 5–35 °C. The controller may round or limit values to its own
  step and limits.
- **Attributes:** `manual_setpoint`, `override` (`none`, `temporary`, `vacation_away`,
  `adjust`), `blocking_source` and `zone`.
- The action is `heating` / `cooling` / `idle` based on the zone's state.

### Standby and vacation

The two switches on the controller device turn the whole system's Standby or Vacation mode
on and off.

### Example: notify on a controller error

```yaml
automation:
  - alias: "Wavin Sentio error"
    triggers:
      - trigger: state
        entity_id: binary_sensor.wavin_sentio_ccu_1234_error   # adjust to your entity
        to: "on"
    actions:
      - action: notify.notify
        data:
          message: "The Wavin Sentio reports an error."
```

### Example: show flow, return and ΔT on a dashboard

Add the three sensors (T2 and T3, renamed, plus *Flow/return difference*) to an entities or
history graph card.

## Options

Open the integration, then the gear icon (**Configure**).

| Option | Description |
|---|---|
| Zones to create | Choose which of the discovered zones become devices. |
| Heating circuits (HCC) to create | Shown only if circuits were discovered. |
| Flow / return thermistor for ΔT | Choose T1–T5, or `-` to disable the ΔT sensor. |
| Update interval | 5–300 seconds. Default 15. Each update makes roughly 30 Modbus requests with a typical setup. |

The integration reloads when you save. **Discovery runs when the integration loads.** If you
connect a new zone or circuit later, reload the integration (⋮ → **Reload**) so it is found,
then select it in the options.

By default a zone is created only if it reports a valid desired temperature, and a circuit
only if it reports a valid flow temperature. That is how unused zones and circuits are kept out.

## Removing unused devices

Devices for zones or circuits you have deselected can be deleted: open the device →
⋮ → **Delete device**. The controller device and all active devices are protected and cannot
be deleted. If you only see *Disable*, the device is still selected in the options.

## Reading raw registers (debug action)

The action `wavin_sentio.read_registers` reads raw Modbus registers and returns them. It is
meant for debugging, for exploring a setup, and for bug reports. It never writes.

Open **Developer tools → Actions**, switch to YAML mode and run, for example:

```yaml
action: wavin_sentio.read_registers
data:
  type: input        # input | holding | discrete
  address: 7701      # register number exactly as printed in Wavin's manual
  count: 8
  individually: true # read one at a time so missing registers do not fail the whole read
```

The response contains `raw` values, and for 16-bit registers also `fp100` (the value divided
by 100, `null` for the invalid marker `0x7FFF`). Missing registers show `error: exception 2`
("illegal data address"), which simply means that register does not exist on your setup.

Register numbers are used **exactly as printed in the manual** (no ±1 offset).

## Troubleshooting

Enable debug logging and include the log in bug reports:

```yaml
logger:
  default: warning
  logs:
    custom_components.wavin_sentio: debug
```

| Problem | What to try |
|---|---|
| "Cannot connect" during setup | Check the IP, that Modbus TCP is enabled on the display, that the firmware is TM60014 or newer, and that port 502 is not blocked. If another Modbus client (Node-RED and so on) is connected, try closing it. This last point is a suggestion and not verified. |
| "The controller answered with a Modbus error" | Try unit ID `255` instead of `1`. |
| Writes fail or have no effect | Modbus mode must be *Read/write* (not *Read only* or *Write with password*). |
| Target temperature does not stick | In Schedule mode the schedule wins. Setting a temperature from Home Assistant switches the zone to Manual, check that this happened. |
| Entities show *unavailable* | The controller returned the invalid marker `0x7FFF`: no sensor connected, or a wireless sensor has not reported yet. For zones sharing a sensor, only the zone that owns it may report values. |
| Zone or circuit missing | It reports no valid value, so it is not selected by default. Select it in the options. For something newly connected, reload the integration first. |
| Occasional short errors or gaps | The controller answers "busy" during start-up and while saving its configuration. The integration retries automatically. |
| Values look wrong or a register is not what you expect | Use the debug action and open an issue. Firmware versions differ, and Wavin says the register list is not final. |
| Entity IDs are not what you expected | IDs come from device and entity names at first creation. Rename entities in the UI. They keep a stable unique ID. |

## Limitations

- **Not implemented:** ITC controllers (73xx/74xx), domestic hot water (Calefa DHW-201 and
  tank), buffer tank controls, ventilation, dehumidifiers, the peripheral list (thermostats
  and sensors with signal strength), writing names, schedules, tuning parameters (heat curve
  and similar), outdoor temperature override, and Modbus *Write with password* mode.
- The registers for these exist in the Wavin manual, so they can be added. Register dumps from
  installations that have them help a lot.
- **Cooling** is only partly handled. The mode is shown, and the climate action can report
  `cooling`, but nobody has tested it. The climate entity offers Heat and Auto only.
- **Dummy rooms** (zones with no thermostat or sensor) are skipped.
- One controller per config entry. Multiple controllers can each be added.
- Update interval is polling-based. There is no push from the controller.
- The Wavin manual says the Modbus interface is **not** meant as a user or installer
  interface, but for monitoring, tuning and restricting users.
- Modbus on the Sentio supports at most 32 registers per read. The integration stays within that.

## Safety and security

- **Modbus TCP has no authentication or encryption.** Anyone who can reach port 502 can read
  and, in *Read/write* mode, change values, without going through Home Assistant. Keep the
  controller on a trusted network or VLAN, and never expose port 502 to the internet.
- Prefer *Read only* if you only want monitoring.
- Changing setpoints and modes affects your heating and energy use. Use Home Assistant
  automations that write to the Sentio with care, and avoid very frequent writes: after changes the
  controller runs a configuration save and may answer "busy" meanwhile.
- Frost protection, high-temperature cut-off and other safety functions run inside the Sentio.
  Do not disable them through any tool.

## Contributing

Bug reports, register dumps and pull requests are welcome.

When opening an issue, please include:

- Sentio firmware version (System information on the display) and controller model
- What hardware is connected (floor heating, radiators, boiler or heat pump, DHW, ventilation)
- Home Assistant version and integration version
- Debug logs from `custom_components.wavin_sentio`
- If relevant, output of `wavin_sentio.read_registers` for the registers in question

Useful register ranges to dump from setups that have them (use `individually: true`):

| What | Type | Start | Count |
|---|---|---|---|
| ITC1 | input / discrete | 7301 / 7301 | 10 / 8 |
| HCC1–HCC3 | input | 7701, 7801, 7901 | 8 |
| H/C source | input | 8101 | 1 |
| Boiler / heat pump | input | 8201 | 4 |
| Buffer tank | input | 8301 | 5 |
| DHW (DHW-201) | input | 6501 | 12 |
| DHW tank | input | 6601 | 8 |
| Ventilation 1 | input | 61001 | 38 |
| Dehumidifier 1 | input | 65001 | 12 |

Please read code changes carefully: this project has no automated tests against real
hardware, so reviews by humans who know the Sentio are valuable.

## How it was built

- Written by **Claude (Anthropic)** from Wavin's public *Sentio Modbus Manual* (August 2024,
  firmware packages 3.2–3.4) and a community forum thread about Sentio on Modbus TCP, directed
  by the repository owner.
- The Modbus layer is a small, dependency-free asyncio client (`api.py`), so it does not
  depend on the `pymodbus` version in your Home Assistant.
- The register logic was tested against a simulated Sentio, including "busy" answers, missing
  registers, invalid values, writes and the author's real register values. The Home Assistant
  platform code (entities, config flow) was syntax-checked and then used on the author's real
  installation, but has no automated test suite.
- Please treat the code as you would any unreviewed third-party code.

## License

[MIT](LICENSE). Wavin and Sentio are trademarks of their respective owners and are used here
only to describe compatibility.
