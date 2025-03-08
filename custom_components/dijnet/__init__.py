"""Dijnet component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_DOWNLOAD_DIR,
    CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE,
    DATA_CONTROLLER,
    DOMAIN,
)
from .controller import DijnetController, is_controller_exists, set_controller

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:  # noqa: ARG001
    """
    Sets up the Dijnet component.

    Args:
      hass:
        The Home Assistant instance.
      config:
        The configuration.

    Returns:
      The value indicates whether the setup succeeded.

    """
    hass.data[DOMAIN] = {DATA_CONTROLLER: {}}
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """
    Initializes the sensors based on the config entry.

    Args:
      hass:
        The Home Assistant instance.
      config_entry:
        The config entry which contains information gathered by the config flow.

    Returns:
      The value indicates whether the setup succeeded.

    """
    if not is_controller_exists(hass, config_entry.data[CONF_USERNAME]):
        set_controller(
            hass,
            config_entry.data[CONF_USERNAME],
            DijnetController(
                config_entry.data[CONF_USERNAME],
                config_entry.data[CONF_PASSWORD],
                config_entry.data[CONF_DOWNLOAD_DIR],
                config_entry.data[CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE],
            ),
        )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(config_entry, ("sensor",))
    )

    return True


async def async_migrate_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """
    Migrates old entry.

    Args:
      hass:
        The Home Assistant instance.
      config_entry:
        The config entry to migrate.

    Returns:
      The value indicates whether the migration succeeded.
    """
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new_config_entry = {**config_entry.data}
        new_config_entry[CONF_ENCASHMENT_REPORTED_AS_PAID_AFTER_DEADLINE] = False

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new_config_entry)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
