"""The configuration flow module for Dijnet integration."""

import logging
from typing import Any, Self

import voluptuous as vol
from homeassistant.config_entries import HANDLERS, ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DOWNLOAD_DIR, CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE, DOMAIN
from .dijnet_session import DijnetSession

_LOGGER = logging.getLogger(__name__)


class DijnetOptionsFlowHandler(OptionsFlow):
    """Handle Dijnet options."""

    def __init__(self: Self, config_entry: ConfigEntry) -> None:
        """
        Initialize a new instance of DijnetOptionsFlowHandler class.

        Args:
          config_entry:
            The config entry of the integration.

        """
        self.config_entry = config_entry

    async def async_step_init(self: Self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        Handles Dijnet configuration init step.

        Args:
          user_input:
            The dictionary contains the settings entered by the user
            on the configuration screen.

        """
        data_schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD, default=self.config_entry.data[CONF_PASSWORD]): str,
                vol.Optional(
                    CONF_DOWNLOAD_DIR, default=self.config_entry.data.get(CONF_DOWNLOAD_DIR)
                ): str,
                vol.Required(
                    CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE,
                    default=self.config_entry.data[CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE],
                ): bool,
            }
        )

        if user_input is not None:
            async with DijnetSession() as session:
                if not await session.post_login(
                    self.config_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
                ):
                    return self.async_show_form(
                        step_id="init",
                        data_schema=data_schema,
                        errors={"base": "invalid_username_or_password"},
                    )

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_entry.data | user_input
            )

            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(step_id="init", data_schema=data_schema)


@HANDLERS.register(DOMAIN)
class DijnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow handler for Dijnet integration."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigFlow) -> DijnetOptionsFlowHandler:
        """
        Gets the options flow handler for the integration.

        Args:
          config_entry:
            The config entry of the integration.

        Returns:
          The options flow handler for the integration.

        """
        return DijnetOptionsFlowHandler(config_entry)

    async def async_step_user(self: Self, user_input: dict[str, Any]) -> FlowResult:
        """
        Handles the step when integration added from the UI.

        Args:
          user_input:
            The dictionary contains the settings entered by the user
            on the configuration screen.

        Returns:
          The result of the flow step.
        """
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_DOWNLOAD_DIR): str,
                vol.Required(CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE): bool,
            }
        )

        if user_input is not None:
            async with DijnetSession() as session:
                if not await session.post_login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                ):
                    return self.async_show_form(
                        step_id="user",
                        data_schema=data_schema,
                        errors={CONF_USERNAME: "invalid_username_or_password"},
                    )

            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            data = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_DOWNLOAD_DIR: user_input.get(CONF_DOWNLOAD_DIR, ""),
                CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE: user_input[
                    CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE
                ],
            }

            return self.async_create_entry(title=f"Dijnet ({user_input[CONF_USERNAME]})", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_import(self: Self, import_config: dict[str, Any]) -> FlowResult:
        """Handles the yaml configuration import step."""
        _LOGGER.debug("Importing Dijnet config from yaml.")

        await self.async_set_unique_id(import_config[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Dijnet ({import_config[CONF_USERNAME]})", data=import_config
        )
