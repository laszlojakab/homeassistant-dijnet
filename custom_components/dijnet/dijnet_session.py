# pylint: disable=bad-continuation
'''
Module for a Dijnet session.
'''
import logging
from datetime import datetime
from types import TracebackType
from typing import Optional, Type

import aiohttp

_LOGGER = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
ROOT_URL = 'https://www.dijnet.hu'


class DijnetSession:
    '''
    DijnetSession class represents a session at Dijnet.
    '''

    def __init__(self):
        '''
        Initialize a new instance of DijnetSession class.
        '''
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)

    async def get_root_page(self) -> bytes:
        '''
        Loads the root page content of Dijnet.

        Returns
        -------
        bytes
            The root page content.
        '''
        async with self._session.get(ROOT_URL) as response:
            return await response.read()

    async def get_main_page(self) -> bytes:
        '''
        Loads the main page content of Dijnet after login.

        Returns
        -------
        bytes
            The main page content.
        '''
        _LOGGER.debug('Getting main page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/main') as response:
            return await response.read()

    async def get_new_providers_page(self) -> bytes:
        '''
        Loads the new providers page content of Dijnet after login.

        Returns
        -------
        bytes
            The new providers page content.
        '''
        _LOGGER.debug('Getting regszolg_new page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/regszolg_new') as response:
            return await response.read()

    async def get_registered_providers_page(self) -> bytes:
        '''
        Loads the registered providers page content of Dijnet after login.

        Returns
        -------
        bytes
            The registered providers page content.
        '''
        _LOGGER.debug('Getting regszolg_list page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/regszolg_list') as response:
            return await response.read()

    async def get_invoice_page(self, index: int) -> bytes:
        '''
        Loads the invoice page content for the specified invoice index.

        Parameters
        ----------
        index: int
            The index of the invoice.

        Returns
        -------
        bytes
            The invoice page content.
        '''
        _LOGGER.debug('Getting szamla_select page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/szamla_select?vfw_coll=szamla_list&vfw_rowid={index}&exp=K') as response:
            return await response.read()

    async def get_invoice_history_page(self) -> bytes:
        '''
        Loads the invoice history page content.

        Returns
        -------
        bytes
            The invoice history page content.
        '''
        _LOGGER.debug('Getting szamla_hist page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/szamla_hist') as response:
            return await response.read()

    async def get_invoice_list_page(self) -> bytes:
        '''
        Loads the invoice list page content.

        Returns
        -------
        bytes
            The invoice list page content.
        '''
        _LOGGER.debug('Getting szamla_list page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/szamla_list') as response:
            return await response.read()

    async def get_invoice_download_page(self) -> bytes:
        '''
        Loads the invoice download page content.

        Returns
        -------
        bytes
            The invoice download page content.
        '''
        _LOGGER.debug('Getting szamla_letolt page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/szamla_letolt') as response:
            return await response.read()

    async def get_invoice_search_page(self) -> bytes:
        '''
        Loads the invoice search page content.

        Returns
        -------
        bytes
            The invoice search page content.
        '''
        _LOGGER.debug('Getting szamla_search page.')
        async with self._session.get(f'{ROOT_URL}/ekonto/control/szamla_search') as response:
            return await response.read()

    async def post_search_invoice(
        self,
        provider_name: str,
        reg_id: str,
        from_date: str,
        to_date: str
    ):
        '''
        Executes an invoice search with the specified parameters

        Parameters
        ----------
        provider_name: str
            The name of the provider.
        reg_id: str
            The reg id.
        from_date: str
            The search date interval start as date iso string.
        to_date: str
            The search date interval end as date iso string.

        Returns
        -------
        bytes
            The search result.
        '''
        _LOGGER.debug('Posting search to szamla_search_submit.')
        async with self._session.post(
            f'{ROOT_URL}/ekonto/control/szamla_search_submit',
            data={
                'vfw_form': 'szamla_search_submit',
                'vfw_coll': 'szamla_search_params',
                'szlaszolgnev': provider_name,
                'regszolgid': reg_id,
                'datumtol': datetime.fromisoformat(from_date).strftime(DATE_FORMAT),
                'datumig': datetime.fromisoformat(to_date).strftime(DATE_FORMAT)
            }
        ) as response:
            return await response.read()

    async def download(self, url: str) -> bytes:
        '''
        Downloads the content of the specified url.

        Parameters
        ----------
        url: str
            The url to download

        Returns
        -------
        bytes
            The downloaded content.
        '''
        _LOGGER.debug('Downloading file: %s', url)
        async with self._session.get(url) as response:
            return await response.read()

    async def post_login(self, username: str, password: str) -> bool:
        '''
        Posts the login information to Dijnet.

        Parameters
        ----------
        username: str
            The username.
        password: str
            The password.

        Returns
        -------
        bool
            The value indicates whether the login was successful.
        '''
        _LOGGER.debug('Posting login information to login_check_ajax.')
        async with self._session.post(
                'https://www.dijnet.hu/ekonto/login/login_check_ajax',
                data={
                    "username": username,
                    "password": password
                }
        ) as response:
            json = await response.json(content_type='text/plain')
            if not json['success']:
                _LOGGER.warning(json)
            return json['success']
