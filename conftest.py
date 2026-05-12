# makes sure pytest can find the backend package from the project root
# basically just adds the project root to sys.path

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
