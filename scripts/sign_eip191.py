#!/usr/bin/env python3
"""
Sign a message using EIP-191 (personal_sign) with a given private key.

Usage:
  python scripts/sign_eip191.py -k <hex_private_key> -m "Login MortalCoin headless"

Environment variables:
  PRIVATE_KEY  Optional. If set and -k is omitted, will be used as the key.

Optional:
  -a / --address  Expected address to compare against recovered address
  --json          Output machine-readable JSON only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3


def _ensure_0x_prefixed(value: str) -> str:
    return value if value.startswith("0x") else f"0x{value}"


def sign_message(private_key: str, message: str) -> dict[str, Any]:
    private_key = _ensure_0x_prefixed(private_key)
    account = Account.from_key(private_key)
    eth_message = encode_defunct(text=message)
    signed = Account.sign_message(eth_message, private_key=private_key)
    signature = _ensure_0x_prefixed(signed.signature.hex())

    try:
        recovered = Account.recover_message(eth_message, signature=signature)
        recovered_checksum = Web3.to_checksum_address(recovered)
    except Exception:
        recovered_checksum = None

    return {
        "address": Web3.to_checksum_address(account.address),
        "message": message,
        "signature": signature,
        "recovered_address": recovered_checksum,
        "matches": recovered_checksum == Web3.to_checksum_address(account.address)
        if recovered_checksum
        else False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign message via EIP-191 (personal_sign)")
    parser.add_argument("-k", "--private-key", dest="private_key", help="Hex private key (0x...) or via env PRIVATE_KEY")
    parser.add_argument(
        "-m",
        "--message",
        dest="message",
        default="Login MortalCoin headless",
        help="Message to sign",
    )
    parser.add_argument(
        "-a",
        "--address",
        dest="expected_address",
        default=None,
        help="Expected address (to compare with recovered)",
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON only")

    args = parser.parse_args()

    private_key = args.private_key or os.getenv("PRIVATE_KEY")
    if not private_key:
        print("Error: private key must be provided via -k/--private-key or PRIVATE_KEY env", file=sys.stderr)
        return 2

    result = sign_message(private_key, args.message)

    if args.expected_address:
        try:
            result["expected_address"] = Web3.to_checksum_address(args.expected_address)
            result["expected_matches"] = (
                result["recovered_address"] == result["expected_address"]
                if result["recovered_address"]
                else False
            )
        except Exception:
            result["expected_address"] = args.expected_address
            result["expected_matches"] = False

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("Address:            ", result["address"]) 
        print("Message:            ", result["message"]) 
        print("Signature:          ", result["signature"]) 
        print("Recovered address:  ", result["recovered_address"]) 
        print("Matches self:       ", result["matches"]) 
        if "expected_address" in result:
            print("Expected address:   ", result["expected_address"]) 
            print("Matches expected:   ", result["expected_matches"]) 

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


