from dragonpilot.settings import tr

ITEMS = [
  {
    "section": "Lateral",
    "key": "dp_lat_toyota_cc_curve",
    "type": "toggle_item",
    "title": lambda: tr("Toyota CC Curve Tuning"),
    "description": lambda: tr("Smooths out lateral jerk feedforward and reduces PID sensitivity on curve entry, tailored for Toyota Corolla Cross to prevent excessive initial steering angle and wobble."),
    "flags": "PERSISTENT",
    "param_type": "BOOL",
    "default": "1",
  },
]
