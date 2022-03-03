# homeassistant-dijnet

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/laszlojakab/homeassistant-dijnet?include_prereleases)
![GitHub](https://img.shields.io/github/license/laszlojakab/homeassistant-dijnet?)
![GitHub all releases](https://img.shields.io/github/downloads/laszlojakab/homeassistant-dijnet/total)
[![Donate](https://img.shields.io/badge/donate-Coffee-yellow.svg)](https://www.buymeacoffee.com/laszlojakab)

[Dijnet](https://www.dijnet.hu/) integration for [Home Assistant](https://www.home-assistant.io/)

## Installation

You can install this integration via [HACS](#hacs) or [manually](#manual).

### HACS

This integration is included in HACS. Search for the `Dijnet` integration and choose install. Reboot Home Assistant and configure the 'Dijnet' integration via the integrations page or press the blue button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dijnet)

### Manual

Copy the `custom_components/dijnet` to your `custom_components` folder. Reboot Home Assistant and configure the 'Dijnet' integration via the integrations page or press the blue button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dijnet)

## Features

- The integration provides services for every invoice issuer. Every invoice issuer could have multiple providers. For example DBH Zrt. invoice issuer handles invoices for FV Zrt. and FCSM Zrt. In that case the integration creates separate sensors for these providers.
- For all providers an invoice amount sensor is created. It contains the sum of unpaid amount for a provider. The details of the unpaid invoices can be read out from `unpaid_invoices` attribute of the sensor.
<!-- - For all providers a calendar entity is created. These entities are disabled by default. You can enable them by selecting 'Enable entity' toggle. The calendar entity registers an event for every incoming invoice. The event start date is the issuance date of the invoice. The event end date is the deadline of the invoice. If the invoices is paid before deadline, the end date of the event became the payment date. If the invoice is not paid until deadline the event end date will be today. -->

## Enable debug logging

The [logger](https://www.home-assistant.io/integrations/logger/) integration lets you define the level of logging activities in Home Assistant. Turning on debug mode will show more information about the running of the integration in the homeassistant.log file.

```yaml
logger:
  default: error
  logs:
    custom_components.dijnet: debug
```