"""Minimal dependency stubs for running unit tests without Home Assistant."""

from __future__ import annotations

from typing import Generic, TypeVar
import dataclasses
import sys
import types


def install() -> None:
    """Install minimal aiohttp and Home Assistant stubs into sys.modules."""
    _patch_dataclass_slots_support()

    if "homeassistant" in sys.modules and "aiohttp" in sys.modules:
        return

    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        """Stub aiohttp client error."""

    class ClientTimeout:
        """Stub aiohttp timeout container."""

        def __init__(self, total=None):
            self.total = total

    class BasicAuth:
        """Stub aiohttp basic auth."""

        def __init__(self, login: str, password: str) -> None:
            self.login = login
            self.password = password

    class ClientSession:
        """Stub aiohttp client session."""

    aiohttp.ClientError = ClientError
    aiohttp.ClientTimeout = ClientTimeout
    aiohttp.BasicAuth = BasicAuth
    aiohttp.ClientSession = ClientSession
    sys.modules["aiohttp"] = aiohttp

    homeassistant = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = homeassistant

    const = types.ModuleType("homeassistant.const")

    class Platform:
        """Stub platform enum."""

        SENSOR = "sensor"

    const.Platform = Platform
    sys.modules["homeassistant.const"] = const

    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        """Stub config entry."""

        def __init__(self, entry_id: str = "test-entry", data=None) -> None:
            self.entry_id = entry_id
            self.data = data or {}

    class ConfigFlow:
        """Stub config flow base class."""

        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.ConfigFlowResult = dict
    sys.modules["homeassistant.config_entries"] = config_entries

    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        """Stub Home Assistant object."""

        def __init__(self) -> None:
            self.data = {}

    core.HomeAssistant = HomeAssistant
    sys.modules["homeassistant.core"] = core

    exceptions = types.ModuleType("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        """Stub auth failure exception."""

    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    sys.modules["homeassistant.exceptions"] = exceptions

    helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers

    config_validation = types.ModuleType("homeassistant.helpers.config_validation")

    def config_entry_only_config_schema(domain):
        return {"config_entry_only": domain}

    config_validation.config_entry_only_config_schema = config_entry_only_config_schema
    sys.modules["homeassistant.helpers.config_validation"] = config_validation

    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(hass):
        return None

    aiohttp_client.async_get_clientsession = async_get_clientsession
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")

    def async_get(hass):
        class Registry:
            def async_get(self, entity_id):
                return None

            def async_update_entity(self, entity_id, **kwargs):
                return None

        return Registry()

    def async_entries_for_config_entry(registry, entry_id):
        return []

    entity_registry.async_get = async_get
    entity_registry.async_entries_for_config_entry = async_entries_for_config_entry
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    coordinator_type = TypeVar("coordinator_type")

    class DataUpdateCoordinator(Generic[coordinator_type]):
        """Stub update coordinator."""

        def __init__(
            self,
            hass,
            logger,
            *,
            config_entry=None,
            name=None,
            update_interval=None,
            always_update=True,
        ) -> None:
            self.hass = hass
            self.logger = logger
            self.config_entry = config_entry
            self.name = name
            self.update_interval = update_interval
            self.always_update = always_update
            self.data = None
            self.last_update_success = False

    class UpdateFailed(Exception):
        """Stub update failure exception."""

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    storage = types.ModuleType("homeassistant.helpers.storage")
    store_type = TypeVar("store_type")

    class Store(Generic[store_type]):
        """Stub storage helper."""

        def __init__(self, hass, version, key) -> None:
            self.hass = hass
            self.version = version
            self.key = key
            self.saved_data = None

        async def async_load(self):
            return self.saved_data

        async def async_save(self, data) -> None:
            self.saved_data = data

    storage.Store = Store
    sys.modules["homeassistant.helpers.storage"] = storage

    components = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = components

    http = types.ModuleType("homeassistant.components.http")

    @dataclasses.dataclass(frozen=True)
    class StaticPathConfig:
        """Stub static path configuration."""

        url_path: str
        path: str
        cache_headers: bool

    http.StaticPathConfig = StaticPathConfig
    sys.modules["homeassistant.components.http"] = http

    lovelace = types.ModuleType("homeassistant.components.lovelace")
    sys.modules["homeassistant.components.lovelace"] = lovelace

    lovelace_const = types.ModuleType("homeassistant.components.lovelace.const")
    lovelace_const.LOVELACE_DATA = "lovelace"
    lovelace_const.MODE_STORAGE = "storage"
    sys.modules["homeassistant.components.lovelace.const"] = lovelace_const

    sensor = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass:
        """Stub sensor device classes."""

        ENUM = "enum"

    @dataclasses.dataclass(frozen=True)
    class SensorEntityDescription:
        """Stub sensor entity description."""

        key: str
        translation_key: str | None = None
        device_class: str | None = None
        options: list[str] | None = None
        native_unit_of_measurement: str | None = None

    class SensorEntity:
        """Stub sensor entity."""

    sensor.SensorDeviceClass = SensorDeviceClass
    sensor.SensorEntity = SensorEntity
    sensor.SensorEntityDescription = SensorEntityDescription
    sys.modules["homeassistant.components.sensor"] = sensor

    entity = types.ModuleType("homeassistant.helpers.entity")

    class DeviceInfo(dict):
        """Stub device info."""

    entity.DeviceInfo = DeviceInfo
    sys.modules["homeassistant.helpers.entity"] = entity

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = object
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    class CoordinatorEntity(Generic[coordinator_type]):
        """Stub coordinator-backed entity."""

        def __init__(self, coordinator) -> None:
            self.coordinator = coordinator

    update_coordinator.CoordinatorEntity = CoordinatorEntity

    websocket_api = types.ModuleType("homeassistant.components.websocket_api")

    class ActiveConnection:
        """Stub active websocket connection."""

        def send_error(self, *args, **kwargs):
            return None

        def send_result(self, *args, **kwargs):
            return None

    def async_register_command(hass, command):
        return None

    def websocket_command(schema):
        def decorator(func):
            return func

        return decorator

    def async_response(func):
        return func

    websocket_api.ActiveConnection = ActiveConnection
    websocket_api.async_register_command = async_register_command
    websocket_api.websocket_command = websocket_command
    websocket_api.async_response = async_response
    sys.modules["homeassistant.components.websocket_api"] = websocket_api

    voluptuous = types.ModuleType("voluptuous")

    class _RequiredKey(str):
        """Stub voluptuous required key wrapper."""

    def Required(key, default=None):
        return _RequiredKey(key)

    def Schema(schema):
        return schema

    voluptuous.Required = Required
    voluptuous.Schema = Schema
    sys.modules["voluptuous"] = voluptuous


def _patch_dataclass_slots_support() -> None:
    """Ignore dataclass(slots=...) on older local Python runtimes."""
    original = dataclasses.dataclass
    if getattr(original, "_edf_tempo_slots_patched", False):
        return

    def compat_dataclass(*args, **kwargs):
        kwargs.pop("slots", None)
        return original(*args, **kwargs)

    compat_dataclass._edf_tempo_slots_patched = True  # type: ignore[attr-defined]
    dataclasses.dataclass = compat_dataclass
