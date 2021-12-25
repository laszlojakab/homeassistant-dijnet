import logging
import os.path
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.helpers.typing import HomeAssistantType
from pyquery import PyQuery as pq

from .const import DATA_CONTROLLER, DOMAIN
from .dijnet_session import DijnetSession

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=3)


class DijnetController:
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


def set_controller(hass: HomeAssistantType, user_name: str, controller: DijnetController) -> None:
    hass.data[DOMAIN][DATA_CONTROLLER][user_name] = controller


def get_controller(hass: HomeAssistantType, user_name: str) -> DijnetController:
    return hass.data[DOMAIN][DATA_CONTROLLER].get(user_name)


def is_controller_exists(hass: HomeAssistantType, user_name: str) -> bool:
    return user_name in hass.data[DOMAIN][DATA_CONTROLLER]
