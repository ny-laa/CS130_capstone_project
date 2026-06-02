# makes sure pytest can find both import styles used across the test suite:
# adding both the project root and backend/ covers both without changing any test.

import sys
import os

_root = os.path.dirname(__file__)
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "backend"))
