"""Sensor platform for the EDF Tempo integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import TempoDayData, TempoSeasonSummaryData
from .const import (
    ATTR_BLUE_DAYS,
    ATTR_BLUE_TOTAL,
    ATTR_COLOR_CODE,
    ATTR_DATE,
    ATTR_FALLBACK,
    ATTR_RED_DAYS,
    ATTR_RED_TOTAL,
    ATTR_SEASON_END,
    ATTR_SEASON_START,
    ATTR_TOTAL_PLACED,
    ATTR_UPDATED_DATE,
    ATTR_WHITE_DAYS,
    ATTR_WHITE_TOTAL,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import EdfTempoDataUpdateCoordinator


@dataclass(frozen=True, slots=True)
class EdfTempoSensorEntityDescription(SensorEntityDescription):
    """Describe an EDF Tempo sensor."""

    value_key: str = ""
    object_id: str = ""


TEMPO_COLOR_OPTIONS = ["blue", "white", "red", "unknown"]
REMAINING_DAY_FIELDS = {
    "remaining_red_days": ("red_days", "red_total"),
    "remaining_white_days": ("white_days", "white_total"),
    "remaining_blue_days": ("blue_days", "blue_total"),
}


SENSORS: tuple[EdfTempoSensorEntityDescription, ...] = (
    EdfTempoSensorEntityDescription(
        key="today",
        translation_key="today",
        device_class=SensorDeviceClass.ENUM,
        options=TEMPO_COLOR_OPTIONS,
        value_key="today",
        object_id="edf_tempo_today",
    ),
    EdfTempoSensorEntityDescription(
        key="tomorrow",
        translation_key="tomorrow",
        device_class=SensorDeviceClass.ENUM,
        options=TEMPO_COLOR_OPTIONS,
        value_key="tomorrow",
        object_id="edf_tempo_tomorrow",
    ),
    EdfTempoSensorEntityDescription(
        key="season_summary",
        translation_key="season_summary",
        value_key="season_summary",
        object_id="edf_tempo_season_summary",
    ),
    EdfTempoSensorEntityDescription(
        key="remaining_red_days",
        translation_key="remaining_red_days",
        native_unit_of_measurement="d",
        value_key="remaining_red_days",
        object_id="edf_tempo_remaining_red_days",
    ),
    EdfTempoSensorEntityDescription(
        key="remaining_white_days",
        translation_key="remaining_white_days",
        native_unit_of_measurement="d",
        value_key="remaining_white_days",
        object_id="edf_tempo_remaining_white_days",
    ),
    EdfTempoSensorEntityDescription(
        key="remaining_blue_days",
        translation_key="remaining_blue_days",
        native_unit_of_measurement="d",
        value_key="remaining_blue_days",
        object_id="edf_tempo_remaining_blue_days",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EDF Tempo sensors from a config entry."""
    coordinator: EdfTempoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EdfTempoSensor(coordinator, entry, description) for description in SENSORS
    )


class EdfTempoSensor(CoordinatorEntity[EdfTempoDataUpdateCoordinator], SensorEntity):
    """Representation of an EDF Tempo sensor."""

    entity_description: EdfTempoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EdfTempoDataUpdateCoordinator,
        entry: ConfigEntry,
        description: EdfTempoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = description.object_id

    @property
    def native_value(self) -> str | int:
        """Return the current state."""
        if self.entity_description.value_key == "season_summary":
            return str(self._season_summary.total_placed)
        if self.entity_description.value_key in REMAINING_DAY_FIELDS:
            used_field, total_field = REMAINING_DAY_FIELDS[
                self.entity_description.value_key
            ]
            return max(
                getattr(self._season_summary, total_field)
                - getattr(self._season_summary, used_field),
                0,
            )
        color_code = self._day_data.color_code
        if color_code in {"BLUE", "WHITE", "RED"}:
            return color_code.lower()
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional sensor attributes."""
        if self.entity_description.value_key == "season_summary":
            return {
                ATTR_SEASON_START: self._season_summary.season_start,
                ATTR_SEASON_END: self._season_summary.season_end,
                ATTR_TOTAL_PLACED: self._season_summary.total_placed,
                ATTR_BLUE_DAYS: self._season_summary.blue_days,
                ATTR_WHITE_DAYS: self._season_summary.white_days,
                ATTR_RED_DAYS: self._season_summary.red_days,
                ATTR_BLUE_TOTAL: self._season_summary.blue_total,
                ATTR_WHITE_TOTAL: self._season_summary.white_total,
                ATTR_RED_TOTAL: self._season_summary.red_total,
            }
        if self.entity_description.value_key in REMAINING_DAY_FIELDS:
            used_field, total_field = REMAINING_DAY_FIELDS[
                self.entity_description.value_key
            ]
            return {
                ATTR_SEASON_START: self._season_summary.season_start,
                ATTR_SEASON_END: self._season_summary.season_end,
                "used_days": getattr(self._season_summary, used_field),
                "total_days": getattr(self._season_summary, total_field),
            }
        return {
            ATTR_DATE: self._day_data.date,
            ATTR_COLOR_CODE: self._day_data.color_code,
            ATTR_FALLBACK: self._day_data.fallback,
            ATTR_UPDATED_DATE: self._day_data.updated_date,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the integration device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Community integration",
            model="Tempo data source: RTE",
        )

    @property
    def _day_data(self) -> TempoDayData:
        """Return the relevant day data."""
        return getattr(self.coordinator.data, self.entity_description.value_key)

    @property
    def _season_summary(self) -> TempoSeasonSummaryData:
        """Return the season summary data."""
        return self.coordinator.data.season_summary
