"""Config flow for the Time Based Cover integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_SOURCE_COVER,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_TRAVEL_TIME,
    DOMAIN,
    MAX_TRAVEL_TIME,
    MIN_TRAVEL_TIME,
)

TRAVEL_TIME_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=MIN_TRAVEL_TIME,
        max=MAX_TRAVEL_TIME,
        step=0.5,
        unit_of_measurement="s",
        mode=selector.NumberSelectorMode.BOX,
    )
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_COVER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=COVER_DOMAIN)
        ),
        vol.Required(
            CONF_TRAVEL_TIME_UP, default=DEFAULT_TRAVEL_TIME
        ): TRAVEL_TIME_SELECTOR,
        vol.Required(
            CONF_TRAVEL_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
        ): TRAVEL_TIME_SELECTOR,
    }
)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): selector.TextSelector()}
).extend(OPTIONS_SCHEMA.schema)


class TimeBasedCoverConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a time based cover."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for name, source cover and travel times."""
        if user_input is not None:
            # Only one time based cover per source cover
            self._async_abort_entries_match(
                {CONF_SOURCE_COVER: user_input[CONF_SOURCE_COVER]}
            )
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data={}, options=user_input)

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return TimeBasedCoverOptionsFlow()


class TimeBasedCoverOptionsFlow(OptionsFlow):
    """Allow changing source cover and travel times after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
