"""Cover platform for the Time Based Cover integration."""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_UNAVAILABLE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_SOURCE_COVER,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_TRAVEL_TIME,
    DIRECTION_DOWN,
    DIRECTION_UP,
    DOMAIN,
    POSITION_CLOSED,
    POSITION_OPEN,
    SERVICE_SET_KNOWN_POSITION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the time based cover from a config entry."""
    async_add_entities([TimeBasedCover(entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION,
        {
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=POSITION_CLOSED, max=POSITION_OPEN)
            )
        },
        "async_set_known_position",
    )


class TimeBasedCover(CoverEntity, RestoreEntity):
    """A cover whose position is estimated from motor run time."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the cover from the config entry."""
        config = {**entry.data, **entry.options}
        self._source_cover: str = config[CONF_SOURCE_COVER]
        self._travel_time_up = float(config.get(CONF_TRAVEL_TIME_UP, DEFAULT_TRAVEL_TIME))
        self._travel_time_down = float(
            config.get(CONF_TRAVEL_TIME_DOWN, DEFAULT_TRAVEL_TIME)
        )

        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

        # Position when not moving (0 = closed, 100 = open)
        self._position: float = float(POSITION_CLOSED)
        # Movement state
        self._direction: str | None = None
        self._target: int | None = None
        self._move_start_time: float = 0.0
        self._move_start_position: float = 0.0

        self._unsub_finish: CALLBACK_TYPE | None = None
        self._unsub_tick: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore the last known position and track the source cover."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            last_position = last_state.attributes.get(ATTR_CURRENT_POSITION)
            if last_position is not None:
                self._position = float(last_position)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_cover], self._handle_source_state_change
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending timers."""
        self._cancel_timers()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_source_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Update availability when the source cover changes."""
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Available as long as the source cover is available."""
        state = self.hass.states.get(self._source_cover)
        return state is not None and state.state != STATE_UNAVAILABLE

    @property
    def current_cover_position(self) -> int:
        """Return the estimated current position."""
        return round(self._calculate_position())

    @property
    def is_closed(self) -> bool:
        """Return True if the cover is fully closed."""
        return self.current_cover_position == POSITION_CLOSED

    @property
    def is_opening(self) -> bool:
        """Return True if the cover is opening."""
        return self._direction == DIRECTION_UP

    @property
    def is_closing(self) -> bool:
        """Return True if the cover is closing."""
        return self._direction == DIRECTION_DOWN

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose configuration for transparency."""
        return {
            CONF_SOURCE_COVER: self._source_cover,
            CONF_TRAVEL_TIME_UP: self._travel_time_up,
            CONF_TRAVEL_TIME_DOWN: self._travel_time_down,
        }

    def _calculate_position(self) -> float:
        """Calculate the position, taking any ongoing movement into account."""
        if self._direction is None or self._target is None:
            return self._position

        elapsed = time.monotonic() - self._move_start_time
        if self._direction == DIRECTION_UP:
            position = self._move_start_position + elapsed / self._travel_time_up * 100
            return min(position, float(self._target), float(POSITION_OPEN))

        position = self._move_start_position - elapsed / self._travel_time_down * 100
        return max(position, float(self._target), float(POSITION_CLOSED))

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover fully."""
        await self._async_move_to(POSITION_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover fully."""
        await self._async_move_to(POSITION_CLOSED)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._async_move_to(int(kwargs[ATTR_POSITION]))

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover and keep the estimated position."""
        self._freeze_position()
        await self._async_call_source(SERVICE_STOP_COVER)
        self.async_write_ha_state()

    async def async_set_known_position(self, position: int) -> None:
        """Correct the stored position without moving the cover."""
        self._freeze_position()
        self._position = float(position)
        self.async_write_ha_state()

    async def _async_move_to(self, target: int) -> None:
        """Start moving towards a target position."""
        current = self._freeze_position()
        is_end_position = target in (POSITION_OPEN, POSITION_CLOSED)

        if round(current) == target and not is_end_position:
            self.async_write_ha_state()
            return

        if round(current) == target:
            # Already at an end position: send the command anyway to re-sync,
            # the motor stops by itself at its end stop
            direction = DIRECTION_UP if target == POSITION_OPEN else DIRECTION_DOWN
        else:
            direction = DIRECTION_UP if target > current else DIRECTION_DOWN

        travel_time = (
            self._travel_time_up if direction == DIRECTION_UP else self._travel_time_down
        )
        duration = abs(target - current) / 100 * travel_time

        self._direction = direction
        self._target = target
        self._move_start_position = current
        self._move_start_time = time.monotonic()

        await self._async_call_source(
            SERVICE_OPEN_COVER if direction == DIRECTION_UP else SERVICE_CLOSE_COVER
        )

        self._unsub_finish = async_call_later(
            self.hass, duration, self._async_finish_move
        )
        self._unsub_tick = async_track_time_interval(
            self.hass, self._handle_tick, UPDATE_INTERVAL
        )
        self.async_write_ha_state()

    async def _async_finish_move(self, _now: datetime) -> None:
        """Called when the calculated travel time has elapsed."""
        self._unsub_finish = None
        target = self._target
        self._cancel_timers()

        if target is None:
            return

        # At end positions the motor stops by itself
        if target not in (POSITION_OPEN, POSITION_CLOSED):
            await self._async_call_source(SERVICE_STOP_COVER)

        self._position = float(target)
        self._direction = None
        self._target = None
        self.async_write_ha_state()

    @callback
    def _handle_tick(self, _now: datetime) -> None:
        """Push the estimated position while moving."""
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _freeze_position(self) -> float:
        """Stop tracking movement and store the current estimated position."""
        position = self._calculate_position()
        self._cancel_timers()
        self._position = position
        self._direction = None
        self._target = None
        return position

    def _cancel_timers(self) -> None:
        """Cancel the finish timer and the update ticker."""
        if self._unsub_finish is not None:
            self._unsub_finish()
            self._unsub_finish = None
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None

    async def _async_call_source(self, service: str) -> None:
        """Send a command to the source cover."""
        _LOGGER.debug("Calling %s on %s", service, self._source_cover)
        await self.hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._source_cover},
            blocking=False,
        )
