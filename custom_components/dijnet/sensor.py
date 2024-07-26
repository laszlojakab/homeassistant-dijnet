"""Support for Dijnet."""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, HomeAssistantType

from .const import CONF_DOWNLOAD_DIR, DOMAIN
from .controller import DijnetController, InvoiceIssuer, get_controller

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DOWNLOAD_DIR, default=""): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Import yaml config and initiates config flow for Dijnet integration."""

    # Check if entry config exists and skips import if it does.
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.warning(
            "Setting up Dijnet integration from yaml is deprecated. Please remove configuration from yaml."
        )
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """
    Setup of Dijnet sensors for the specified config_entry.

    Parameters
    ----------
    hass: homeassistant.helpers.typing.HomeAssistantType
        The Home Assistant instance.
    config_entry: homeassistant.helpers.typing.ConfigEntry
        The config entry which is used to create sensors.
    async_add_entities: homeassistant.helpers.entity_platform.AddEntitiesCallback
        The callback which can be used to add new entities to Home Assistant.

    Returns
    -------
    bool
        The value indicates whether the setup succeeded.
    """
    _LOGGER.info("Setting up Dijnet sensors.")

    controller = get_controller(hass, config_entry.data[CONF_USERNAME])

    for registered_invoice_issuer in await controller.get_issuers():
        async_add_entities(
            [
                InvoiceAmountSensor(
                    controller, config_entry.entry_id, registered_invoice_issuer, provider
                )
                for provider in registered_invoice_issuer.providers
            ]
        )
        _LOGGER.debug("Sensor added (%s)", registered_invoice_issuer)

    _LOGGER.info("Setting up Dijnet sensors completed.")
    return True


class InvoiceAmountSensor(SensorEntity):
    def __init__(
        self,
        controller: DijnetController,
        config_entry_id: str,
        invoice_issuer: InvoiceIssuer,
        provider: str,
    ):
        self._controller = controller
        self._invoice_issuer = invoice_issuer
        self._state = None
        self._attr_unique_id = f"{config_entry_id}_{invoice_issuer.issuer}_{invoice_issuer.issuer_id}_{provider}_amount"
        self._provider = provider
        self.entity_description = SensorEntityDescription(
            key="invoice_amount",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement="Ft",
            name=f"Dijnet - {provider} fizetendő összeg",
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://dijnet.hu/",
            manufacturer="Dijnet Zrt",
            identifiers={
                (DOMAIN, self._invoice_issuer.issuer + "|" + self._invoice_issuer.issuer_id)
            },
            name=self._invoice_issuer.display_name,
        )

    async def async_update(self):
        invoices = [
            invoice
            for invoice in await self._controller.get_unpaid_invoices()
            if invoice.display_name == self._invoice_issuer.display_name
            and invoice.provider == self._provider
        ]
        self._attr_native_value = sum([invoice.amount for invoice in invoices])
        self._attr_extra_state_attributes = {
            "unpaid_invoices": [invoice.to_dictionary() for invoice in invoices]
        }
