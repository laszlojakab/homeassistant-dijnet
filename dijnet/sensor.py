"""Support for Dijnet."""
import json
import logging
import re
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_NAME, CONF_PASSWORD,
                                 CONF_USERNAME)
from homeassistant.helpers.entity import Entity

from pyquery import PyQuery as pq

SCAN_INTERVAL = timedelta(hours=3)
ICON = "mdi:currency-usd"
UNIT = "Ft"
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Dijnet Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Dijnet sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    session = requests.Session()
    session.get('https://www.dijnet.hu')
    loginResponse = session.post('https://www.dijnet.hu/ekonto/login/login_check_ajax',
                                 data={'username': username, 'password': password})
    loginResponseObject = json.loads(loginResponse.text)
    if (loginResponseObject["success"] != True):
        _LOGGER.error("Dijnet login failed. " + loginResponseObject["error"])
        return

    session.get("https://www.dijnet.hu/ekonto/control/main")
    session.get("https://www.dijnet.hu/ekonto/control/regszolg_new")

    providersResponse = session.get(
        "https://www.dijnet.hu/ekonto/control/regszolg_list")
    providersResponsePq = pq(providersResponse.text)
    for row in providersResponsePq.find(".szamla_table > tbody > tr").items():
        async_add_entities([DijnetProviderSensor(row.children(
            "td:nth-child(3)").text(), username, password)])

    async_add_entities([DijnetTotalSensor(username, password)], True)


class DijnetBaseSensor(Entity):
    def __init__(self, username, password):
        self._state = None
        self._username = username
        self._password = password
        self._attributes = {}

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
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        session = requests.Session()
        session.get('https://www.dijnet.hu')
        loginResponse = session.post('https://www.dijnet.hu/ekonto/login/login_check_ajax', data={
                                     'username': self._username, 'password': self._password})
        loginResponseObject = json.loads(loginResponse.text)
        if (loginResponseObject["success"] != True):
            _LOGGER.error("Dijnet login failed. " +
                          loginResponseObject["error"])
            self._state = None
            return

        unpaidInvoicesPageResponse = session.get(
            "https://www.dijnet.hu/ekonto/control/main")
        unpaidInvoicesPq = pq(unpaidInvoicesPageResponse.text)
        unpaidInvoices = []
        for row in unpaidInvoicesPq.find(".szamla_table > tbody > tr").items():
            unpaidInvoices.append({
                'provider': row.children("td:nth-child(1)").text(),
                'issuerId': row.children("td:nth-child(2)").text(),
                'invoiceNo': row.children("td:nth-child(3)").text(),
                'issuanceDate': row.children("td:nth-child(4)").text(),
                'invoiceAmount': float(re.sub(r"[\sA-Za-z]+", "", row.children("td:nth-child(5)").text())),
                'deadline': row.children("td:nth-child(6)").text(),
                'amount': float(re.sub(r"[\sA-Za-z]+", "", row.children("td:nth-child(7)").text()))
            })

        self._attributes = {'unpaidInvoices': unpaidInvoices}
        self._state = len(unpaidInvoices) > 0


class DijnetProviderSensor(DijnetBaseSensor):
    # """Representation of a Dijnet provider sensor."""
    def __init__(self, provider, username, password):
        """Initialize the Dijnet provider sensor."""
        super().__init__(username, password)
        self._provider = provider

    @property
    def name(self):
        """Return the name of the sensor."""
        return f'Dijnet ({self._provider})'

    def update(self):
        super().update()
        self._state = None
        amount = 0
        for unpaidInvoice in self._attributes['unpaidInvoices']:
            if (unpaidInvoice['issuerId'] == self._provider):
                amount = amount + unpaidInvoice['amount']
        self._state = amount


class DijnetTotalSensor(DijnetBaseSensor):
    # """Representation of a Dijnet sensor."""
    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Dijnet fizetendő számlák összege'

    def update(self):
        super().update()
        amount = 0
        for unpaidInvoice in self._attributes['unpaidInvoices']:
            amount = amount + unpaidInvoice['amount']
        self._state = amount
