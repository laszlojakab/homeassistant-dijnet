"""
The calendar module for Dijnet integration.
"""

# pylint: disable=bad-continuation
import logging
from datetime import datetime, timedelta
from typing import Any

from dateutil import tz
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import DijnetController, Invoice, InvoiceIssuer, PaidInvoice, get_controller

_LOGGER = logging.getLogger(__name__)


class DijnetPaymentCalendarEventDevice(CalendarEntity):
    """
    Represents the Dijnet payment calendar event device.
    """

    def __init__(
        self,
        controller: DijnetController,
        config_entry_id: str,
        invoice_issuer: InvoiceIssuer,
        provider: str,
    ):
        """
        Initialize a new instance of DijnetPaymentCalendarEventDevice class.

        Args:
          controller:
            The Dijnet controller instance.
          config_entry_id:
            The config_entry.entry_id which created the instance.
          invoice_issuer:
            The invoice issuer instance.
          provider:
            The provider name.
        """
        self._controller = controller
        self._invoice_issuer = invoice_issuer
        self._provider = provider
        self._attr_name = f"Dijnet - {provider} fizetési naptár"
        self._attr_unique_id = f"{config_entry_id}_{invoice_issuer.issuer}_{invoice_issuer.issuer_id}_{provider}_payment"
        self._unpaid_invoices: list[Invoice] = []
        self._paid_invoices: list[PaidInvoice] = []
        self._event: CalendarEvent | None = None
        self._attr_entity_registry_enabled_default = False
        self._all_events = []

    @property
    def event(self) -> dict[str, Any]:
        """
        Gets the next upcoming payment event.
        """
        return self._event

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
        """
        Updates the next event in the calendar.
        """
        await self._update_invoices()
        if len(self._unpaid_invoices) == 0:
            self._event = None
        else:
            self._event = self._get_event(self._unpaid_invoices[0])

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """
        Return calendar events within a datetime range.

        Args:
          hass:
            The Home Assistant instance.
          start_date: datetime
            The datetime range start.
          end_date: datetime
            The datetime range end.
        """
        await self._update_invoices()
        local_zone = tz.tzlocal()
        start_date_as_date = start_date.astimezone(local_zone).replace(tzinfo=None).date()
        end_date_as_date = end_date.astimezone(local_zone).replace(tzinfo=None).date()

        result: list[CalendarEvent] = []
        for invoice in self._unpaid_invoices:
            latest_start = max(start_date_as_date, invoice.issuance_date)
            earliest_end = min(end_date_as_date, max(invoice.deadline, datetime.now().date()))
            delta = (earliest_end - latest_start).days + 1
            overlap = delta > 0
            if overlap:
                result.append(self._get_event(invoice))

        for invoice in self._paid_invoices:
            latest_start = max(start_date_as_date, invoice.issuance_date)
            earliest_end = min(end_date_as_date, invoice.paid_at)
            delta = (earliest_end - latest_start).days + 1
            overlap = delta > 0
            if overlap:
                result.append(self._get_event(invoice))

        return result

    async def _update_invoices(self):
        self._unpaid_invoices = [
            unpaid_invoice
            for unpaid_invoice in await self._controller.get_unpaid_invoices()
            if unpaid_invoice.display_name == self._invoice_issuer.display_name
            and unpaid_invoice.provider == self._provider
        ]
        self._paid_invoices = [
            paid_invoice
            for paid_invoice in await self._controller.get_paid_invoices()
            if paid_invoice.display_name == self._invoice_issuer.display_name
            and paid_invoice.provider == self._provider
        ]

    def _get_event(self, invoice: Invoice) -> CalendarEvent:
        if isinstance(invoice, PaidInvoice):
            end_date = invoice.paid_at
            if invoice.paid_at > invoice.deadline:
                summary_additional_info = " - fizetési határidőn túl rendezve"
            else:
                summary_additional_info = " - rendezve"
        else:
            end_date = max(invoice.deadline, datetime.now().date())
            if end_date > invoice.deadline:
                summary_additional_info = " - lejárt fizetési határidő"
            else:
                summary_additional_info = ""

        end_date = end_date + timedelta(days=1)

        return CalendarEvent(
            invoice.issuance_date,
            end_date,
            f"{invoice.provider} befizetés{summary_additional_info}",
            f"{invoice.provider} befizetés, összeg: {invoice.amount!s}, határidő: {invoice.deadline.strftime('%Y.%m.%d')}",
            "https://dijnet.hu/",
        )


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """
    Setup of Dijnet calendars for the specified config_entry.

    Args:
      hass:
        The Home Assistant instance.
      config_entry:
        The config entry which is used to create sensors.
      async_add_entities:
        The callback which can be used to add new entities to Home Assistant.

    Returns:
      The value indicates whether the setup succeeded.
    """
    _LOGGER.info("Setting up Dijnet calendar events.")

    controller = get_controller(hass, config_entry.data[CONF_USERNAME])

    async_add_entities(
        [
            DijnetPaymentCalendarEventDevice(controller, config_entry.entry_id, issuer, provider)
            for issuer in await controller.get_issuers()
            for provider in issuer.providers
        ]
    )

    _LOGGER.info("Setting up Dijnet calendar events completed.")
