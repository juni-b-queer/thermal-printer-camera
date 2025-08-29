import json
import utils.colors as colors

CONFIG_METADATA = {
    "countdown": {"increment": 0.25, "type": "float"},
    "photo_interval": {"increment": 0.25, "type": "float"},
    "photobooth_count": {"increment": 1, "type": "int"},
    "show_flash": {"increment": None, "type": "bool"},
    "flash_color": {"increment": None, "type": "select", "options": colors.COLOR_LIST}
}

def load_config(filepath="/home/pi/Desktop/picamera/config.json"):
    with open(filepath, 'r') as f:
        config = json.load(f)
    return config

def save_config(config, filepath="/home/pi/Desktop/picamera/config.json"):
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=4)  # indent for readability
