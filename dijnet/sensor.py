"""Support for Dijnet."""
import json
import logging
import re
from datetime import timedelta, datetime

from pathlib import Path
import os.path
from os import path
import homeassistant.helpers.config_validation as cv
import requests
import threading
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

CONF_DOWNLOAD_DIR = "download_dir"
CONF_DOWNLOAD_DIR_DEFAULT = ""
DEFAULT_NAME = "Dijnet Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DOWNLOAD_DIR, default=CONF_DOWNLOAD_DIR_DEFAULT): cv.string
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Dijnet sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    downloadDir = config[CONF_DOWNLOAD_DIR]
    wrapper = DijnetWrapper(username, password, downloadDir)

    _LOGGER.debug("Setting up platform.")

    for provider in wrapper.getProviders():
        async_add_entities(
            [DijnetProviderSensor(provider, wrapper)])
        _LOGGER.debug("Sensor added (%s)", provider)

    _LOGGER.debug("Adding total sensor")
    async_add_entities([DijnetTotalSensor(wrapper)], True)


class DijnetWrapper:
    def __init__(self, username, password, downloadDir):
        self._lock = threading.Lock()
        self._username = username
        self._password = password
        self._downloadDir = downloadDir
        self._unpaidInvoices = None
        self._unpaidInvoicesLastUpdate = None
        self._providers = None
        self._files = {}

    def getUnpaidInvoices(self):
        if (self._unpaidInvoices == None):
            self.updateUnpaidInvoices()
        return self._unpaidInvoices

    def getProviders(self):
        if (self._providers == None):
            self.updateProviders()
        return self._providers

    def isUnpaidInvoicesUpdatedNotLongAgo(self):
        if (self._unpaidInvoicesLastUpdate == None):
            return False

        ageInMinutes = self.getUnpaidInvoicesAge().seconds / 60.0

        return (ageInMinutes < 1)  # less than a minute

    def getUnpaidInvoicesAge(self):
        if (self._unpaidInvoicesLastUpdate == None):
            return None

        return (datetime.now() - self._unpaidInvoicesLastUpdate)

    def updateProviders(self):
        self._providers = []

        _LOGGER.debug("Updating providers.")
        session = requests.Session()
        if (self.login(session) == False):
            return

        _LOGGER.debug("Loading main website.")
        session.get("https://www.dijnet.hu/ekonto/control/main")

        _LOGGER.debug("Loading 'regszolg_new' website.")
        session.get("https://www.dijnet.hu/ekonto/control/regszolg_new")

        _LOGGER.debug("Loading 'regszolg_list' website.")
        providersResponse = session.get(
            "https://www.dijnet.hu/ekonto/control/regszolg_list")

        _LOGGER.debug("Parsing 'regszolg_list' website.")
        providersResponsePq = pq(providersResponse.text)
        for row in providersResponsePq.find(".szamla_table > tbody > tr").items():
            providerName = row.children("td:nth-child(3)").text()
            _LOGGER.debug("Provider found (%s)", providerName)
            self._providers.append(providerName)

        return

    def updateUnpaidInvoices(self):
        with self._lock:
            if (self.isUnpaidInvoicesUpdatedNotLongAgo()):
                _LOGGER.debug("Skipping unpaid invoices update. Data updated recently (%i seconds ago)",
                              self.getUnpaidInvoicesAge().seconds)
                return
            else:
                _LOGGER.debug("Updating unpaid invoices.")
                self._unpaidInvoicesLastUpdate = datetime.now()
                session = requests.Session()
                if (self.login(session) == False):
                    return

                _LOGGER.debug("Loading 'main' website.")
                unpaidInvoicesPageResponse = session.get(
                    "https://www.dijnet.hu/ekonto/control/main")

                _LOGGER.debug("Parsing 'main' website.")
                unpaidInvoicesPq = pq(unpaidInvoicesPageResponse.text)
                unpaidInvoices = []
                for row in unpaidInvoicesPq.find(".szamla_table > tbody > tr").items():
                    provider = row.children("td:nth-child(1)").text()
                    issuerId = row.children("td:nth-child(2)").text()
                    invoiceNo = row.children("td:nth-child(3)").text()
                    issuanceDate = row.children("td:nth-child(4)").text()
                    invoiceAmount = float(
                        re.sub(r"[\sA-Za-z]+", "", row.children("td:nth-child(5)").text()))
                    deadline = row.children("td:nth-child(6)").text()
                    amount = float(
                        re.sub(r"[\sA-Za-z]+", "", row.children("td:nth-child(7)").text()))

                    _LOGGER.debug("Unpaid invoice found. %s, %s, %s, %s, %f, %s, %f", provider,
                                  issuerId, invoiceNo, issuanceDate, invoiceAmount, deadline, amount)

                    unpaidInvoice = {
                        'provider': provider,
                        'issuerId': issuerId,
                        'invoiceNo': invoiceNo,
                        'issuanceDate': issuanceDate,
                        'invoiceAmount': invoiceAmount,
                        'deadline': deadline,
                        'amount': amount,
                        'files': []
                    }

                    unpaidInvoices.append(unpaidInvoice)

                    unpaidInvoicePageUrl = "https://www.dijnet.hu" + \
                        row.find("td:nth-child(8) a").attr("href")
                    _LOGGER.debug("Loading invoice page (%s)",
                                  unpaidInvoicePageUrl)

                    session.get(unpaidInvoicePageUrl)

                    _LOGGER.debug("Loading 'szamla_letolt' page")
                    unpaidInvoiceDownloadPageResponse = session.get(
                        "https://www.dijnet.hu/ekonto/control/szamla_letolt")

                    _LOGGER.debug("Parsing 'szamla_letolt' page")
                    unpaidInvoiceDownloadPageResponsePq = pq(
                        unpaidInvoiceDownloadPageResponse.text)

                    if (self._downloadDir != ""):                        
                        Path(self._downloadDir).mkdir(parents=True, exist_ok=True)

                        for downloadableLink in unpaidInvoiceDownloadPageResponsePq.find("#tab_szamla_letolt a[href^=szamla]").items():
                            href = downloadableLink.attr("href")
                            extension = href.replace("szamla_", "")[:3]
                            fileName = f"{self._downloadDir}/szamla_{issuanceDate.replace('.', '')}_{invoiceNo}.{extension}"
                            downloadUrl = f"https://www.dijnet.hu/ekonto/control/{href}"
                            _LOGGER.debug(
                                "Downloadable file found (%s).", downloadUrl)

                            if os.path.exists(fileName):
                                _LOGGER.debug(
                                    "File already downloaded (%s)", fileName)
                            else:
                                _LOGGER.debug(
                                    "Downloading file (%s -> %s).", downloadUrl, fileName)
                                fileDownloadRequest = session.get(downloadUrl)
                                with open(fileName, "wb") as fil:
                                    for chunk in fileDownloadRequest.iter_content(1024):
                                        fil.write(chunk)
                                self._files[fileName] = None

                self._unpaidInvoices = unpaidInvoices
        return

    def login(self, session):
        _LOGGER.debug("Loading root website")
        session.get('https://www.dijnet.hu')

        _LOGGER.debug("Logging in to dijnet website.")
        loginResponse = session.post('https://www.dijnet.hu/ekonto/login/login_check_ajax',
                                     data={'username': self._username, 'password': self._password})
        loginResponseObject = json.loads(loginResponse.text)
        if (loginResponseObject["success"] != True):
            _LOGGER.error("Login failed. %s", loginResponseObject["error"])
            return False

        _LOGGER.debug("Login succeeded.")
        return True


class DijnetBaseSensor(Entity):
    def __init__(self, wrapper):
        self._state = None
        self._wrapper = wrapper
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
        _LOGGER.debug("Updating wrapper for dijnet sensor (%s).", self.name)
        self._wrapper.updateUnpaidInvoices()
        _LOGGER.debug(
            "Updating wrapper for dijnet sensor (%s) completed.", self.name)
        self._attributes = {
            'providers': self._wrapper.getProviders(),
            'unpaidInvoices': self._wrapper.getUnpaidInvoices()
        }
        self._state = len(self._wrapper.getUnpaidInvoices()) > 0

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
