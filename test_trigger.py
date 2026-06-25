import sys
import os

# Set dummy environment so app.py doesn't crash if it tries to run something on import
os.environ["PORT"] = "5000"

from app import mahabucha_daily_summary
print("Triggering daily summary...")
mahabucha_daily_summary()
print("Done!")
