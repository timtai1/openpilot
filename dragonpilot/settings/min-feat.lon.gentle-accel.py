from dragonpilot.settings import tr

ITEMS = [
  {
    "section": "Longitudinal",
    "key": "dp_lon_smooth_accel",
    "type": "text_spin_button_item",
    "title": lambda: tr("Gentle Acceleration"),
    "description": lambda: tr("Scales maximum acceleration during takeoff and cruise (0.5x - 1.0x). Default is 0.5x. Smoothes out aggressive throttle when lead cars pull away."),
    "options": ["0.5x", "0.6x", "0.7x", "0.8x", "0.9x", "1.0x"],
    "condition": "openpilotLongitudinalControl",
    "flags": "PERSISTENT",
    "param_type": "INT",
    "default": "0",
  },
]
