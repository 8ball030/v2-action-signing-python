# NOTE:
# There are 3 types of transfers, each using different module data types:
# 1. private/transfer_erc20 routes uses the TransferERC20ModuleData type for signatures
# 2. private/transfer_position route uses the TradeModuleData type for signatures
# 3. private/transfer_positions (plural) uses the MakerTransferPositionsModuleData and TakerTransferPositionsModuleData types for signatures

# This example goes over #2

import json
import time
from decimal import ROUND_HALF_UP, Decimal

import requests
from web3 import Web3

from derive_action_signing import (
    SignedAction,
    MakerTransferPositionModuleData, 
    TakerTransferPositionModuleData,
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

    ###################################
    # Get user's positions and find instrument #
    ###################################

    # First get user's positions to find what instruments they have
    url = "https://api-demo.lyra.finance/private/get_positions"
    positions_response = requests.post(
        url,
        json={"subaccount_id": FROM_SUBACCOUNT_ID},
        headers={
            **utils.sign_rest_auth_header(
                web3_client, DERIVE_CONTRACT_WALLET_ADDRESS, SESSION_KEY_PRIVATE_KEY
            ),
            "accept": "application/json",
            "content-type": "application/json",
        },
    )
    positions_data = positions_response.json()["result"]

    if not positions_data["positions"]:
        print("No positions found")
        return

    # Get the first instrument from user's positions
    first_position = positions_data["positions"][0]
    instrument_name = first_position["instrument_name"]
    instrument_type = first_position["instrument_type"]

    print(f"Found user instrument: {instrument_name} ({instrument_type})")

    # Now get the full instrument details from get_instruments
    if instrument_type == "perp":
        url = "https://api-demo.lyra.finance/public/get_instruments"
        instruments_response = requests.post(
            url,
            json={"currency": "ETH", "instrument_type": "perp", "expired": False},
            headers={"accept": "application/json", "content-type": "application/json"},
        )
        instruments = instruments_response.json()["result"]
        instrument = next(
            inst for inst in instruments if inst["instrument_name"] == instrument_name
        )
    else:
        url = "https://api-demo.lyra.finance/public/get_instruments"
        instruments_response = requests.post(
            url,
            json={"currency": "ETH", "instrument_type": "option", "expired": False},
            headers={"accept": "application/json", "content-type": "application/json"},
        )
        instruments = instruments_response.json()["result"]
        instrument = next(
            inst for inst in instruments if inst["instrument_name"] == instrument_name
        )

    print(f"Selected instrument for transfer: {instrument['instrument_name']}")

    # Get position details for dynamic amount and price
    position = first_position
    position_amount = (
        Decimal(position["amount"]) if position["amount"] != "0" else Decimal("0.1")
    )  # Use 0.1 as minimum if no position
    position_price = (
        Decimal(position["mark_value"])
        if position["mark_value"] != "0"
        else Decimal(instrument.get("mark_price", "100"))
    )

    position_amount = position_amount.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    position_price = abs(
        position_price.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )

    print(f"Position amount: {position_amount}")
    print(f"Position average price: {position_price}")

    ###################
    # Define Transfer #
    ###################

    # Transfer amount and price from position data
    transfer_amount = abs(position_amount)  # Use absolute value for transfer amount
    transfer_price = position_price
    original_position_amount = Decimal(position["amount"])

    print(f"Original position amount: {original_position_amount}")
    print(f"Transfer amount: {transfer_amount}")
    print("Creating transfer-specific signed actions using inheritance-based wrapper classes...")

    # Create maker order parameters
    base_nonce = utils.get_action_nonce()
    maker_nonce = base_nonce
    maker_signature_expiry = utils.MAX_INT_32

    # Create taker order parameters - ensure different nonce
    taker_nonce = base_nonce + 1
    taker_signature_expiry = utils.MAX_INT_32

    maker_action = SignedAction(
        subaccount_id=FROM_SUBACCOUNT_ID,
        owner=DERIVE_CONTRACT_WALLET_ADDRESS,
        signer=session_key_wallet.address,
        signature_expiry_sec=maker_signature_expiry,
        nonce=maker_nonce,
        module_address=TRADE_MODULE_ADDRESS,
        module_data=MakerTransferPositionModuleData(
            asset_address=instrument["base_asset_address"],
            sub_id=int(instrument["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,
            recipient_id=FROM_SUBACCOUNT_ID,
            position_amount=original_position_amount,
        ),
        DOMAIN_SEPARATOR=DOMAIN_SEPARATOR,
        ACTION_TYPEHASH=ACTION_TYPEHASH,
    )

    taker_action = SignedAction(
        subaccount_id=TO_SUBACCOUNT_ID,
        owner=DERIVE_CONTRACT_WALLET_ADDRESS,
        signer=session_key_wallet.address,
        signature_expiry_sec=taker_signature_expiry,
        nonce=taker_nonce,
        module_address=TRADE_MODULE_ADDRESS,
        module_data=TakerTransferPositionModuleData(
            asset_address=instrument["base_asset_address"],
            sub_id=int(instrument["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,
            recipient_id=TO_SUBACCOUNT_ID,
            position_amount=original_position_amount,
        ),
        DOMAIN_SEPARATOR=DOMAIN_SEPARATOR,
        ACTION_TYPEHASH=ACTION_TYPEHASH,
    )

    # Sign the actions
    maker_action.sign(session_key_wallet.key)
    taker_action.sign(session_key_wallet.key)
    #####################
    # Initiate Transfer #
    #####################

    # Create transfer_position parameters using wrapper class directions
    maker_params = {
        "direction": maker_action.module_data.get_direction(),
        "instrument_name": instrument["instrument_name"],
        **maker_action.to_json(),
    }

    taker_params = {
        "direction": taker_action.module_data.get_direction(),
        "instrument_name": instrument["instrument_name"],
        **taker_action.to_json(),
    }

    print(f"Using instrument: {instrument['instrument_name']}")
    print(f"Transfer amount: {transfer_amount}")

    url = "https://api-demo.lyra.finance/private/transfer_position"
    response = requests.post(
        url,
        json={
            "wallet": DERIVE_CONTRACT_WALLET_ADDRESS,
            "maker_params": maker_params,
            "taker_params": taker_params,
        },
        headers={
            **utils.sign_rest_auth_header(
                web3_client, DERIVE_CONTRACT_WALLET_ADDRESS, SESSION_KEY_PRIVATE_KEY
            ),
            "accept": "application/json",
            "content-type": "application/json",
        },
    )

    try:
        response_data = response.json()
        if response.status_code == 200 and "result" in response_data:
            print("Transfer Position Success:", json.dumps(response_data, indent=4))
        else:
            print("Transfer Position Error:", json.dumps(response_data, indent=4))
    except requests.exceptions.JSONDecodeError:
        print(f"Invalid JSON response: {response.text}")


if __name__ == "__main__":
    main()
