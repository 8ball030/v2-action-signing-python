from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from derive_action_signing.module_data.module_data import ModuleData
from derive_action_signing.module_data.trade import TradeModuleData


@dataclass
class TransferPositionModuleData(ModuleData, ABC):
    """Base class for position transfer module data"""

    asset_address: str
    sub_id: int
    limit_price: Decimal
    amount: Decimal
    recipient_id: int
    position_amount: Decimal  # Original position amount to determine direction

    _internal_trade_module_data: TradeModuleData = field(init=False, default=None)

    def __post_init__(self):
        self._internal_trade_module_data = TradeModuleData(
            asset_address=self.asset_address,
            sub_id=self.sub_id,
            limit_price=self.limit_price,
            amount=abs(self.amount),  # Use absolute amount
            max_fee=Decimal("0"),  # Always 0 for transfers
            recipient_id=self.recipient_id,
            is_bid=self._get_is_bid(),
        )

    @abstractmethod
    def _get_is_bid(self) -> bool:
        """Determine if this is a bid order based on position and role"""
        pass

    @abstractmethod
    def get_direction(self) -> str:
        """Return the direction string for API calls"""
        pass

    def to_abi_encoded(self):
        return self._internal_trade_module_data.to_abi_encoded()

    def to_json(self):
        return self._internal_trade_module_data.to_json()


@dataclass
class MakerTransferPositionModuleData(TransferPositionModuleData):
    """Maker always reduces their position"""

    def _get_is_bid(self) -> bool:
        # If position is positive -> sell (is_bid=False) to reduce long position
        # If position is negative -> buy (is_bid=True) to reduce short position
        return self.position_amount < 0

    def get_direction(self) -> str:
        """Return the direction for this maker (sell if reducing long, buy if reducing short)"""
        return "sell" if self.position_amount > 0 else "buy"


@dataclass
class TakerTransferPositionModuleData(TransferPositionModuleData):
    """Taker always receives the position (opposite of maker)"""

    def _get_is_bid(self) -> bool:
        # If maker reducing long position -> taker buys (is_bid=True)
        # If maker reducing short position -> taker sells (is_bid=False)
        return self.position_amount > 0

    def get_direction(self) -> str:
        """Return the direction for this taker (buy if receiving long, sell if receiving short)"""
        return "buy" if self.position_amount > 0 else "sell"
