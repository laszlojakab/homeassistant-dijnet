"""Support for Dijnet."""
import logging
import os.path
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from custom_components.dijnet.dijnet_session import DijnetSession
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (ConfigType, DiscoveryInfoType,
                                          HomeAssistantType)
from homeassistant.util import Throttle
from pyquery import PyQuery as pq

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=3)
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


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:

    """Set up the Dijnet sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    downloadDir = config[CONF_DOWNLOAD_DIR]
    wrapper = DijnetWrapper(username, password, downloadDir)

    _LOGGER.debug("Setting up platform.")

    for provider in (await wrapper.getProviders()):
        add_entities(
            [DijnetProviderSensor(provider, wrapper)])
        _LOGGER.debug("Sensor added (%s)", provider)

    _LOGGER.debug("Adding total sensor")
    add_entities([DijnetTotalSensor(wrapper)], True)


class DijnetWrapper:
    def __init__(self, username, password, downloadDir):
        self._lock = threading.Lock()
        self._username = username
        self._password = password
        self._downloadDir = downloadDir
        self._unpaidInvoices = None
        self._unpaidInvoicesLastUpdate = None
        self._providers = None

    async def getUnpaidInvoices(self):
        if (self._unpaidInvoices == None):
            await self.updateUnpaidInvoices()
        return self._unpaidInvoices

    async def getProviders(self):
        if (self._providers == None):
            await self.updateProviders()
        return self._providers

    def isUnpaidInvoicesUpdatedNotLongAgo(self):
        if (self._unpaidInvoicesLastUpdate == None):
            return False

        return self.getUnpaidInvoicesAge() < MIN_TIME_BETWEEN_UPDATES

    def getUnpaidInvoicesAge(self):
        if (self._unpaidInvoicesLastUpdate == None):
            return None

        return (datetime.now() - self._unpaidInvoicesLastUpdate)

    async def updateProviders(self):
        self._providers = []

        _LOGGER.debug("Updating providers.")

        async with DijnetSession() as session:
            await session.get_root_page()

            if not await session.post_login(self._username, self._password):
                return

            _LOGGER.debug("Loading main page.")
            await session.get_main_page()

            _LOGGER.debug("Loading 'regszolg_new' page.")
            await session.get_new_providers_page()

            _LOGGER.debug("Loading 'regszolg_list' page.")
            providersResponse = await session.get_registered_providers_page()

            _LOGGER.debug("Parsing 'regszolg_list' page.")
            providersResponsePq = pq(providersResponse)
            for row in providersResponsePq.find(".szamla_table > tbody > tr").items():
                providerName = row.children("td:nth-child(3)").text()
                _LOGGER.debug("Provider found (%s)", providerName)
                self._providers.append(providerName)

    async def updateUnpaidInvoices(self):
        with self._lock:
            if (self.isUnpaidInvoicesUpdatedNotLongAgo()):
                _LOGGER.debug("Skipping unpaid invoices update. Data updated recently (%i seconds ago)",
                              self.getUnpaidInvoicesAge().seconds)
                return
            else:
                _LOGGER.debug("Updating unpaid invoices.")
                self._unpaidInvoicesLastUpdate = datetime.now()
                async with DijnetSession() as session:
                    await session.get_root_page()

                    if not (await session.post_login(self._username, self._password)):
                        return

                    _LOGGER.debug("Loading 'main' website.")
                    unpaidInvoicesPageResponse = await session.get_main_page()

                    _LOGGER.debug("Parsing 'main' website.")
                    unpaidInvoicesPq = pq(unpaidInvoicesPageResponse)
                    unpaidInvoices = []
                    index = 0
                    for row in unpaidInvoicesPq.find(".szamla_table > tbody > tr").items():
                        provider = row.children("td:nth-child(1)").text()
                        issuerId = row.children("td:nth-child(2)").text()
                        invoiceNo = row.children("td:nth-child(3)").text()
                        issuanceDate = row.children("td:nth-child(4)").text()
                        invoiceAmount = float(
                            re.sub(r"[^0-9\-]+", "", row.children("td:nth-child(5)").text()))
                        deadline = row.children("td:nth-child(6)").text()
                        amount = float(
                            re.sub(r"[^0-9\-]+", "", row.children("td:nth-child(7)").text()))

                        _LOGGER.debug("Unpaid invoice found. %s, %s, %s, %s, %f, %s, %f", provider,
                                      issuerId, invoiceNo, issuanceDate, invoiceAmount, deadline, amount)

                        unpaidInvoice = {
                            'provider': provider,
                            'issuerId': issuerId,
                            'invoiceNo': invoiceNo,
                            'issuanceDate': issuanceDate,
                            'invoiceAmount': invoiceAmount,
                            'deadline': deadline,
                            'amount': amount
                        }

                        unpaidInvoices.append(unpaidInvoice)

                        _LOGGER.debug("Loading invoice page (%s)", index)

                        await session.get_invoice_page(index)

                        _LOGGER.debug("Loading 'szamla_letolt' page")

                        unpaidInvoiceDownloadPageResponse = await session.get_invoice_download_page()

                        _LOGGER.debug("Parsing 'szamla_letolt' page")
                        unpaidInvoiceDownloadPageResponsePq = pq(unpaidInvoiceDownloadPageResponse)

                        if (self._downloadDir != ""):
                            Path(self._downloadDir).mkdir(
                                parents=True, exist_ok=True)

                            for downloadableLink in unpaidInvoiceDownloadPageResponsePq.find("#tab_szamla_letolt a:not([href^=http])").items():
                                href = downloadableLink.attr("href")
                                extension = href.split("?")[0].split("_")[-1]
                                name = href.split("?")[0][:-4]
                                fileName = f"{name}_{issuanceDate.replace('.', '')}_{invoiceNo}.{extension}".replace(
                                    "/", "_").replace("\\", "_")
                                downloadUrl = f"https://www.dijnet.hu/ekonto/control/{href}"
                                _LOGGER.debug(
                                    "Downloadable file found (%s).", downloadUrl)

                                fullPath = f"{self._downloadDir}/{fileName}"

                                if os.path.exists(fullPath):
                                    _LOGGER.debug(
                                        "File already downloaded (%s)", fullPath)
                                else:
                                    _LOGGER.debug(
                                        "Downloading file (%s -> %s).", downloadUrl, fullPath)
                                    fileDownloadRequest = await session.download(downloadUrl)
                                    with open(fullPath, "wb") as fil:
                                        for chunk in fileDownloadRequest.iter_content(1024):
                                            fil.write(chunk)

                        index = index + 1
                    self._unpaidInvoices = unpaidInvoices


class DijnetBaseSensor(Entity):
    def __init__(self, wrapper):
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
            'providers': await self._wrapper.getProviders(),
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
