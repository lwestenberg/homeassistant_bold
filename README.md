# home_assistant_bold

## Installation

- Copy the bold folder to config/custom_components/
- Restart Home Assistant
- Install the integration from the Integrations list in Home Assistant

## Development

Run the compatibility checks with a Python version supported by Home Assistant:

```sh
python3 -m pip install homeassistant bold_smart_lock==0.3.9
python3 -m unittest discover -s tests -v
```
