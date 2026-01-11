"""Entry point for running the package as a module.

Usage: python -m evt_parser [args]
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
