import pytest
from derive_action_signing import SignedAction, MakerTransferPositionModuleData, TakerTransferPositionModuleData
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
    """Test that transfer_position actions generate valid signatures using wrapper classes"""
    
    SMART_CONTRACT_WALLET_ADDRESS = "0x8772185a1516f0d61fC1c2524926BfC69F95d698"
    FROM_SUBACCOUNT_ID = 30769
    TO_SUBACCOUNT_ID = 31049
    
    transfer_amount = Decimal("0.1")
    transfer_price = Decimal("75")
    position_amount = Decimal("1.0")  # Positive position

    # Create maker action (sender) - maker reduces their position
    maker_action = SignedAction(
        subaccount_id=FROM_SUBACCOUNT_ID,
        owner=SMART_CONTRACT_WALLET_ADDRESS,
        signer=random_session_key.address,
        signature_expiry_sec=MAX_INT_32,
        nonce=get_action_nonce(),
        module_address=module_addresses["trade"],
        module_data=MakerTransferPositionModuleData(
            asset_address=live_instrument_ticker["base_asset_address"],
            sub_id=int(live_instrument_ticker["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,
            recipient_id=FROM_SUBACCOUNT_ID,
            position_amount=position_amount,
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
        module_data=TakerTransferPositionModuleData(
            asset_address=live_instrument_ticker["base_asset_address"],
            sub_id=int(live_instrument_ticker["base_asset_sub_id"]),
            limit_price=transfer_price,
            amount=transfer_amount,
            recipient_id=TO_SUBACCOUNT_ID,
            position_amount=position_amount,
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
    
    # Test wrapper class behavior
    assert maker_action.module_data.get_direction() == "sell"  # Maker sells to reduce long position
    assert taker_action.module_data.get_direction() == "buy"   # Taker buys to receive position


def test_transfer_position_module_data_encoding(live_instrument_ticker):
    """Test that wrapper classes encoding works correctly for position transfers"""
    
    transfer_price = Decimal("100")
    transfer_amount = Decimal("0.5")
    position_amount = Decimal("2.0")  # Positive position
    
    # Test maker wrapper class
    maker_module_data = MakerTransferPositionModuleData(
        asset_address=live_instrument_ticker["base_asset_address"],
        sub_id=int(live_instrument_ticker["base_asset_sub_id"]),
        limit_price=transfer_price,
        amount=transfer_amount,
        recipient_id=12345,
        position_amount=position_amount,
    )
    
    # Test ABI encoding
    encoded = maker_module_data.to_abi_encoded()
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0
    
    # Test JSON encoding
    json_data = maker_module_data.to_json()
    assert json_data["limit_price"] == "100"
    assert json_data["amount"] == "0.5"
    assert json_data["max_fee"] == "0"
    
    # Test direction logic
    assert maker_module_data.get_direction() == "sell"  # Reducing long position


def test_transfer_position_zero_fee_requirement():
    """Test that transfer positions automatically enforce zero max_fee"""
    
    # Test that wrapper classes automatically set max_fee to 0
    maker_module_data = MakerTransferPositionModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("1"),
        recipient_id=12345,
        position_amount=Decimal("1"),  # Positive position
    )
    
    taker_module_data = TakerTransferPositionModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("1"),
        recipient_id=67890,
        position_amount=Decimal("1"),  # Positive position
    )
    
    # Verify both automatically have zero fees
    assert maker_module_data.to_json()["max_fee"] == "0"
    assert taker_module_data.to_json()["max_fee"] == "0"


def test_transfer_position_direction_logic():
    """Test that maker/taker direction logic works correctly for different position types"""
    
    # Test with positive position (long)
    positive_position = Decimal("1")
    
    maker_long = MakerTransferPositionModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("0.5"),
        recipient_id=12345,
        position_amount=positive_position,
    )
    
    taker_long = TakerTransferPositionModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("0.5"),
        recipient_id=67890,
        position_amount=positive_position,
    )
    
    # For positive position: maker sells to reduce, taker buys to receive
    assert maker_long.get_direction() == "sell"
    assert taker_long.get_direction() == "buy"
    
    # Test with negative position (short)
    negative_position = Decimal("-1")
    
    maker_short = MakerTransferPositionModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("0.5"),
        recipient_id=12345,
        position_amount=negative_position,
    )
    
    taker_short = TakerTransferPositionModuleData(
        asset_address="0x1234567890123456789012345678901234567890",
        sub_id=1,
        limit_price=Decimal("100"),
        amount=Decimal("0.5"),
        recipient_id=67890,
        position_amount=negative_position,
    )
    
    # For negative position: maker buys to reduce, taker sells to receive
    assert maker_short.get_direction() == "buy"
    assert taker_short.get_direction() == "sell"