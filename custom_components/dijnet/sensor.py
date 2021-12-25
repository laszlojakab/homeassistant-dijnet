"""Support for Dijnet."""
import logging
import re
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (ConfigType, DiscoveryInfoType,
                                          HomeAssistantType)
from homeassistant.util import Throttle

from .const import CONF_DOWNLOAD_DIR, DOMAIN
from .controller import DijnetController, get_controller

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=3)
ICON = "mdi:currency-usd"
UNIT = "Ft"
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Dijnet Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DOWNLOAD_DIR, default=''): cv.string
    }
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Import yaml config and initiates config flow for Dijnet integration."""

    # Check if entry config exists and skips import if it does.
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.warning(
            'Setting up Dijnet integration from yaml is deprecated. Please remove configuration from yaml.')
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> bool:
    '''
    Setup of Dijnet sensors for the specified config_entry.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    config_entry: homeassistant.helpers.typing.ConfigEntry
        The config entry which is used to create sensors.
    async_add_entities: homeassistant.helpers.entity_platform.AddEntitiesCallback
        The callback which can be used to add new entities to Home Assistant.

    Returns
    -------
    bool
        The value indicates whether the setup succeeded.
    '''
    _LOGGER.info('Setting up Dijnet sensors.')

    controller = get_controller(hass, config_entry.data[CONF_USERNAME])

    for registered_invoice_issuer in await controller.get_issuers():
        async_add_entities(
            [DijnetProviderSensor(registered_invoice_issuer.displayname, controller)]
        )
        _LOGGER.debug('Sensor added (%s)', registered_invoice_issuer)

    _LOGGER.debug('Adding total sensor')
    async_add_entities([DijnetTotalSensor(controller)], True)

    _LOGGER.info('Setting up Helios EasyControls sensors completed.')
    return True


class DijnetBaseSensor(Entity):
    def __init__(self, wrapper: DijnetController):
        self._state = None
        self._wrapper = wrapper
        self._attributes = {}
        self._data = {}

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state != None and self._state > 0

    @property
    def available(self) -> bool:
        """Return true if the device is available and value has not expired."""
        return self._state != None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UNIT

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("Updating wrapper for dijnet sensor (%s).", self.name)
        await self._wrapper.updateUnpaidInvoices()
        _LOGGER.debug(
            "Updating wrapper for dijnet sensor (%s) completed.", self.name)

        self._data = {
            'providers': await self._wrapper.get_issuers(),
            'unpaidInvoices': await self._wrapper.getUnpaidInvoices()
        }
        self._state = len(await self._wrapper.getUnpaidInvoices()) > 0

    def get_filename_from_cd(self, cd):
        """
        Get filename from content-disposition
        """
        if not cd:
            return None
        fname = re.findall('filename=(.+)', cd)
        if len(fname) == 0:
            return None
        return fname[0]


class DijnetProviderSensor(DijnetBaseSensor):
    # """Representation of a Dijnet provider sensor."""
    def __init__(self, provider, wrapper):
        """Initialize the Dijnet provider sensor."""
        super().__init__(wrapper)
        self._provider = provider

    @property
    def name(self):
        """Return the name of the sensor."""
        return f'Dijnet ({self._provider})'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await super().async_update()
        self._state = None
        amount = 0
        unpaidInvoices = []
        for unpaidInvoice in self._data['unpaidInvoices']:
            if (unpaidInvoice['issuerId'] == self._provider):
                amount = amount + unpaidInvoice['amount']
                unpaidInvoices.append(unpaidInvoice)

        self._attributes = {'unpaidInvoices': unpaidInvoices}
        self._state = amount


class DijnetTotalSensor(DijnetBaseSensor):
    # """Representation of a Dijnet sensor."""
    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Dijnet fizetendő számlák összege'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await super().async_update()
        amount = 0
        for unpaidInvoice in self._data['unpaidInvoices']:
            amount = amount + unpaidInvoice['amount']
        self._state = amount
