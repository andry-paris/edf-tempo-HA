"""Data coordinator for the EDF Tempo integration."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EdfTempoApiError,
    EdfTempoAuthError,
    EdfTempoClient,
    TempoCalendarData,
)
from .const import (
    DOMAIN,
    MIDDAY_POLL_SLOTS,
    MIDDAY_POLL_WINDOW_END,
    MIN_SEASON_START_YEAR,
    OVERNIGHT_POLL_SLOTS,
    OVERNIGHT_POLL_WINDOW_END,
    PARIS_TIME_ZONE,
)
from .season_cache import EdfTempoSeasonCache, TempoSeasonCacheEntry, build_cache_entry

_LOGGER = logging.getLogger(__name__)


class EdfTempoDataUpdateCoordinator(DataUpdateCoordinator[TempoCalendarData]):
    """Coordinate EDF Tempo API updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: EdfTempoClient,
        season_cache: EdfTempoSeasonCache,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            always_update=False,
        )
        self.client = client
        self._season_cache = season_cache
        self._overnight_baseline_date: str | None = None
        self._overnight_baseline: TempoCalendarData | None = None
        self._midday_baseline_date: str | None = None
        self._midday_baseline: TempoCalendarData | None = None

    async def _async_setup(self) -> None:
        """Validate credentials before the first refresh."""
        try:
            await self.client.async_validate_credentials()
            _LOGGER.debug("EDF Tempo credentials validated successfully")
        except EdfTempoAuthError as err:
            _LOGGER.warning("EDF Tempo authentication failed during coordinator setup")
            raise ConfigEntryAuthFailed from err
        except EdfTempoApiError as err:
            _LOGGER.warning("EDF Tempo credential validation failed: %s", err)
            raise UpdateFailed(f"Unable to validate credentials: {err}") from err

    async def _async_update_data(self) -> TempoCalendarData:
        """Fetch data from the EDF Tempo API."""
        previous_data = self.data if self.last_update_success else None
        _LOGGER.debug("Refreshing EDF Tempo coordinator data")
        try:
            day_window = await self.client.async_get_tempo_days()
            season_summary = await self._async_get_current_season_summary(
                day_window.today,
                day_window.tomorrow,
            )
            data = TempoCalendarData(
                today=day_window.today,
                tomorrow=day_window.tomorrow,
                season_summary=season_summary,
                fetched_at=datetime.now(PARIS_TIME_ZONE).isoformat(),
            )
        except EdfTempoAuthError as err:
            _LOGGER.warning("EDF Tempo authentication failed during data refresh")
            raise ConfigEntryAuthFailed from err
        except EdfTempoApiError as err:
            _LOGGER.warning("EDF Tempo data refresh failed: %s", err)
            raise UpdateFailed(f"Unable to fetch Tempo data: {err}") from err

        self.update_interval = self._compute_next_update_interval(data, previous_data)
        _LOGGER.debug(
            "EDF Tempo data refreshed: today=%s tomorrow=%s next_update_in=%ss",
            data.today.color_code,
            data.tomorrow.color_code,
            int(self.update_interval.total_seconds()),
        )

        return data

    async def _async_get_current_season_summary(self, today, tomorrow):
        """Return the current season summary using cache-first logic."""
        _LOGGER.debug(
            "Building current EDF Tempo season summary with today=%s tomorrow=%s",
            today.color_code,
            tomorrow.color_code,
        )
        cache_entry = await self.async_get_season_entry(self.current_season_start_year)
        cache_entry = await self._season_cache.async_update_current_season(
            cache_entry,
            today,
            tomorrow,
        )
        return cache_entry.summary

    async def async_get_season_entry(self, season_start_year: int) -> TempoSeasonCacheEntry:
        """Return a cache entry for the requested season, fetching it on demand if needed."""
        if season_start_year < MIN_SEASON_START_YEAR or season_start_year > self.current_season_start_year:
            raise EdfTempoApiError("Requested season is outside the supported range")

        season_start = datetime(season_start_year, 9, 1, tzinfo=PARIS_TIME_ZONE).date()
        season_end = datetime(season_start_year + 1, 8, 31, tzinfo=PARIS_TIME_ZONE).date()
        season_start_key = season_start.isoformat()

        cache_entry = self._season_cache.get(season_start_key)
        if cache_entry is None:
            _LOGGER.debug("EDF Tempo season cache miss for %s", season_start_key)
            season_day_colors = await self.client.async_get_season_day_colors(season_start, season_end)
            cache_entry = build_cache_entry(
                season_start_key,
                season_end.isoformat(),
                season_day_colors,
            )
            await self._season_cache.async_set(cache_entry)
        else:
            _LOGGER.debug("EDF Tempo season cache hit for %s", season_start_key)

        if (
            season_start_year == self.current_season_start_year
            and self.last_update_success
            and self.data is not None
        ):
            _LOGGER.debug("Refreshing current season cache entry from live day window")
            cache_entry = await self._season_cache.async_update_current_season(
                cache_entry,
                self.data.today,
                self.data.tomorrow,
            )

        return cache_entry

    @property
    def current_season_start_year(self) -> int:
        """Return the current season start year."""
        now = datetime.now(PARIS_TIME_ZONE)
        season_start, _season_end = self.client._get_current_season_bounds(now)
        return season_start.year

    def _compute_next_update_interval(
        self,
        current_data: TempoCalendarData,
        previous_data: TempoCalendarData | None,
    ) -> timedelta:
        """Compute the delay until the next required polling slot."""
        now = datetime.now(PARIS_TIME_ZONE)
        self._refresh_window_baselines(now, current_data, previous_data)

        overnight_changed = self._has_overnight_update(current_data)
        overnight_interval = self._next_slot_delay(
            now,
            OVERNIGHT_POLL_SLOTS,
            OVERNIGHT_POLL_WINDOW_END,
            stop_polling=overnight_changed,
        )
        if overnight_interval is not None:
            _LOGGER.debug(
                "EDF Tempo next update scheduled in overnight window: %ss",
                int(overnight_interval.total_seconds()),
            )
            return overnight_interval

        midday_changed = self._has_midday_update(current_data)
        midday_interval = self._next_slot_delay(
            now,
            MIDDAY_POLL_SLOTS,
            MIDDAY_POLL_WINDOW_END,
            stop_polling=midday_changed,
        )
        if midday_interval is not None:
            _LOGGER.debug(
                "EDF Tempo next update scheduled in midday window: %ss",
                int(midday_interval.total_seconds()),
            )
            return midday_interval

        next_midnight = datetime.combine(
            now.date() + timedelta(days=1),
            OVERNIGHT_POLL_SLOTS[0],
            tzinfo=PARIS_TIME_ZONE,
        )
        next_interval = max(next_midnight - now, timedelta(minutes=1))
        _LOGGER.debug(
            "EDF Tempo next update scheduled for next overnight window in %ss",
            int(next_interval.total_seconds()),
        )
        return next_interval

    def _refresh_window_baselines(
        self,
        now: datetime,
        current_data: TempoCalendarData,
        previous_data: TempoCalendarData | None,
    ) -> None:
        """Capture the pre-window baseline for overnight and midday polling."""
        today_key = now.date().isoformat()

        overnight_end = datetime.combine(
            now.date(), OVERNIGHT_POLL_WINDOW_END, tzinfo=PARIS_TIME_ZONE
        )
        if now <= overnight_end and self._overnight_baseline_date != today_key:
            self._overnight_baseline_date = today_key
            self._overnight_baseline = previous_data or current_data
        elif now > overnight_end and self._overnight_baseline_date != today_key:
            self._overnight_baseline_date = today_key
            self._overnight_baseline = current_data

        midday_start = datetime.combine(now.date(), MIDDAY_POLL_SLOTS[0], tzinfo=PARIS_TIME_ZONE)
        midday_end = datetime.combine(now.date(), MIDDAY_POLL_WINDOW_END, tzinfo=PARIS_TIME_ZONE)
        if midday_start <= now <= midday_end and self._midday_baseline_date != today_key:
            self._midday_baseline_date = today_key
            self._midday_baseline = previous_data or current_data
        elif now > midday_end and self._midday_baseline_date != today_key:
            self._midday_baseline_date = today_key
            self._midday_baseline = current_data

    def _has_overnight_update(self, current_data: TempoCalendarData) -> bool:
        """Return True when the overnight window has produced a new daily state."""
        today_key = datetime.now(PARIS_TIME_ZONE).date().isoformat()
        if self._overnight_baseline is None or self._overnight_baseline_date != today_key:
            return False

        baseline = self._overnight_baseline
        return (
            baseline.today.color_code != current_data.today.color_code
            or baseline.today.date != current_data.today.date
            or baseline.tomorrow.color_code != current_data.tomorrow.color_code
            or baseline.tomorrow.date != current_data.tomorrow.date
        )

    def _has_midday_update(self, current_data: TempoCalendarData) -> bool:
        """Return True when the midday window has produced a new state."""
        today_key = datetime.now(PARIS_TIME_ZONE).date().isoformat()
        if self._midday_baseline is None or self._midday_baseline_date != today_key:
            return False

        baseline = self._midday_baseline
        return (
            baseline.today.color_code != current_data.today.color_code
            or baseline.tomorrow.color_code != current_data.tomorrow.color_code
            or baseline.tomorrow.date != current_data.tomorrow.date
        )

    def _next_slot_delay(
        self,
        now: datetime,
        slots: tuple,
        window_end: time,
        *,
        stop_polling: bool,
    ) -> timedelta | None:
        """Return the delay to the next polling slot for a window."""
        window_end_dt = datetime.combine(now.date(), window_end, tzinfo=PARIS_TIME_ZONE)
        if stop_polling and now <= window_end_dt:
            return None

        slot_datetimes = [
            datetime.combine(now.date(), slot, tzinfo=PARIS_TIME_ZONE) for slot in slots
        ]

        for slot in slot_datetimes:
            if now < slot:
                return slot - now

        if now <= window_end_dt and not stop_polling:
            next_day_first_slot = slot_datetimes[0] + timedelta(days=1)
            return next_day_first_slot - now

        return None
