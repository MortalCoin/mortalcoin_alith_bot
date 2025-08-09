"""
Web3 connection utilities.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from web3 import Web3
from web3.contract import Contract
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # geth_poa_middleware was deprecated in newer web3 versions
    geth_poa_middleware = None

# Import our converted ABIs
from uniswap_v2_abi import UNISWAP_V2_PAIR_ABI, ERC20_ABI


logger = logging.getLogger(__name__)


def get_web3_connection(rpc_url: str) -> Web3:
    """Create Web3 connection."""
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    
    # Add POA middleware if needed (for some networks like BSC)
    if geth_poa_middleware is not None:
        try:
            web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception:
            pass
        
    if not web3.is_connected():
        raise ConnectionError(f"Failed to connect to {rpc_url}")
        
    logger.info(f"Connected to blockchain at {rpc_url}")
    return web3


def get_contract(web3: Web3, contract_address: str, abi_path: Optional[str] = None) -> Contract:
    """Get contract instance using ABI from file."""
    if not abi_path:
        # Default ABI path relative to this file
        abi_path = Path(__file__).parent.parent / "contract_abi.json"
    
    with open(abi_path, "r") as f:
        abi = json.load(f)
        
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=abi
    )
    
    logger.info(f"Loaded contract at {contract_address}")
    return contract


def get_uniswap_pair_contract(web3: Web3, pair_address: str) -> Contract:
    """Get Uniswap V2 pair contract instance."""
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(pair_address),
        abi=UNISWAP_V2_PAIR_ABI
    )
    
    logger.info(f"Loaded Uniswap V2 pair contract at {pair_address}")
    return contract


def get_erc20_contract(web3: Web3, token_address: str) -> Contract:
    """Get ERC20 token contract instance."""
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=ERC20_ABI
    )
    
    logger.info(f"Loaded ERC20 contract at {token_address}")
    return contract