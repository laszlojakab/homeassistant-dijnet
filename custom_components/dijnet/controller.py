# pylint: disable=bad-continuation
'''
Module for Dijnet controller.
'''
import logging
import re
from datetime import datetime, timedelta
from os import makedirs, path
from typing import Any, Dict, List

import yaml
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle, slugify
from pyquery import PyQuery as pq
from pyquery.pyquery import PyQuery

from .const import DATA_CONTROLLER, DOMAIN
from .dijnet_session import DijnetSession

_LOGGER = logging.getLogger(__name__)

MIN_DATE = "1990-01-01"
DATE_FORMAT = "%Y.%m.%d"
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=3)
MIN_TIME_BETWEEN_ISSUER_UPDATES = timedelta(days=1)
PAID_INVOICES_FILENAME = ".dijnet_paid_invoices.yaml"
REGISTRY_FILENAME = ".dijnet_registry.yaml"
ATTR_REGISTRY_NEXT_QUERY_DATE = "next_query_date"

ATTR_PROVIDER = "provider"
ATTR_DISPLAYNAME = "displayname"
ATTR_INVOICE_NO = "invoice_no"
ATTR_ISSUANCE_DATE = "issuance_date"
ATTR_DEADLINE = "deadline"
ATTR_AMOUNT = "amount"
PAID_KEY = "paid"
ATTR_PAID_AT = "paid_at"


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


class Invoice:
    '''
    Represents an invoice.
    '''

    def __init__(
        self,
        provider: str,
        displayname: str,
        invoice_no: str,
        issuance_date: datetime,
        amount: int,
        deadline: datetime
    ):
        '''
        Initialize a new instance of Invoice class.

        Parameters
        ----------
        provider: str
            The provider.
        displayname: str
            The displayname.
        invoice_no: str
            The invoice number.
        issuance_date: datetime
            The issuance date.
        amount: int
            The invoice amount.
        deadline: datetime
            The deadline.
        '''
        self._provider = provider
        self._displayname = displayname
        self._invoice_no = invoice_no
        self._issuance_date = issuance_date
        self._amount = amount
        self._deadline = deadline

    @property
    def provider(self) -> str:
        '''
        Gets the provider.
        '''
        return self._provider

    @property
    def displayname(self) -> str:
        '''
        Gets the displayname.
        '''
        return self._displayname

    @property
    def invoice_no(self) -> str:
        '''
        Gets the invoice number.
        '''
        return self._invoice_no

    @property
    def issuance_date(self) -> datetime:
        '''
        Gets the issuance date.
        '''
        return self._issuance_date

    @property
    def amount(self) -> int:
        '''
        Gets the issuance date.
        '''
        return self._amount

    @property
    def deadline(self) -> datetime:
        '''
        Gets the deadline.
        '''
        return self._deadline

    def __eq__(self, obj):
        return isinstance(obj, Invoice) and \
            obj.provider == self.provider and \
            obj.invoice_no == self.invoice_no

    def to_dictionary(self) -> Dict[str, Any]:
        '''
        Converts the paid invoice to a dictionary.

        Returns
        -------
        Dict[str, Any]
            The dictionary contains information of paid invoice.
        '''
        return {
            ATTR_PROVIDER: self._provider,
            ATTR_DISPLAYNAME: self.displayname,
            ATTR_INVOICE_NO: self.invoice_no,
            ATTR_ISSUANCE_DATE: self.issuance_date,
            ATTR_AMOUNT: self.amount,
            ATTR_DEADLINE: self.deadline
        }

    def __str__(self):
        return self.to_dictionary().__str__()


class PaidInvoice(Invoice):
    '''
    Represents a paid invoice.
    '''

    def __init__(
        self,
        provider: str,
        displayname: str,
        invoice_no: str,
        issuance_date: datetime,
        amount: int,
        deadline: datetime,
        paid_at: datetime
    ):
        '''
        Initialize a new instance of Invoice class.

        Parameters
        ----------
        provider: str
            The provider.
        displayname: str
            The displayname.
        invoice_no: str
            The invoice number.
        issuance_date: datetime
            The issuance date.
        amount: int
            The invoice amount.
        deadline: datetime
            The deadline.
        paid_at: datetime
            The date of payment.
        '''
        super().__init__(provider, displayname, invoice_no, issuance_date, amount, deadline)
        self._paid_at = paid_at

    @property
    def paid_at(self) -> datetime:
        '''
        Gets the date of payment.
        '''
        return self._paid_at

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Any]):
        '''
        Converts a dictionary to PaidInvoice instance.

        Parameters
        ----------
        dictionary: Dict[str, Any]
            The dictionary to convert.

        Returns
        -------
        PaidInvoice
            The converted paid invoice.
        '''
        return PaidInvoice(
            dictionary[ATTR_PROVIDER],
            dictionary[ATTR_DISPLAYNAME],
            dictionary[ATTR_INVOICE_NO],
            dictionary[ATTR_ISSUANCE_DATE].date().isoformat() if isinstance(
                dictionary[ATTR_ISSUANCE_DATE], datetime) else dictionary[ATTR_ISSUANCE_DATE],
            dictionary[ATTR_DEADLINE].date().isoformat() if isinstance(
                dictionary[ATTR_DEADLINE], datetime) else dictionary[ATTR_DEADLINE],
            dictionary[ATTR_AMOUNT],
            dictionary[ATTR_PAID_AT]
        )

    def to_dictionary(self) -> Dict[str, Any]:
        '''
        Converts the paid invoice to a dictionary.

        Returns
        -------
        Dict[str, Any]
            The dictionary contains information of paid invoice.
        '''
        res = super().to_dictionary()
        res[ATTR_PAID_AT] = self.paid_at

        return res


class DijnetController:
    '''
    Responsible for providing data from Dijnet website.
    '''

    def __init__(self, username: str, password: str, download_dir: str = None):
        '''
        Initialize a new instance of DijnetController class.

        Parameters
        ----------
        username: str
            The registered username.
        password: str
            The password for user.
        download_dir: str
            Optional download directory. If set then the invoice
            files are downloaded to that location.
        '''
        self._username = username
        self._password = password
        self._download_dir = download_dir
        self._registry: Dict[str, str] = None
        self._unpaid_invoices: List[Invoice] = []
        self._paid_invoices: List[Invoice] = []
        self._issuers: List[InvoiceIssuer] = []

    async def get_unpaid_invoices(self) -> List[Invoice]:
        '''
        Gets the list of unpaid invoices.

        Returns
        -------
        List[Invoice]
            The list of unpaid invoices.
        '''
        await self.update_invoices()
        return self._unpaid_invoices

    async def get_paid_invoices(self) -> List[Invoice]:
        '''
        Gets the list of paid invoices.

        Returns
        -------
        List[Invoice]
            The list of paid invoices.
        '''
        await self.update_invoices()
        return self._paid_invoices

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

    @Throttle(MIN_TIME_BETWEEN_ISSUER_UPDATES)
    async def update_registered_issuers(self):
        '''
        Updates the registered issuers list.
        '''
        issuers: List[InvoiceIssuer] = []

        _LOGGER.debug('Updating issuers.')

        async with DijnetSession() as session:
            await session.get_root_page()

            if not await session.post_login(self._username, self._password):
                return

            await session.get_main_page()

            await session.get_new_providers_page()

            providers_response = await session.get_registered_providers_page()

            providers_response_pquery = pq(providers_response)
            for row in providers_response_pquery.find(".szamla_table > tbody > tr").items():
                issuer_name = row.children("td:nth-child(1)").text()
                issuer_id = row.children("td:nth-child(2)").text()
                display_name = row.children("td:nth-child(3)").text()
                issuer = InvoiceIssuer(issuer_id, issuer_name, display_name)
                issuers.append(issuer)
                _LOGGER.debug("Issuer found (%s)", issuer)

            self._issuers = issuers

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update_invoices(self):
        '''
        Updates the invoice lists.
        '''
        _LOGGER.debug("Updating invoices.")

        if self._registry is None:
            self._initialize_registry_and_unpaid_invoices()

        async with DijnetSession() as session:
            await session.get_root_page()

            if not await session.post_login(self._username, self._password):
                return

            from_date = self._registry[ATTR_REGISTRY_NEXT_QUERY_DATE]
            to_date = datetime.now().date().isoformat()

            await session.get_main_page()

            await session.get_invoice_search_page()

            search_result = await session.post_search_invoice('', '', from_date, to_date)

            invoices_pyquery = pq(search_result)
            possible_new_paid_invoices: List[PaidInvoice] = []
            possible_new_unpaid_invoices: List[Invoice] = []
            index = 0
            for row in invoices_pyquery.find('.szamla_table > tbody > tr').items():
                invoice: Invoice = None
                if self._is_invoice_paid(row):
                    await session.get_invoice_page(index)
                    invoice_history_page = await session.get_invoice_history_page()
                    invoice_history_page_response_pyquery = pq(invoice_history_page)
                    for history_row in invoice_history_page_response_pyquery.find('.szamla_table.xt_lower tr').items():
                        if history_row.children('td:nth-child(4)').text() == '**Sikeres fizetés**':
                            paid_at = datetime.strptime(
                                history_row.children('td:nth-child(1)').text(),
                                DATE_FORMAT
                            ).date().isoformat()
                            invoice = self._create_invoice_from_row(row, paid_at)
                            possible_new_paid_invoices.append(invoice)
                        else:
                            # not paid?
                            invoice = self._create_invoice_from_row(row)
                else:
                    invoice = self._create_invoice_from_row(row)
                    possible_new_unpaid_invoices.append(invoice)

                if self._download_dir != '':
                    directory = path.join(self._download_dir, slugify(invoice.displayname))
                    makedirs(directory, exist_ok=True)
                    if invoice is not PaidInvoice:
                        await session.get_invoice_page(index)

                    invoice_download_page = await session.get_invoice_download_page()

                    unpaid_invoice_download_page_response_pyquery = PyQuery(
                        invoice_download_page)

                    for downloadable_link in unpaid_invoice_download_page_response_pyquery.find('#tab_szamla_letolt a:not([href^=http])').items():
                        href = downloadable_link.attr('href')
                        extension = href.split('?')[0].split('_')[-1]
                        name = href.split('?')[0][:-4]
                        filename = slugify(
                            f"{name}_{datetime.fromisoformat(invoice.issuance_date).strftime('%Y%m%d')}_{invoice.invoice_no}.{extension}"
                        )
                        download_url = f"https://www.dijnet.hu/ekonto/control/{href}"
                        _LOGGER.debug('Downloadable file found (%s).', download_url)

                        full_path = path.join(directory, filename)

                        if path.exists(full_path):
                            _LOGGER.debug('File already downloaded (%s)', full_path)
                        else:
                            _LOGGER.info('Downloading file (%s -> %s).', download_url, full_path)
                            file_content = await session.download(download_url)
                            with open(full_path, "wb") as file:
                                file.write(file_content)

                index += 1
                await session.get_invoice_list_page()

            paid_invoices = self._paid_invoices.copy()
            unpaid_invoices = self._unpaid_invoices.copy()
            new_paid_invoices: List[PaidInvoice] = []
            for possible_new_paid_invoice in possible_new_paid_invoices:
                already_exists = False
                for paid_invoice in paid_invoices:
                    if paid_invoice == possible_new_paid_invoice:
                        already_exists = True
                        break

                if not already_exists:
                    paid_invoices.append(possible_new_paid_invoice)
                    new_paid_invoices.append(possible_new_paid_invoice)
                    for unpaid_invoice in unpaid_invoices:
                        if unpaid_invoice == possible_new_paid_invoice:
                            unpaid_invoices.remove(unpaid_invoice)
                            break

            for possible_new_unpaid_invoice in possible_new_unpaid_invoices:
                already_exists = False
                for unpaid_invoice in unpaid_invoices:
                    if unpaid_invoice == possible_new_unpaid_invoice:
                        already_exists = True
                        break

                if not already_exists:
                    unpaid_invoices.append(possible_new_unpaid_invoice)

            if len(new_paid_invoices) > 0:
                with open(PAID_INVOICES_FILENAME, "a") as file:
                    file.write("\n")
                    yaml.dump(
                        list(
                            map(lambda x: x.to_dictionary(), new_paid_invoices)
                        ),
                        file,
                        default_flow_style=False
                    )

            next_query_date = (datetime.fromisoformat(to_date) -
                               timedelta(days=31)).date().isoformat()

            for unpaid_invoice in unpaid_invoices:
                if next_query_date > unpaid_invoice.issuance_date:
                    next_query_date = unpaid_invoice.issuance_date

            registry = {
                ATTR_REGISTRY_NEXT_QUERY_DATE: next_query_date
            }

            with open(REGISTRY_FILENAME, "w") as file:
                yaml.dump(registry, file, default_flow_style=False)

            self._registry = registry
            self._unpaid_invoices = unpaid_invoices
            self._paid_invoices = paid_invoices

    def _create_invoice_from_row(self, row: PyQuery, paid_at: datetime = None) -> Invoice:
        provider = row.children('td:nth-child(1)').text()
        displayname = row.children('td:nth-child(2)').text()
        invoice_no = row.children('td:nth-child(3)').text()
        issuance_date = datetime.strptime(row.children(
            'td:nth-child(4)').text(), DATE_FORMAT).replace(tzinfo=None).date().isoformat()
        amount = float(
            re.sub(r'[^0-9\-]+', '', row.children('td:nth-child(5)').text()))
        deadline = datetime.strptime(row.children(
            'td:nth-child(6)').text(), DATE_FORMAT).replace(tzinfo=None).date().isoformat()

        invoice: Invoice = None
        if paid_at:
            invoice = PaidInvoice(
                provider,
                displayname,
                invoice_no,
                issuance_date,
                amount,
                deadline,
                paid_at
            )
        else:
            invoice = Invoice(
                provider,
                displayname,
                invoice_no,
                issuance_date,
                amount,
                deadline
            )

        _LOGGER.info('Invoice created. %s', invoice)

        return invoice

    def _is_invoice_paid(self, row: PyQuery) -> bool:
        return 'Rendezetlen' not in row.children('td:nth-child(8)').text()

    def _initialize_registry_and_unpaid_invoices(self):
        paid_invoices = None
        registry = None
        try:
            _LOGGER.debug('Loading registry from "%s"', REGISTRY_FILENAME)
            with open(REGISTRY_FILENAME) as file:
                registry = yaml.safe_load(file)

            paid_invoices = []
            _LOGGER.debug('Loading invoices from "%s"', PAID_INVOICES_FILENAME)
            with open(PAID_INVOICES_FILENAME) as file:
                data = yaml.safe_load(file)
                for paid_invoice_dict in data:
                    try:
                        paid_invoices.append(
                            PaidInvoice.from_dictionary(paid_invoice_dict)
                        )
                    # pylint: disable=broad-except
                    except Exception as exception:
                        _LOGGER.warning(
                            'Invalid paid invoice data: %s',
                            exception
                        )
        except FileNotFoundError:
            _LOGGER.debug('"%s" or "%s" not found.', PAID_INVOICES_FILENAME, REGISTRY_FILENAME)
            paid_invoices = []
            registry = {
                ATTR_REGISTRY_NEXT_QUERY_DATE: MIN_DATE
            }

        self._paid_invoices = paid_invoices
        self._registry = registry


def set_controller(hass: HomeAssistantType, user_name: str, controller: DijnetController) -> None:
    '''
    Sets the controller instance for the specified username in Home Assistant data container.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    user_name: str
        The registered username.
    controller: DijnetController
        The controller instance to set.
    '''
    hass.data[DOMAIN][DATA_CONTROLLER][user_name] = controller


def get_controller(hass: HomeAssistantType, user_name: str) -> DijnetController:
    '''
    Gets the controller instance for the specified username from Home Assistant data container.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    user_name: str
        The registered username.

    Returns
    -------
    DijnetController
        The controller associated to the specified username.
    '''
    return hass.data[DOMAIN][DATA_CONTROLLER].get(user_name)


def is_controller_exists(hass: HomeAssistantType, user_name: str) -> bool:
    '''
    Gets the value indicates whether a controller associated to the specified
    username in Home Assistant data container.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    user_name: str
        The registered username.

    Returns
    -------
    bool
        The value indicates whether a controller associated to the specified
        username in Home Assistant data container.
    '''
    return user_name in hass.data[DOMAIN][DATA_CONTROLLER]
