"""
Transaction utilities.
"""

import logging
from typing import Dict, Any, Tuple, Optional

from web3 import Web3
from web3.types import TxParams, HexBytes


logger = logging.getLogger(__name__)


def estimate_gas_with_buffer(web3: Web3, transaction: TxParams, buffer_percent: int = 20) -> int:
    """Estimate gas with buffer."""
    try:
        estimated_gas = web3.eth.estimate_gas(transaction)
        gas_with_buffer = int(estimated_gas * (1 + buffer_percent / 100))
        return gas_with_buffer
    except Exception as e:
        logger.warning(f"Gas estimation failed: {e}, using default")
        return 500000  # Default gas limit


def build_sign_send_transaction(
    web3: Web3,
    function_call,
    private_key: str,
    tx_params: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """Build, sign and send a transaction."""
    if not tx_params:
        tx_params = {}
        
    account = web3.eth.account.from_key(private_key)
    
    # Build transaction
    transaction = function_call.build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': tx_params.get('gas', None),
        'gasPrice': tx_params.get('gasPrice', None),
        'maxFeePerGas': tx_params.get('maxFeePerGas', None),
        'maxPriorityFeePerGas': tx_params.get('maxPriorityFeePerGas', None),
        'value': tx_params.get('value', 0),
    })
    
    # Remove None values
    transaction = {k: v for k, v in transaction.items() if v is not None}
    
    # Estimate gas if not provided
    if 'gas' not in transaction:
        transaction['gas'] = estimate_gas_with_buffer(web3, transaction)
    
    # Set gas price if not provided
    if 'gasPrice' not in transaction and 'maxFeePerGas' not in transaction:
        # Use EIP-1559 if supported
        try:
            base_fee = web3.eth.get_block('latest')['baseFeePerGas']
            max_priority_fee = web3.to_wei(2, 'gwei')
            transaction['maxFeePerGas'] = base_fee * 2 + max_priority_fee
            transaction['maxPriorityFeePerGas'] = max_priority_fee
            # Remove gasPrice if it exists
            transaction.pop('gasPrice', None)
        except Exception:
            # Fallback to legacy gas price
            transaction['gasPrice'] = web3.eth.gas_price
    
    # Sign transaction
    signed_txn = web3.eth.account.sign_transaction(transaction, private_key)
    
    # Send transaction
    tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    
    # Wait for receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] != 1:
        raise Exception(f"Transaction failed: {tx_hash.hex()}")
    
    return tx_hash.hex(), receipt