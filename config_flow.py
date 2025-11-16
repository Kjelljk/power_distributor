"""Config flow for Power Distributor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME

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
    DEFAULT_MAX_COMBINED_LOAD,
    DEFAULT_MAX_INDIVIDUAL_LOAD,
    DEFAULT_DELAY_5_PERCENT,
    DEFAULT_DELAY_20_PERCENT,
    DEFAULT_RAMP_5_PERCENT,
    DEFAULT_RAMP_20_PERCENT,
    DEFAULT_RECOVERY_TIME_FAST,
    DEFAULT_RECOVERY_TIME_SLOW,
)

_LOGGER = logging.getLogger(__name__)

# Schema for Step 1: Entities and Main Limits
STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default="Power Distributor"): str,
    # Entity Inputs
    vol.Required(CONF_ENTITY_COMBINED_LOAD): str,
    vol.Required(CONF_ENTITY_UNIT_1): str,
    vol.Required(CONF_ENTITY_UNIT_2): str,
    vol.Required(CONF_ENTITY_UNIT_3): str,
    vol.Required(CONF_ENTITY_UNIT_4): str,
    # Parameter Inputs (Coerced to float)
    vol.Required(CONF_MAX_COMBINED_LOAD, default=DEFAULT_MAX_COMBINED_LOAD): vol.Coerce(float),
    vol.Required(CONF_MAX_INDIVIDUAL_LOAD, default=DEFAULT_MAX_INDIVIDUAL_LOAD): vol.Coerce(float),
})

# Schema for Step 2: OA Tuning Parameters (All Coerced to float, in Minutes)
STEP_TUNING_SCHEMA = vol.Schema({
    vol.Required(CONF_DELAY_5_PERCENT, default=DEFAULT_DELAY_5_PERCENT): vol.Coerce(float),
    vol.Required(CONF_DELAY_20_PERCENT, default=DEFAULT_DELAY_20_PERCENT): vol.Coerce(float),
    vol.Required(CONF_RAMP_5_PERCENT, default=DEFAULT_RAMP_5_PERCENT): vol.Coerce(float),
    vol.Required(CONF_RAMP_20_PERCENT, default=DEFAULT_RAMP_20_PERCENT): vol.Coerce(float),
    vol.Required(CONF_RECOVERY_TIME_FAST, default=DEFAULT_RECOVERY_TIME_FAST): vol.Coerce(float),
    vol.Required(CONF_RECOVERY_TIME_SLOW, default=DEFAULT_RECOVERY_TIME_SLOW): vol.Coerce(float),
})


class PowerDistributorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Power Distributor."""

    VERSION = 1
    _user_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step (Entities and Main Limits)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_MAX_COMBINED_LOAD] <= 0 or user_input[CONF_MAX_INDIVIDUAL_LOAD] <= 0:
                errors["base"] = "positive_limits_required"
            
            if not errors:
                self._user_data.update(user_input)
                return await self.async_step_tuning()

        return self.async_show_form(
            step_id="user", 
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, self._user_data), 
            errors=errors
        )

    async def async_step_tuning(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the second step (OA Tuning Parameters)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._user_data.update(user_input)
            
            # Final data compilation
            final_data = self._user_data
            
            # Create the entry
            return self.async_create_entry(
                title=final_data[CONF_NAME], 
                data=final_data
            )

        return self.async_show_form(
            step_id="tuning", 
            data_schema=self.add_suggested_values_to_schema(STEP_TUNING_SCHEMA, self._user_data), 
            errors=errors,
            description_placeholders={"description": "Set the time constants (in minutes) for Overload Acceptance (OA) recovery and ramp-down."}
        )