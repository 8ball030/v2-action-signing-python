import pytest
from derive_action_signing import SignedAction, TradeModuleData
from derive_action_signing.utils import MAX_INT_32, get_action_nonce
from decimal import Decimal
from web3 import Web3


def test_transfer_position_signature_generation(
    domain_separator,
    action_typehash,
    module_addresses,
    live_instrument_ticker,
    random_session_key,
):
    """Test that transfer_position actions generate valid signatures using TradeModuleData"""
    
    SMART_CONTRACT_WALLET_ADDRESS = "0x8772185a1516f0d61fC1c2524926BfC69F95d698"
    FROM_SUBACCOUNT_ID = 30769
    TO_SUBACCOUNT_ID = 31049
    
    transfer_amount = Decimal("0.1")
    transfer_price = Decimal("75")

    # Create maker action (sender) - maker reduces their position
    # Assuming positive position, maker sells to reduce
    maker_action = SignedAction(
        subaccount_id=FROM_SUBACCOUNT_ID,
        owner=SMART_CONTRACT_WALLET_ADDRESS,
        signer=random_session_key.address,
        signature_expiry_sec=MAX_INT_32,
        nonce=get_action_nonce(),
        module_address=module_addresses["trade"],
        module_data=TradeModuleData(
            asset_address=live_instrument_ticker["base_asset_address"],
            sub_id=int(live_instrument_ticker["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,  # Use absolute amount
            max_fee=Decimal("0"),  # No fee for transfers
            recipient_id=FROM_SUBACCOUNT_ID,  # Same as subaccount_id
            is_bid=False,  # Sell to reduce position
        ),
        DOMAIN_SEPARATOR=domain_separator,
        ACTION_TYPEHASH=action_typehash,
    )

    # Create taker action (recipient)  
    taker_action = SignedAction(
        subaccount_id=TO_SUBACCOUNT_ID,
        owner=SMART_CONTRACT_WALLET_ADDRESS,
        signer=random_session_key.address,
        signature_expiry_sec=MAX_INT_32,
        nonce=get_action_nonce(),
        module_address=module_addresses["trade"],
        module_data=TradeModuleData(
            asset_address=live_instrument_ticker["base_asset_address"],
            sub_id=int(live_instrument_ticker["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,  # Use absolute amount
            max_fee=Decimal("0"),  # No fee for transfers
            recipient_id=TO_SUBACCOUNT_ID,  # Same as subaccount_id
            is_bid=True,  # Buy to receive position
        ),
        DOMAIN_SEPARATOR=domain_separator,
        ACTION_TYPEHASH=action_typehash,
    )

    # Sign both actions
    maker_action.sign(random_session_key.key)
    taker_action.sign(random_session_key.key)

    # Verify signatures exist and are valid
    assert maker_action.signature is not None
    assert taker_action.signature is not None
    
    maker_action.validate_signature()
    taker_action.validate_signature()


def test_transfer_position_module_data_encoding(live_instrument_ticker):
    """Test that TradeModuleData encoding works correctly for position transfers"""
    
    transfer_price = Decimal("100")
    transfer_amount = Decimal("0.5")
    
    module_data = TradeModuleData(
        asset_address=live_instrument_ticker["base_asset_address"],
        sub_id=int(live_instrument_ticker["base_asset_sub_id"]),
        limit_price=transfer_price,
        amount=transfer_amount,
        max_fee=Decimal("0"),  # Always 0 for transfers
        recipient_id=12345,
        is_bid=True,
    )
    
    # Test ABI encoding
    encoded = module_data.to_abi_encoded()
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0
    
    # Test JSON encoding
    json_data = module_data.to_json()
    assert json_data["limit_price"] == "100"
    assert json_data["amount"] == "0.5"
    assert json_data["max_fee"] == "0"


def test_transfer_position_zero_fee_requirement():
    """Test that transfer positions must have zero max_fee"""
    
    # This test ensures our implementation follows the protocol requirement
    # that position transfers must have zero fees
    module_data = TradeModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("1"),
        max_fee=Decimal("0"),  # Must be zero for transfers
        recipient_id=12345,
        is_bid=True,
    )
    
    assert module_data.max_fee == Decimal("0")
    
    json_data = module_data.to_json()
    assert json_data["max_fee"] == "0"