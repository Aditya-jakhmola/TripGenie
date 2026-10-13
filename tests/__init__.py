# Import src.graph before anything else. The app does the same, and it is the
# one import order in which the src.graph <-> src.agents package cycle
# resolves. Importing src.agents first (as a test module might) hits the cycle.
import src.graph  # noqa: F401

import logging

# The code under test logs warnings on purpose (bad model output, failed
# lookups). Silence them so a passing run is clean to read.
logging.disable(logging.CRITICAL)