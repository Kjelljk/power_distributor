"""Constants for the Power Distributor integration."""

DOMAIN = "power_distributor"
PLATFORMS = [SENSOR_DOMAIN] # <- NEW: Define the platforms used by this integration

# Configuration Keys (Sensor Entities - Actual Load)
CONF_ENTITY_COMBINED_LOAD = "entity_combined_load"
CONF_ENTITY_UNIT_1 = "entity_unit_1"
CONF_ENTITY_UNIT_2 = "entity_unit_2"
CONF_ENTITY_UNIT_3 = "entity_unit_3"
CONF_ENTITY_UNIT_4 = "entity_unit_4"

# Configuration Keys (Parameters - Limits)
CONF_MAX_COMBINED_LOAD = "max_combined_load"       # X (System hard limit)
CONF_MAX_INDIVIDUAL_LOAD = "max_individual_load"   # Y (Individual hard cap)

# Configuration Keys (Parameters - Overload Acceptance Tuning)
# All values are in Minutes
CONF_DELAY_5_PERCENT = "delay_5_percent"           # Time (T_delay) allowed at 5% overload before OA starts dropping
CONF_DELAY_20_PERCENT = "delay_20_percent"         # Time (T_delay) allowed at 20% overload before OA starts dropping
CONF_RAMP_5_PERCENT = "ramp_5_percent"             # Time (T_ramp) to ramp limit down from overload to X (at 5% overload trigger)
CONF_RAMP_20_PERCENT = "ramp_20_PERCENT"           # Time (T_ramp) to ramp limit down from overload to X (at 20% overload trigger)
CONF_RECOVERY_TIME_FAST = "recovery_time_fast"     # Time (T_recover) for OA to recover 0->100% when 20% UNDER load
CONF_RECOVERY_TIME_SLOW = "recovery_time_slow"     # Time (T_recover) for OA to recover 0->100% when at RATED load

# Default Values (used in config_flow)
DEFAULT_MAX_COMBINED_LOAD = 16.0
DEFAULT_MAX_INDIVIDUAL_LOAD = 4.0
DEFAULT_DELAY_5_PERCENT = 10.0
DEFAULT_DELAY_20_PERCENT = 2.0
DEFAULT_RAMP_5_PERCENT = 10.0
DEFAULT_RAMP_20_PERCENT = 5.0
DEFAULT_RECOVERY_TIME_FAST = 20.0
DEFAULT_RECOVERY_TIME_SLOW = 60.0

# General
NUM_CONSUMERS = 4
SCAN_INTERVAL_SECONDS = 5
