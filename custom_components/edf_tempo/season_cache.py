"""Season summary caching for EDF Tempo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import TempoDayData, TempoSeasonSummaryData
from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_season_cache"
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TempoSeasonCacheEntry:
    """Season cache entry containing the summary and known day-color map."""

    summary: TempoSeasonSummaryData
    day_colors: dict[str, str]


class EdfTempoSeasonCache:
    """Persist season summaries to avoid repeated full-season API calls."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the season cache store."""
        self._store: Store[dict[str, dict[str, object]]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )
        self._data: dict[str, dict[str, object]] = {}

    async def async_load(self) -> None:
        """Load cached data from storage."""
        stored = await self._store.async_load()
        self._data = stored or {}
        _LOGGER.debug("Loaded EDF Tempo season cache with %s entries", len(self._data))

    def get(self, season_start: str) -> TempoSeasonCacheEntry | None:
        """Return a cached season entry."""
        payload = self._data.get(season_start)
        if payload is None:
            return None

        summary_payload = payload.get("summary")
        day_colors_payload = payload.get("day_colors")
        if not isinstance(summary_payload, dict) or not isinstance(day_colors_payload, dict):
            return None

        return TempoSeasonCacheEntry(
            summary=TempoSeasonSummaryData(
                season_start=str(summary_payload["season_start"]),
                season_end=str(summary_payload["season_end"]),
                total_placed=int(summary_payload["total_placed"]),
                blue_days=int(summary_payload["blue_days"]),
                white_days=int(summary_payload["white_days"]),
                red_days=int(summary_payload["red_days"]),
                blue_total=int(summary_payload["blue_total"]),
                white_total=int(summary_payload["white_total"]),
                red_total=int(summary_payload["red_total"]),
            ),
            day_colors={str(key): str(value) for key, value in day_colors_payload.items()},
        )

    async def async_set(self, entry: TempoSeasonCacheEntry) -> None:
        """Persist a season entry."""
        self._data[entry.summary.season_start] = {
            "summary": asdict(entry.summary),
            "day_colors": entry.day_colors,
        }
        await self._store.async_save(self._data)
        _LOGGER.debug(
            "Saved EDF Tempo season cache entry for %s with %s known days",
            entry.summary.season_start,
            len(entry.day_colors),
        )

    async def async_update_current_season(
        self,
        entry: TempoSeasonCacheEntry,
        today: TempoDayData,
        tomorrow: TempoDayData,
    ) -> TempoSeasonCacheEntry:
        """Update the current season cache entry from fresh today/tomorrow values."""
        day_colors = dict(entry.day_colors)
        changed = False

        for day in (today, tomorrow):
            if day.color_code is None:
                continue
            if not (entry.summary.season_start <= day.date <= entry.summary.season_end):
                continue

            previous_color = day_colors.get(day.date)
            if previous_color != day.color_code:
                day_colors[day.date] = day.color_code
                changed = True

        if not changed:
            _LOGGER.debug(
                "No current-season cache update required for %s",
                entry.summary.season_start,
            )
            return entry

        updated_entry = TempoSeasonCacheEntry(
            summary=_build_summary(entry.summary.season_start, entry.summary.season_end, day_colors),
            day_colors=day_colors,
        )
        await self.async_set(updated_entry)
        _LOGGER.debug(
            "Updated current EDF Tempo season cache for %s",
            entry.summary.season_start,
        )
        return updated_entry


def build_cache_entry(
    season_start: str,
    season_end: str,
    day_colors: dict[str, str],
) -> TempoSeasonCacheEntry:
    """Build a cache entry from a date->color map."""
    normalized_day_colors = {
        str(day): normalized_color
        for day, color in day_colors.items()
        if (normalized_color := str(color).upper()) in {"BLUE", "WHITE", "RED"}
    }
    return TempoSeasonCacheEntry(
        summary=_build_summary(season_start, season_end, normalized_day_colors),
        day_colors=normalized_day_colors,
    )


def _build_summary(
    season_start: str,
    season_end: str,
    day_colors: dict[str, str],
) -> TempoSeasonSummaryData:
    """Build a season summary from its date->color map."""
    blue_days = sum(1 for color in day_colors.values() if color == "BLUE")
    white_days = sum(1 for color in day_colors.values() if color == "WHITE")
    red_days = sum(1 for color in day_colors.values() if color == "RED")

    return TempoSeasonSummaryData(
        season_start=season_start,
        season_end=season_end,
        total_placed=blue_days + white_days + red_days,
        blue_days=blue_days,
        white_days=white_days,
        red_days=red_days,
    )
