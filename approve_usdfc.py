import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv() # Load .env file from project root

# --- Configuration ---
# Your private key (ensure it's in your .env file)
PRIVATE_KEY = os.getenv("FILECOIN_PRIVATE_KEY")
if not PRIVATE_KEY:
    raise ValueError("FILECOIN_PRIVATE_KEY not found in .env file.")

# RPC URL for Filecoin Calibration
RPC_URL = "https://api.calibration.node.glif.io/rpc/v1"

# tUSDFC token contract address (from our investigation)
TUSDFC_CONTRACT_ADDRESS = "0xb3042734b608a1B16e9e86B374A3f3e389B4cDf0"

# Synapse StorageContext contract address (the spender)
SYNAPSE_SPENDER_ADDRESS = "0x02925630df557F957f70E112bA06e50965417CA0"

# --- ERC-20 ABI Snippet for approve function, decimals, and balanceOf ---
ERC20_ABI = [
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}
]

def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("Failed to connect to Filecoin Calibration RPC.")
        return

    account = w3.eth.account.from_key(PRIVATE_KEY)
    sender_address = account.address
    print(f"Connected to RPC. Sender address: {sender_address}")

    # Get tUSDFC contract instance
    tUSDFC_contract = w3.eth.contract(address=TUSDFC_CONTRACT_ADDRESS, abi=ERC20_ABI)

    # Fetch decimals for accurate approval amount
    try:
        decimals = tUSDFC_contract.functions.decimals().call()
        print(f"tUSDFC decimals: {decimals}")
    except Exception as e:
        print(f"Could not fetch tUSDFC decimals. Defaulting to 6. Error: {e}")
        decimals = 6 # Default to 6 decimals if call fails

    # Get current tUSDFC balance
    current_balance_raw = tUSDFC_contract.functions.balanceOf(sender_address).call()
    current_balance_formatted = current_balance_raw / (10 ** decimals)
    print(f"Current tUSDFC balance: {current_balance_formatted}")

    # We will approve 10 tUSDFC
    AMOUNT_TO_APPROVE_RAW = 10 * (10 ** decimals)
    if current_balance_raw < AMOUNT_TO_APPROVE_RAW:
        print(f"Warning: Current balance is less than 10. Approving the full balance of {current_balance_formatted} tUSDFC.")
        AMOUNT_TO_APPROVE_RAW = current_balance_raw
    else:
        print(f"Approving 10 tUSDFC (raw: {AMOUNT_TO_APPROVE_RAW}) for Synapse.")

    # Build the approval transaction
    nonce = w3.eth.get_transaction_count(sender_address)
    gas_price = w3.eth.gas_price

    try:
        gas_estimate = tUSDFC_contract.functions.approve(
            SYNAPSE_SPENDER_ADDRESS,
            AMOUNT_TO_APPROVE_RAW
        ).estimate_gas({'from': sender_address})
        print(f"Gas estimate for approval: {gas_estimate}")
    except Exception as e:
        print(f"Could not estimate gas. Error: {e}. Using a default gas limit of 500,000.")
        gas_estimate = 500_000

    tx = tUSDFC_contract.functions.approve(
        SYNAPSE_SPENDER_ADDRESS,
        AMOUNT_TO_APPROVE_RAW
    ).build_transaction({
        'chainId': w3.eth.chain_id,
        'gas': gas_estimate,
        'gasPrice': gas_price,
        'nonce': nonce,
        'from': sender_address,
    })

    # Sign and send the transaction
    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Approval transaction sent! Tx Hash: {tx_hash.hex()}")

    # Wait for confirmation
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Transaction mined in block {tx_receipt.blockNumber}. Status: {'Success' if tx_receipt.status == 1 else 'Failed'}")

    if tx_receipt.status == 1:
        print(f"Successfully approved {AMOUNT_TO_APPROVE_RAW / (10**decimals)} tUSDFC for Synapse Spender address {SYNAPSE_SPENDER_ADDRESS}")
    else:
        print("Approval transaction failed. Please check the transaction on a block explorer.")

if __name__ == "__main__":
    main()
