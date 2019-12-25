# homeassistant-dijnet
[Dijnet](https://www.dijnet.hu) integration for Home Assistant

## Usage:
```yaml
sensor:
  - platform: dijnet
    username: !secret dijnet_username
    password: !secret dijnet_password
```

```yaml
binary_sensor:
  - platform: dijnet
    username: !secret dijnet_username
    password: !secret dijnet_password
```
