# NOTE:
# There are 3 types of transfers, each using different module data types:
# 1. private/transfer_erc20 routes uses the TransferERC20ModuleData type for signatures
# 2. private/transfer_position route uses the TradeModuleData type for signatures
# 3. private/transfer_positions (plural) uses the MakerTransferPositionsModuleData and TakerTransferPositionsModuleData types for signatures

# This example goes over #2

import json
import requests
from web3 import Web3
from decimal import Decimal
import time
from derive_action_signing import (
    SignedAction,
    TradeModuleData,
    utils,
)


def main():
    ########################################
    # Get existing testnet subaccount info #
    ########################################
    # SMART_CONTRACT_WALLET_ADDRESS
    DERIVE_CONTRACT_WALLET_ADDRESS = "0xeda0656dab4094C7Dc12F8F12AF75B5B3Af4e776"
    SESSION_KEY_PRIVATE_KEY = "0x83ee63dc6655509aabce0f7e501a31c511195e61e9d0e9917f0a55fd06041a66"
    web3_client = Web3()
    session_key_wallet = web3_client.eth.account.from_key(SESSION_KEY_PRIVATE_KEY)

    FROM_SUBACCOUNT_ID = 137402
    TO_SUBACCOUNT_ID = 137404

    #############################################
    # Protocol Constants from docs.lyra.finance #
    #############################################

    DOMAIN_SEPARATOR = "0x9bcf4dc06df5d8bf23af818d5716491b995020f377d3b7b64c29ed14e3dd1105"
    ACTION_TYPEHASH = "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17"
    # single position transfers use TRADE_MODULE_ADDRESS
    TRADE_MODULE_ADDRESS = "0x87F2863866D85E3192a35A73b388BD625D83f2be"
    # WebSocket for position opening
    WEBSOCKET_URL = "wss://api-demo.lyra.finance/ws"

    ###################################
    # Get a live instrument to transfer #
    ###################################

    # Get a currently active instrument
    url = "https://api-demo.lyra.finance/public/get_instruments"
    response = requests.post(
        url,
        json={
            "currency": "ETH",
            "instrument_type": "option",
            "expired": False
        },
        headers={"accept": "application/json", "content-type": "application/json"},
    )
    instruments = response.json()["result"]
    # Find an active instrument
    active_instruments = [inst for inst in instruments if inst["is_active"]]
    if not active_instruments:
        print("No active instruments found")
        return
    instrument = active_instruments[0]  # Use the first active instrument
    print(f"Selected instrument for transfer: {instrument['instrument_name']}")
    
    ###################
    # Define Transfer #
    ###################

    # Transfer amount and price for the position (matching opened position)
    transfer_amount = Decimal("1")
    transfer_price = Decimal("100")

    # Create the maker order (from sender subaccount)
    maker_action = SignedAction(
        subaccount_id=FROM_SUBACCOUNT_ID,
        owner=DERIVE_CONTRACT_WALLET_ADDRESS,
        signer=session_key_wallet.address,
        signature_expiry_sec=utils.MAX_INT_32,
        nonce=utils.get_action_nonce(),
        module_address=TRADE_MODULE_ADDRESS,
        module_data=TradeModuleData(
            asset_address=instrument["base_asset_address"],
            sub_id=int(instrument["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,  
            max_fee=Decimal("0"),  # No fee for position transfers
            recipient_id=TO_SUBACCOUNT_ID,
            is_bid=False,  # This is a sell order (maker)
        ),
        DOMAIN_SEPARATOR=DOMAIN_SEPARATOR,
        ACTION_TYPEHASH=ACTION_TYPEHASH,
    )

    maker_action.sign(session_key_wallet.key)

    # Create the taker order (to recipient subaccount)
    taker_action = SignedAction(
        subaccount_id=TO_SUBACCOUNT_ID,
        owner=DERIVE_CONTRACT_WALLET_ADDRESS,
        signer=session_key_wallet.address,
        signature_expiry_sec=utils.MAX_INT_32,
        nonce=utils.get_action_nonce(),
        module_address=TRADE_MODULE_ADDRESS,
        module_data=TradeModuleData(
            asset_address=instrument["base_asset_address"],
            sub_id=int(instrument["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,
            max_fee=Decimal("0"),  # No fee for position transfers
            recipient_id=FROM_SUBACCOUNT_ID,
            is_bid=True,  # This is a buy order (taker)
        ),
        DOMAIN_SEPARATOR=DOMAIN_SEPARATOR,
        ACTION_TYPEHASH=ACTION_TYPEHASH,
    )

    taker_action.sign(session_key_wallet.key)
    #####################
    # Initiate Transfer #
    #####################

    # Create request - API requires direction and instrument_name fields
    maker_params = maker_action.to_json()
    maker_params["direction"] = "sell"
    maker_params["instrument_name"] = instrument["instrument_name"]
    
    taker_params = taker_action.to_json()  
    taker_params["direction"] = "buy"
    taker_params["instrument_name"] = instrument["instrument_name"]
    
    print(f"Using instrument: {instrument['instrument_name']}")
    print(f"Transfer amount: {transfer_amount}")
    print("DEBUG: Maker params:", json.dumps(maker_params, indent=2, default=str))
    print("DEBUG: Taker params:", json.dumps(taker_params, indent=2, default=str))
    
    response = requests.post(
        "https://api-demo.lyra.finance/private/transfer_position",
        json={
            "wallet": DERIVE_CONTRACT_WALLET_ADDRESS,
            "maker_params": maker_params,
            "taker_params": taker_params,
        },
        headers={
            **utils.sign_rest_auth_header(web3_client, DERIVE_CONTRACT_WALLET_ADDRESS, SESSION_KEY_PRIVATE_KEY),
            "accept": "application/json",
            "content-type": "application/json",
        },
    )
    try:
        response_data = response.json()
        if response.status_code == 200 and 'result' in response_data:
            print("Transfer Position Success:", json.dumps(response_data, indent=4))
        else:
            print("Transfer Position Error:", json.dumps(response_data, indent=4))
    except requests.exceptions.JSONDecodeError:
        print(f"Invalid JSON response: {response.text}")


if __name__ == "__main__":
    main()
