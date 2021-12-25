# pylint: disable=bad-continuation
'''
The configuration flow module for Dijnet integration.
'''
import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant.config_entries import (HANDLERS, ConfigEntry, ConfigFlow,
                                          OptionsFlow)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DOWNLOAD_DIR, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DijnetOptionsFlowHandler(OptionsFlow):
    '''Handle Dijnet options.'''

    def __init__(self, config_entry: ConfigEntry) -> None:
        '''
        Initialize a new instance of DijnetOptionsFlowHandler class.

        Parameters
        ----------
        config_entry: homeassistant.config_entries.ConfigEntry
            The config entry of the integration.

        Returns
        -------
        None
        '''
        self.data = config_entry.data

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> FlowResult:
        '''
        Handles Dijnet configuration init step.

        Parameters
        ----------
        user_input: Dict[str, Any]
            The dictionary contains the settings entered by the user
            on the configuration screen.
        '''
        if user_input is not None:
            self.data = self.data | user_input

            return self.async_create_entry(
                title=f'Dijnet ({self.data[CONF_USERNAME]})', data=self.data
            )

        options = {
            vol.Required(
                CONF_PASSWORD,
                default=self.data[CONF_PASSWORD]
            ): str,
            vol.Optional(
                CONF_DOWNLOAD_DIR,
                default=self.data.get(CONF_DOWNLOAD_DIR)
            ): str
        }

        return self.async_show_form(step_id='init', data_schema=vol.Schema(options))


@HANDLERS.register(DOMAIN)
class DijnetConfigFlow(ConfigFlow, domain=DOMAIN):
    '''
    Configuration flow handler for Dijnet integration.
    '''
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigFlow) -> DijnetOptionsFlowHandler:
        '''
        Gets the options flow handler for the integration.

        Parameters
        ----------
        config_entry: homeassistant.config_entries.ConfigEntry
            The config entry of the integration.

        Returns
        -------
        DijnetOptionsFlowHandler
            The options flow handler for the integration.
        '''
        return DijnetOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_info: Dict[str, Any]) -> FlowResult:
        '''
        Handles the step when integration added from the UI.
        '''
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_DOWNLOAD_DIR): str
        })

        if user_info is not None:
            await self.async_set_unique_id(user_info[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            data = {
                CONF_USERNAME: user_info[CONF_USERNAME],
                CONF_PASSWORD: user_info[CONF_PASSWORD],
                CONF_DOWNLOAD_DIR: user_info.get(CONF_DOWNLOAD_DIR, '')
            }

            return self.async_create_entry(
                title=f'Dijnet ({user_info[CONF_USERNAME]})', data=data
            )

        return self.async_show_form(
            step_id='user',
            data_schema=data_schema,
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> FlowResult:
        '''
        Handles the yaml configuration import step.
        '''
        _LOGGER.debug('Importing Dijnet config from yaml.')

        await self.async_set_unique_id(import_config[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f'Dijnet ({import_config[CONF_USERNAME]})', data=import_config
        )
