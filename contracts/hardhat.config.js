require("@nomicfoundation/hardhat-toolbox");

/**
 * Hardhat configuration for CGAE smart contracts.
 *
 * Targets:
 *   calibnet  — Filecoin Calibration Testnet (chain 314159)
 *   localhost — Local Hardhat node for development
 *
 * Required env vars for Calibnet deployment:
 *   PRIVATE_KEY         — hex private key (no 0x prefix) of the deployer wallet
 *
 * Testnet resources:
 *   tFIL Faucet:   https://faucet.calibnet.chainsafe-fil.io/funds.html
 *   Explorer:      https://calibration.filscan.io
 *   RPC:           https://api.calibration.node.glif.io/rpc/v1
 *
 * Usage:
 *   cd contracts
 *   npm install
 *   export PRIVATE_KEY=<your_hex_key>
 *   npm run deploy:calibnet
 */

const PRIVATE_KEY = process.env.PRIVATE_KEY ||
  // Fallback zero key for compilation/testing only — never deploy with this
  "0000000000000000000000000000000000000000000000000000000000000001";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },

  networks: {
    // Filecoin Calibration Testnet
    calibnet: {
      url: process.env.CALIBNET_RPC_URL || "https://api.calibration.node.glif.io/rpc/v1",
      chainId: 314159,
      accounts: [`0x${PRIVATE_KEY}`],
      // Filecoin uses higher gas limits than Ethereum
      gas: 10_000_000,
      gasPrice: 1_000_000_000, // 1 Gwei — adjust if txs fail
      timeout: 120_000,        // 2 min timeout (Calibnet is slow)
    },

    // Local development
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
  },

  // Compilation output paths
  paths: {
    sources: ".",
    artifacts: "./artifacts",
    cache: "./cache",
  },
};
