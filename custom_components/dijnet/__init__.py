'''Dijnet component.'''

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import CONF_DOWNLOAD_DIR, DATA_CONTROLLER, DOMAIN
from .controller import is_controller_exists, set_controller, DijnetController


# pylint: disable=unused-argument
async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    '''
    Set up the Dijnet component.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    config: homeassistant.helpers.typing.ConfigType
        The configuration.

    Returns
    -------
    bool
        The value indicates whether the setup succeeded.
    '''
    hass.data[DOMAIN] = {DATA_CONTROLLER: {}}
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    '''
    Initialize the sensors based on the config entry.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    config_entry: homeassistant.config_entries.ConfigEntry
        The config entry which contains information gathered by the config flow.

    Returns
    -------
    bool
        The value indicates whether the setup succeeded.
    '''

    if not is_controller_exists(hass, config_entry.data[CONF_USERNAME]):
        set_controller(
            hass,
            config_entry.data[CONF_USERNAME],
            DijnetController(
                config_entry.data[CONF_USERNAME],
                config_entry.data[CONF_PASSWORD],
                config_entry.data[CONF_DOWNLOAD_DIR]
            )
        )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, 'sensor')
    )

    return True
