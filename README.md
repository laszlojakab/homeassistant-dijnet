# homeassistant-dijnet
[Dijnet](https://www.dijnet.hu/) integration for [Home Assistant](https://www.home-assistant.io/)

## Usage:
```yaml
sensor:
  - platform: dijnet
    username: !secret dijnet_username
    password: !secret dijnet_password
```