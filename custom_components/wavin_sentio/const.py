"""Constants for the Wavin Sentio integration."""

DOMAIN = "wavin_sentio"

CONF_UNIT_ID = "unit_id"
CONF_ZONES = "zones"
CONF_HCCS = "hccs"
CONF_FLOW_SENSOR = "flow_sensor"
CONF_RETURN_SENSOR = "return_sensor"

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 15  # seconds
MAX_ZONES = 16

MODE_SCHEDULE = 0
MODE_MANUAL = 1

# Register layout (numbers as printed in the Wavin manual).
# Zone N uses base = N * 100.
ZONE_IN_DESIRED = 1      # input  base+1  (desired temp, effective)
ZONE_IN_ROOM_TYPE = 27   # input  base+27 (0 normal, 1 dummy)
ZONE_HOLD_NAME = 1       # holding base+1 .. base+16 (utf8 name)
ZONE_HOLD_MODE = 17      # holding base+17 (0 schedule, 1 manual)
ZONE_HOLD_SETPOINT = 19  # holding base+19 (fp100)
ZONE_DISC_FIRST = 1      # discrete base+1 .. base+4

LOC_HOLD_STANDBY = 26
LOC_HOLD_VACATION = 27
LOC_IN_HC_MODE = 20
OUTDOOR_IN_TEMP = 3301

THERMISTOR_IN_FIRST = 12801  # input 12801..12805 = T1..T5 (fp100)
THERMISTOR_COUNT = 5

# Heating/cooling controllers HCC1-3: base 7700 / 7800 / 7900
HCC_BASES = {1: 7700, 2: 7800, 3: 7900}
SOURCE_IN_STATE = 8101   # H/C source state; discrete 8101-8103
BOILER_IN_FIRST = 8201   # boiler/heat pump input 8201-8204; discrete 8201-8204
BOILER_HOLD_NAME = 8201  # holding 8201-8216 (utf8 name)
