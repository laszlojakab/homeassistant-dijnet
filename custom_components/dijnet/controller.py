import logging
import os.path
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle
from pyquery import PyQuery as pq

from .const import DATA_CONTROLLER, DOMAIN
from .dijnet_session import DijnetSession

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=3)
MIN_TIME_BETWEEN_ISSUER_UPDATES = timedelta(days=1)


class InvoiceIssuer():
    '''
    Represents an invoice issuer.
    '''

    def __init__(self, issuer_id: str, issuer_name: str, displayname: str):
        '''
        Initialize a new instance of InvoiceIssuer class.

        Parameters
        ----------
        issuer_id: str
            The registration ID at the invoice issuer.
        issuer_name: str
            The name of the invoice issuer.
        displayname: str
            The display name of the registration.
        '''
        self._issuer_id = issuer_id
        self._issuer_name = issuer_name
        self._displayname = displayname

    def __str__(self) -> str:
        '''
        Returns the string representation of the class.
        '''
        return f'{self.issuer} - {self.issuer_id} - {self.displayname}'

    @property
    def issuer_id(self) -> str:
        '''
        Gets the invoice issuer id.
        '''
        return self._issuer_id

    @property
    def displayname(self) -> str:
        '''
        Gets the dislayname.
        '''
        return self._displayname

    @property
    def issuer(self) -> str:
        '''
        Gets the invoice issuer name.
        '''
        return self._issuer_name


class DijnetController:
    def __init__(self, username, password, downloadDir):
        self._lock = threading.Lock()
        self._username = username
        self._password = password
        self._downloadDir = downloadDir
        self._unpaidInvoices = None
        self._unpaidInvoicesLastUpdate = None
        self._issuers: List[InvoiceIssuer] = []

    async def getUnpaidInvoices(self):
        if (self._unpaidInvoices == None):
            await self.updateUnpaidInvoices()
        return self._unpaidInvoices

    async def get_issuers(self) -> List[InvoiceIssuer]:
        '''
        Gets the list of registered invoice issuers.

        Returns
        -------
        List[InvoiceIssuer]
            The list of registered invoice issuers.
        '''
        await self.update_registered_issuers()
        return self._issuers

    def isUnpaidInvoicesUpdatedNotLongAgo(self):
        if (self._unpaidInvoicesLastUpdate == None):
            return False

        return self.getUnpaidInvoicesAge() < MIN_TIME_BETWEEN_UPDATES

    def getUnpaidInvoicesAge(self):
        if (self._unpaidInvoicesLastUpdate == None):
            return None

        return (datetime.now() - self._unpaidInvoicesLastUpdate)

    @Throttle(MIN_TIME_BETWEEN_ISSUER_UPDATES)
    async def update_registered_issuers(self):
        '''
        Updates the registered issuers list.
        '''
        issuers: List[InvoiceIssuer] = []

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
            providers_response = await session.get_registered_providers_page()

            _LOGGER.debug("Parsing 'regszolg_list' page.")
            providers_response_pquery = pq(providers_response)
            for row in providers_response_pquery.find(".szamla_table > tbody > tr").items():
                issuer_name = row.children("td:nth-child(1)").text()
                issuer_id = row.children("td:nth-child(2)").text()
                display_name = row.children("td:nth-child(3)").text()
                issuer = InvoiceIssuer(issuer_id, issuer_name, display_name)
                issuers.append(issuer)
                _LOGGER.debug("Issuer found (%s)", issuer)

            self._issuers = issuers

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
                                    file_content = await session.download(downloadUrl)
                                    with open(fullPath, "wb") as file:
                                        file.write(file_content)

                        index = index + 1
                    self._unpaidInvoices = unpaidInvoices


def set_controller(hass: HomeAssistantType, user_name: str, controller: DijnetController) -> None:
    hass.data[DOMAIN][DATA_CONTROLLER][user_name] = controller


def get_controller(hass: HomeAssistantType, user_name: str) -> DijnetController:
    return hass.data[DOMAIN][DATA_CONTROLLER].get(user_name)


def is_controller_exists(hass: HomeAssistantType, user_name: str) -> bool:
    return user_name in hass.data[DOMAIN][DATA_CONTROLLER]
