# content of conftest.py
import pytest
import requests
import random
from web3 import Account
from eth_account.signers.base import BaseAccount

###############################################################################
# Constants taken from https://docs.derive.finance/reference/protocol-constants #
###############################################################################


@pytest.fixture
def random_wallet() -> BaseAccount:
    return Account.create()


@pytest.fixture
def random_session_key() -> BaseAccount:
    return Account.create()


@pytest.fixture
def domain_separator():
    return "0x9bcf4dc06df5d8bf23af818d5716491b995020f377d3b7b64c29ed14e3dd1105"


@pytest.fixture
def action_typehash():
    return "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17"


@pytest.fixture
def module_addresses():
    return {
        "trade": "0x87F2863866D85E3192a35A73b388BD625D83f2be",
        "withdraw": "0xe850641C5207dc5E9423fB15f89ae6031A05fd92",
        "transfer_erc20": "0x0CFC1a4a90741aB242cAfaCD798b409E12e68926",
        "rfq": "0x4E4DD8Be1e461913D9A5DBC4B830e67a8694ebCa",
        "deposit": "0x43223Db33AdA0575D2E100829543f8B04A37a1ec",
    }


#############################
# Requested via testnet API #
#############################


@pytest.fixture(scope="module")
def live_instrument_ticker():
    """
    Return all live ETH option tickers and extract sub_id.
    """
    return _get_live_instrument_ticker(nth=0)


@pytest.fixture(scope="module")
def second_live_instrument_ticker():
    """
    Return all live ETH option tickers and extract sub_id.
    """
    return _get_live_instrument_ticker(nth=1)

def _get_live_instrument_ticker(nth=0):
    url = "https://api-demo.lyra.finance/public/get_instruments"
    payload = {
        "expired": False,
        "instrument_type": "option",
        "currency": "ETH",
    }
    response = requests.post(
        url, json=payload, headers={"accept": "application/json", "content-type": "application/json"}
    )

    # return the first is_active true instrument
    for instrument in response.json()["result"]:
        if instrument["is_active"]:
            nth -= 1
        
        if nth == -1:
            return instrument

    raise ValueError("No active instrument found")