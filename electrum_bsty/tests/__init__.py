import asyncio
import os
import unittest
import threading
import tempfile
import shutil

import electrum_bsty as electrum
import electrum_bsty.logging
from electrum_bsty import constants
from electrum_bsty import util


# Set this locally to make the test suite run faster.
# If set, unit tests that would normally test functions with multiple implementations,
# will only be run once, using the fastest implementation.
# e.g. libsecp256k1 vs python-ecdsa. pycryptodomex vs pyaes.
FAST_TESTS = False


electrum_bsty.logging._configure_stderr_logging()

electrum_bsty.util.AS_LIB_USER_I_WANT_TO_MANAGE_MY_OWN_ASYNCIO_LOOP = True


class ElectrumTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class for our unit tests."""

    TESTNET = False
    # maxDiff = None  # for debugging

    # some unit tests are modifying globals... so we run sequentially:
    _test_lock = threading.Lock()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.TESTNET:
            constants.set_testnet()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls.TESTNET:
            constants.set_mainnet()

    def setUp(self):
        self._test_lock.acquire()
        super().setUp()
        self.electrum_path = tempfile.mkdtemp()
        assert util._asyncio_event_loop is None, "global event loop already set?!"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        loop = util.get_asyncio_loop()
        # IsolatedAsyncioTestCase creates event loops with debug=True, which makes the tests take ~4x time
        if not (os.environ.get("PYTHONASYNCIODEBUG") or os.environ.get("PYTHONDEVMODE")):
            loop.set_debug(False)
        util._asyncio_event_loop = loop

    def tearDown(self):
        shutil.rmtree(self.electrum_path)
        super().tearDown()
        util._asyncio_event_loop = None  # cleared here, at the ~last possible moment. asyncTearDown is too early.
        self._test_lock.release()


def as_testnet(func):
    """Function decorator to run a single unit test in testnet mode.

    NOTE: this is inherently sequential; tests running in parallel would break things
    """
    old_net = constants.net
    if asyncio.iscoroutinefunction(func):
        async def run_test(*args, **kwargs):
            try:
                constants.set_testnet()
                return await func(*args, **kwargs)
            finally:
                constants.net = old_net
    else:
        def run_test(*args, **kwargs):
            try:
                constants.set_testnet()
                return func(*args, **kwargs)
            finally:
                constants.net = old_net
    return run_test
