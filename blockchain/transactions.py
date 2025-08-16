"""
Transaction utilities.
"""

import logging
from typing import Dict, Any, Tuple, Optional
import time

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
    tx_params: Optional[Dict[str, Any]] = None,
    *,
    retries: int = 2,
    retry_sleep_seconds: float = 0.3,
    fee_bump_factor: float = 1.15,
) -> Tuple[str, Dict[str, Any]]:
    """Build, sign and send a transaction with basic nonce/fee retry logic.

    - Detects 'nonce too low' and refreshes nonce using 'pending'.
    - Handles 'already known' by waiting on the computed tx hash.
    - Bumps fees on retries to satisfy replacement requirements.
    """
    if not tx_params:
        tx_params = {}

    account = web3.eth.account.from_key(private_key)

    def _apply_default_fees(tx: Dict[str, Any], attempt_index: int) -> None:
        # If both legacy and EIP-1559 are absent, set EIP-1559 params
        if 'gasPrice' not in tx and 'maxFeePerGas' not in tx:
            try:
                base_fee = web3.eth.get_block('latest')['baseFeePerGas']
                max_priority_fee = web3.to_wei(2, 'gwei')
                tx['maxFeePerGas'] = base_fee * 2 + max_priority_fee
                tx['maxPriorityFeePerGas'] = max_priority_fee
                tx.pop('gasPrice', None)
            except Exception:
                tx['gasPrice'] = web3.eth.gas_price
        # On retries, bump whichever pricing scheme is present
        if attempt_index > 0:
            if 'maxFeePerGas' in tx and 'maxPriorityFeePerGas' in tx:
                tx['maxPriorityFeePerGas'] = int(tx['maxPriorityFeePerGas'] * fee_bump_factor)
                tx['maxFeePerGas'] = int(tx['maxFeePerGas'] * fee_bump_factor)
            elif 'gasPrice' in tx:
                tx['gasPrice'] = int(tx['gasPrice'] * fee_bump_factor)

    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            # Always take latest pending nonce
            current_nonce = web3.eth.get_transaction_count(account.address, 'pending')
            # Build transaction skeleton
            transaction: Dict[str, Any] = function_call.build_transaction({
                'from': account.address,
                'nonce': current_nonce,
                'gas': tx_params.get('gas', None),
                'gasPrice': tx_params.get('gasPrice', None),
                'maxFeePerGas': tx_params.get('maxFeePerGas', None),
                'maxPriorityFeePerGas': tx_params.get('maxPriorityFeePerGas', None),
                'value': tx_params.get('value', 0),
            })

            # Remove None values
            transaction = {k: v for k, v in transaction.items() if v is not None}

            # Ensure gas
            if 'gas' not in transaction:
                transaction['gas'] = estimate_gas_with_buffer(web3, transaction)

            # Ensure fees and bump on retries
            _apply_default_fees(transaction, attempt)

            # Sign
            signed_txn = web3.eth.account.sign_transaction(transaction, private_key)

            # Broadcast
            tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

            # Wait for receipt
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt['status'] != 1:
                raise Exception(f"Transaction failed: {tx_hash.hex()}")
            return tx_hash.hex(), receipt

        except Exception as exc:  # noqa: BLE001
            last_error = exc

            # Extract provider error message if present
            message: str = ""
            try:
                details = getattr(exc, 'args', [None])[0]
                if isinstance(details, dict):
                    message = str(details.get('message', '')).lower()
                else:
                    message = str(exc).lower()
            except Exception:
                message = str(exc).lower()

            # If tx is already known, wait for its hash
            if 'already known' in message:
                try:
                    # Compute hash and wait
                    raw = signed_txn.raw_transaction  # type: ignore[name-defined]
                    computed_hash = Web3.keccak(raw).hex()
                    receipt = web3.eth.wait_for_transaction_receipt(computed_hash)
                    if receipt['status'] != 1:
                        raise Exception(f"Transaction failed: {computed_hash}")
                    return computed_hash, receipt
                except Exception as wait_exc:  # noqa: BLE001
                    last_error = wait_exc

            # Retryable nonce/price conditions
            retryable = (
                'nonce too low' in message
                or 'replacement transaction underpriced' in message
                or 'transaction underpriced' in message
            )
            if attempt < retries and retryable:
                time.sleep(retry_sleep_seconds)
                continue

            # Non-retryable or retries exhausted
            break

    # If we exit loop without returning
    raise last_error if last_error else Exception('Unknown transaction error')