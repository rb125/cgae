import { Synapse } from '@filoz/synapse-sdk';
import { createWalletClient, http, publicActions } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { calibration } from '@filoz/synapse-core/chains';
import { parseUnits } from 'viem';

// --- Configuration ---
const TUSDFC_ADDRESS = "0xb3042734b608a1B16e9e86B374A3f3e389B4cDf0";
const AMOUNT_TO_DEPOSIT = "10"; // Amount of tUSDFC to deposit
const LOCKUP_ALLOWANCE = "10"; // Amount of tUSDFC for lockup allowance
const MAX_LOCKUP_PERIOD_SECONDS = 31536000; // 1 year in seconds

const ERC20_ABI = [
  {"constant": true, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
  {"constant": true, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
];

async function main() {
    const privateKey = process.env.FILECOIN_PRIVATE_KEY;
    if (!privateKey) {
        console.error('FILECOIN_PRIVATE_KEY environment variable not set.');
        process.exit(1);
    }

    const account = privateKeyToAccount(`0x${privateKey}`);
    const client = createWalletClient({ account, chain: calibration, transport: http() }).extend(publicActions);

    console.log('Using wallet address: ' + account.address);
    console.log('This script will use Synapse.payments.depositWithPermitAndApproveOperator to fund your service account.');

    // --- Get Decimals for tUSDFC ---
    const decimals = await client.readContract({ address: TUSDFC_ADDRESS, abi: ERC20_ABI, functionName: 'decimals' });
    const symbol = await client.readContract({ address: TUSDFC_ADDRESS, abi: ERC20_ABI, functionName: 'symbol' });
    
    console.log('Detected token: ' + symbol + ' with ' + decimals + ' decimals.');

    const amountRaw = parseUnits(AMOUNT_TO_DEPOSIT, decimals);
    const lockupAllowanceRaw = parseUnits(LOCKUP_ALLOWANCE, decimals);

    console.log('Attempting to deposit ' + AMOUNT_TO_DEPOSIT + ' ' + symbol + ' with lockup allowance of ' + LOCKUP_ALLOWANCE + ' ' + symbol + '...');

    const synapse = Synapse.create({ account, transport: http(), chain: calibration });

    const depositResult = await synapse.payments.depositWithPermitAndApproveOperator({
        amount: amountRaw,
        tokenAddress: TUSDFC_ADDRESS,
        lockupAllowance: lockupAllowanceRaw,
        maxLockupPeriod: MAX_LOCKUP_PERIOD_SECONDS,
    });
    
    // The depositWithPermitAndApproveOperator function directly returns the transaction hash.
    const txHash = depositResult; 

    if (!txHash) {
        console.error('Error: The depositWithPermitAndApproveOperator function did not return a valid transaction hash.');
        process.exit(1);
    }

    console.log('Deposit transaction sent. Waiting for confirmation... (Tx: ' + txHash + ')');
    await client.waitForTransactionReceipt({ hash: txHash });
    console.log('Deposit confirmed!');
    console.log('Your Synapse service account should now be funded and approved.');
    console.log('You can now re-run the simulation.');
}

main().catch(err => {
    console.error('An error occurred: ' + err.message);
    process.exit(1);
});
