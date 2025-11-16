"""Power Distributor Sensor platform that implements the proportional load distribution 
with time-based Overload Acceptance (OA) state machine logic."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    DOMAIN,
    CONF_ENTITY_COMBINED_LOAD,
    CONF_ENTITY_UNIT_1,
    CONF_ENTITY_UNIT_2,
    CONF_ENTITY_UNIT_3,
    CONF_ENTITY_UNIT_4,
    CONF_MAX_COMBINED_LOAD,
    CONF_MAX_INDIVIDUAL_LOAD,
    CONF_DELAY_5_PERCENT,
    CONF_DELAY_20_PERCENT,
    CONF_RAMP_5_PERCENT,
    CONF_RAMP_20_PERCENT,
    CONF_RECOVERY_TIME_FAST,
    CONF_RECOVERY_TIME_SLOW,
    NUM_CONSUMERS,
    SCAN_INTERVAL_SECONDS
)

_LOGGER = logging.getLogger(__name__)

# --- Helper Function ---
def get_float_state(state: State | None) -> float | None:
    """Safely converts a state value to a float."""
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        # Attempt to handle common string inputs (stripping units or fixing commas is safer in the config flow,
        # but a clean float conversion is used here.)
        return float(state.state)
    except (ValueError, TypeError):
        return None

def _interpolate_value(x: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Linear interpolation between two points (x1, y1) and (x2, y2)."""
    if x1 == x2: 
        return y1 
    if x <= x1: 
        return y1
    if x >= x2: 
        return y2
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)


# --- Power Management (OA State Machine) ---

class PowerManagement:
    """Manages the shared time-dependent state (OA) and overload logic for combined and individual loads."""

    def __init__(self, hass: HomeAssistant, config: dict):
        """Initialize the Power Management with dynamic configuration."""
        self.hass = hass
        self._config = config
        
        # Limits
        self.max_combined_load = config[CONF_MAX_COMBINED_LOAD]
        self.max_individual_load = config[CONF_MAX_INDIVIDUAL_LOAD]
        
        # Tuning Parameters (in minutes)
        self._delay_5 = config[CONF_DELAY_5_PERCENT]
        self._delay_20 = config[CONF_DELAY_20_PERCENT]
        self._ramp_5 = config[CONF_RAMP_5_PERCENT]
        self._ramp_20 = config[CONF_RAMP_20_PERCENT]
        self._recover_fast = config[CONF_RECOVERY_TIME_FAST]
        self._recover_slow = config[CONF_RECOVERY_TIME_SLOW]

        # Shared OA State variables for Combined Load
        self._combined_oa = 100.0
        self._combined_ramp_start = None
        self._combined_ramp_dur = None
        self._combined_init_factor = 1.0
        
        # Shared OA State variables for Individual Consumers (list of dictionaries)
        self._consumer_oa_states = [
            {'oa': 100.0, 'ramp_start': None, 'init_factor': 1.0, 'ramp_dur': None}
            for _ in range(NUM_CONSUMERS)
        ]
        self._last_update_time = datetime.now()


    def _calculate_oa_timing(self, overload_ratio: float) -> tuple[float, float]:
        """Calculates T_delay and T_ramp based on overload ratio (capped at 1.20). Returns (T_delay, T_ramp) in minutes."""
        ratio = min(1.20, overload_ratio)
        
        T_delay = _interpolate_value(ratio, 1.05, self._delay_5, 1.20, self._delay_20)
        T_ramp = _interpolate_value(ratio, 1.05, self._ramp_5, 1.20, self._ramp_20)
        
        return T_delay, T_ramp

    def _calculate_recovery_time(self, load_ratio: float) -> float:
        """Calculates T_recover (time in minutes for OA to go from 0 to 100)."""
        # Interpolates between 20% under-load (0.80) and rated load (1.00)
        return _interpolate_value(load_ratio, 0.80, self._recover_fast, 1.00, self._recover_slow)


    def _update_oa_state(self, current_load: float, reference_limit: float, state: dict, time_delta_min: float) -> float:
        """Generic OA state machine update. Returns the current limit factor (>=1.0 accepted, <1.0 ramping)."""
        now = datetime.now()
        
        # Avoid division by zero
        if reference_limit <= 0: return 1.0 
        
        overload_ratio = current_load / reference_limit
        
        if current_load <= reference_limit:
            # --- RECOVERY (Load <= Limit) ---
            state['ramp_start'] = None
            
            # Recovery rate based on how far under the limit the load is (0.8 to 1.0)
            load_ratio = max(0.0, min(1.0, current_load / reference_limit)) 
            T_recover = self._calculate_recovery_time(load_ratio)
            
            rate_rise_per_min = 100.0 / T_recover if T_recover > 0 else 100.0 
            state['oa'] = min(100.0, state['oa'] + rate_rise_per_min * time_delta_min)
            
            # In recovery phase, the limit factor is 1.0 (or higher if the load is > X but accepted)
            return max(1.0, overload_ratio) 
            
        else:
            # --- CONSUMPTION (Load > Limit) ---
            T_delay, T_ramp = self._calculate_oa_timing(overload_ratio)
            rate_consume_per_min = 100.0 / T_delay if T_delay > 0 else 100.0

            state['oa'] = max(0.0, state['oa'] - rate_consume_per_min * time_delta_min)

            if state['oa'] > 0:
                # Still in Accepted Overload Phase (OA > 0): No limiting applied yet.
                state['ramp_start'] = None
                return overload_ratio # Limit factor is the actual overload ratio (e.g., 1.15)

            else:
                # --- LIMITING (Ramping Down) Phase (OA <= 0) ---
                
                if state['ramp_start'] is None:
                    # Start of the down-ramping process
                    state['ramp_start'] = now
                    state['ramp_dur'] = T_ramp
                    state['init_factor'] = overload_ratio
                
                time_elapsed_min = (now - state['ramp_start']).total_seconds() / 60.0
                ramp_progress = min(1.0, time_elapsed_min / state['ramp_dur'])
                
                # Interpolate the limit factor from initial_overload_ratio down to 1.0
                current_limit_factor = state['init_factor'] - \
                                      (state['init_factor'] - 1.0) * ramp_progress
                                      
                if ramp_progress >= 1.0:
                    state['oa'] = 0.0 # Keep OA at 0 during steady limiting
                    return 1.0
                
                return current_limit_factor

    def run_distribution(self, L_combined_actual: float, L_units_actual: list[float]) -> dict[str, Any]:
        """
        Runs the main logic, updates OA states, and calculates final proportional limits.
        """
        now = datetime.now()
        time_delta_sec = (now - self._last_update_time).total_seconds()
        time_delta_min = time_delta_sec / 60.0
        self._last_update_time = now
        
        L_units_total = sum(L_units_actual)
        L_unmanaged_actual = max(0.0, L_combined_actual - L_units_total)

        # 1. --- Update COMBINED Overload Acceptance (OA_X) ---
        combined_oa_state = {
            'oa': self._combined_oa, 'ramp_start': self._combined_ramp_start,
            'init_factor': self._combined_init_factor, 'ramp_dur': self._combined_ramp_dur
        }

        # Calculate factor based on total combined load vs max combined load
        combined_limit_factor = self._update_oa_state(
            L_combined_actual, self.max_combined_load, combined_oa_state, time_delta_min
        )
        
        # Update shared state variables
        self._combined_oa = combined_oa_state['oa']
        self._combined_ramp_start = combined_oa_state['ramp_start']
        self._combined_init_factor = combined_oa_state['init_factor']
        self._combined_ramp_dur = combined_oa_state['ramp_dur']
        
        # Determine the COMBINED limit imposed by the OA logic
        if combined_limit_factor > 1.0:
            # In Delay phase: Limit is high (actual load)
            current_combined_limit = L_combined_actual
        else:
            # In Ramping/Limiting phase: Limit is X * factor
            current_combined_limit = self.max_combined_load * combined_limit_factor

        # Capacity available for distribution among the 4 MANAGED consumers
        X_managed_capacity = max(0.0, current_combined_limit - L_unmanaged_actual)

        # 2. --- Update INDIVIDUAL Overload Acceptance (OA_Y) ---
        
        pre_capped_requests = []
        individual_oa_percents = []

        for i, requested_load in enumerate(L_units_actual):
            consumer_state = self._consumer_oa_states[i]

            # Individual OA logic: Based on actual request vs individual limit (Y)
            individual_limit_factor = self._update_oa_state(
                requested_load, self.max_individual_load, consumer_state, time_delta_min
            )
            
            individual_oa_percents.append(round(consumer_state['oa'], 2))

            # Unit's maximum capacity cap imposed by its OA state
            consumer_oa_cap = self.max_individual_load * individual_limit_factor
            
            # The request for the proportional splitter is capped by: (1) OA limit, (2) Hard cap Y
            pre_capped_request = min(requested_load, consumer_oa_cap)
            
            pre_capped_requests.append(pre_capped_request)

        L_units_pre_capped_total = sum(pre_capped_requests)

        # 3. --- Proportional Distribution ---
        final_limits = [0.0] * NUM_CONSUMERS
        
        if X_managed_capacity >= L_units_pre_capped_total:
            # Enough capacity: Units get their OA-capped request (which is also capped by Y)
            final_limits = pre_capped_requests
        else:
            # Capacity shortage: Apply proportional limiting based on available capacity
            if L_units_pre_capped_total > 0:
                scaling_factor = X_managed_capacity / L_units_pre_capped_total
                final_limits = [load * scaling_factor for load in pre_capped_requests]
        
        # Final result structure
        return {
            "combined_oa_percent": round(self._combined_oa, 2),
            "current_combined_limit_A": round(current_combined_limit, 2),
            "available_managed_capacity_A": round(X_managed_capacity, 2),
            "individual_oa_percents": individual_oa_percents,
            "final_limits_A": [round(l, 2) for l in final_limits],
            "units_pre_capped_demand_A": [round(r, 2) for r in pre_capped_requests],
        }

# --- Home Assistant Sensors ---

class PowerDistributorSensor(SensorEntity):
    """Base class for all 5 sensors (1 combined, 4 units)."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = "A" # The main state will be the actual load
    _attr_should_poll = False
    
    def __init__(self, entry_id: str, index: int, source_entity_id: str, name: str, is_combined: bool = False):
        """Initialize the sensor."""
        self._source_entity_id = source_entity_id
        self._is_combined = is_combined
        self._index = index
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{name.lower().replace(' ', '_')}"
        self._last_result = {} # Stores the result dict from PowerManagement
        self._last_actual_load: float | None = None
        self._state_is_valid = True

    @property
    def native_value(self) -> State | None:
        """Return the actual load (A) of the source entity."""
        return self._last_actual_load
    
    @property
    def available(self) -> bool:
        """Return True if entity is available and state is valid."""
        return self._last_actual_load is not None and self._state_is_valid

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the calculated limits and OA status as attributes."""
        attrs = {
            "source_entity_id": self._source_entity_id,
        }
        
        if not self._last_result:
            attrs['status'] = "Initializing"
            return attrs

        if self._is_combined:
            # Combined Load Attributes
            attrs.update({
                "calculated_limit_combined_A": self._last_result.get("current_combined_limit_A"),
                "combined_oa_percent": self._last_result.get("combined_oa_percent"),
                "max_combined_load_x": self.hass.data[DOMAIN]['manager'].max_combined_load,
                "available_managed_capacity_A": self._last_result.get("available_managed_capacity_A"),
            })
        else:
            # Individual Unit Attributes
            attrs.update({
                "calculated_limit_unit_A": self._last_result['final_limits_A'][self._index],
                "individual_oa_percent": self._last_result['individual_oa_percents'][self._index],
                "max_individual_load_y": self.hass.data[DOMAIN]['manager'].max_individual_load,
            })
        
        # Add friendly status based on the load vs the current calculated limit
        current_limit = attrs.get("calculated_limit_unit_A", attrs.get("calculated_limit_combined_A"))
        if self._last_actual_load is not None and current_limit is not None and self._last_actual_load > current_limit + 0.01:
             attrs['control_status'] = "Limit Exceeded"
        else:
             attrs['control_status'] = "Limit Enforced"

        return attrs

    async def async_added_to_hass(self) -> None:
        """Register state change listeners."""
        # Listen only to changes in its own source entity to update its state
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_entity_id], self._state_change_listener
            )
        )
        # Initial run
        await self.async_update()
        
    @callback
    def _state_change_listener(self, event) -> None:
        """Handle state changes and trigger an update."""
        self.async_schedule_update_ha_state(True)
        
    async def async_update(self) -> None:
        """Update the sensor's actual load state."""
        new_state = self.hass.states.get(self._source_entity_id)
        
        self._last_actual_load = get_float_state(new_state)
        
        if self._last_actual_load is None:
            self._state_is_valid = False
        else:
            self._state_is_valid = True

        # All sensors rely on the main controller to run the calculation first
        self._last_result = self.hass.data[DOMAIN].get('latest_results', {})


# --- Main Setup and Controller Logic ---

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Power Distributor Sensor platform from a config entry."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    
    # 1. Initialize the shared Power Management logic (the "Brain")
    manager = PowerManagement(hass, data)
    hass.data[DOMAIN]['manager'] = manager
    hass.data[DOMAIN]['latest_results'] = {}

    # 2. Create Output Sensors
    sensors = []
    
    # Combined Load Sensor
    sensors.append(
        PowerDistributorSensor(
            config_entry.entry_id, -1, data[CONF_ENTITY_COMBINED_LOAD], "Combined Load Status", True
        )
    )

    # Individual Unit Sensors (4 units)
    unit_keys = [CONF_ENTITY_UNIT_1, CONF_ENTITY_UNIT_2, CONF_ENTITY_UNIT_3, CONF_ENTITY_UNIT_4]
    for i, entity_key in enumerate(unit_keys):
        sensors.append(
            PowerDistributorSensor(
                config_entry.entry_id, i, data[entity_key], f"Unit {i+1} Status"
            )
        )
    
    async_add_entities(sensors)

    # 3. Setup the Update Runner
    
    @callback
    async def async_run_controller(now):
        """Runs the Power Management logic and updates all sensor states."""
        
        # --- Gather all inputs ---
        combined_state = hass.states.get(data[CONF_ENTITY_COMBINED_LOAD])
        L_combined_actual = get_float_state(combined_state)
        
        L_units_actual = []
        for entity_key in unit_keys:
            unit_state = hass.states.get(data[entity_key])
            load = get_float_state(unit_state)
            L_units_actual.append(load if load is not None else 0.0)
            
        # Check if critical input (combined load) is valid
        if L_combined_actual is None:
            _LOGGER.warning("Combined load input is unavailable. Halting distribution calculation.")
            return

        # --- Run Logic ---
        try:
            results = manager.run_distribution(L_combined_actual, L_units_actual)
            hass.data[DOMAIN]['latest_results'] = results
            
            # Request all sensor entities to update their states and attributes
            for entity in sensors:
                entity.async_schedule_update_ha_state(True)
                
        except Exception as e:
            _LOGGER.error(f"Error during power distribution calculation: {e}", exc_info=True)


    # Run controller periodically (heartbeat) and whenever an entity state changes
    hass.data[DOMAIN]['controller_update_listener'] = async_track_time_interval(
        hass, async_run_controller, timedelta(seconds=SCAN_INTERVAL_SECONDS)
    )
    
    # Initial run to populate the state immediately
    await async_run_controller(datetime.now())