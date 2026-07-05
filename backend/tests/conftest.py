import os
import sys

# Make the backend src tree importable exactly as the app imports it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
