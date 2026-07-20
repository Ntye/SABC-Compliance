import os
import sys

# Make agent.py importable as a top-level module without packaging.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
