#!/usr/bin/env node
/**
 * CGAE Filecoin Storage — Synapse SDK Uploader
 * =============================================
 * Uploads a JSON audit certificate to Filecoin via the Synapse Warm Storage
 * Service and prints the resulting PieceCID to stdout.
 *
 * Usage:
 *   node upload_to_synapse.mjs <file_path> [--network calibration|mainnet]
 *
 * Required env vars:
 *   FILECOIN_PRIVATE_KEY   — hex private key (no 0x prefix) of the funding wallet
 *
 * Optional env vars:
 *   FILECOIN_NETWORK       — "calibration" (default) or "mainnet"
 *   FILECOIN_RPC           — override RPC endpoint
 *
 * Output (stdout, JSON):
 *   { "cid": "bafk...", "size": 1234, "network": "calibration", "ok": true }
 *
 * On error (stderr + exit 1):
 *   { "error": "...", "ok": false }
 *
 * Install deps (from storage/):
 *   npm install @filoz/synapse-sdk ethers
 */

import { readFileSync, statSync } from "fs";
import { resolve } from "path";
import { createRequire } from "module";

const require = createRequire(import.meta.url);

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === "--help") {
  console.error("Usage: node upload_to_synapse.mjs <file_path> [--network calibration|mainnet]");
  process.exit(1);
}

const filePath = resolve(args[0]);
const networkArg = args.includes("--network") ? args[args.indexOf("--network") + 1] : null;
const network = networkArg || process.env.FILECOIN_NETWORK || "calibration";

// ---------------------------------------------------------------------------
// Environment
// ---------------------------------------------------------------------------

const privateKey = process.env.FILECOIN_PRIVATE_KEY;
if (!privateKey) {
  writeError("FILECOIN_PRIVATE_KEY environment variable not set");
  process.exit(1);
}

// Calibnet constants
const CHAIN_CONFIGS = {
  calibration: {
    chainId: 314159,
    rpc: process.env.FILECOIN_RPC || "https://api.calibration.node.glif.io/rpc/v1",
    name: "Filecoin Calibration testnet",
  },
  mainnet: {
    chainId: 314,
    rpc: process.env.FILECOIN_RPC || "https://api.node.glif.io/rpc/v1",
    name: "Filecoin Mainnet",
  },
};

const chainConfig = CHAIN_CONFIGS[network];
if (!chainConfig) {
  writeError(`Unknown network: ${network}. Use 'calibration' or 'mainnet'`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Main upload
// ---------------------------------------------------------------------------

async function main() {
  // Read the file
  let fileBytes;
  let fileSize;
  try {
    fileBytes = readFileSync(filePath);
    fileSize = statSync(filePath).size;
  } catch (e) {
    writeError(`Cannot read file: ${filePath} — ${e.message}`);
    process.exit(1);
  }

  // Dynamically import Synapse SDK (ESM-compatible)
  let Synapse, ethers;
  try {
    const synapseModule = await import("@filoz/synapse-sdk");
    Synapse = synapseModule.Synapse;
    const ethersModule = await import("ethers");
    ethers = ethersModule;
  } catch (e) {
    writeError(
      `Cannot load @filoz/synapse-sdk or ethers. ` +
      `Run: npm install @filoz/synapse-sdk ethers  (in storage/ directory)\n${e.message}`
    );
    process.exit(2);  // Exit code 2 = SDK not installed (Python wrapper treats as soft fail)
  }

  // Create wallet from private key
  const provider = new ethers.JsonRpcProvider(chainConfig.rpc, {
    chainId: chainConfig.chainId,
    name: chainConfig.name,
  });
  const wallet = new ethers.Wallet(`0x${privateKey}`, provider);

  // Initialise Synapse SDK
  let synapse;
  try {
    synapse = await Synapse.create({
      privateKey: `0x${privateKey}`,
      rpcURL: chainConfig.rpc,
      withCDN: false,         // no CDN markup on testnet
    });
  } catch (e) {
    writeError(`Failed to initialise Synapse SDK: ${e.message}`);
    process.exit(1);
  }

  // Create storage service handle
  let storageService;
  try {
    storageService = await synapse.createStorage({
      storageCapacity: 1,              // 1 GB minimum allocation
      persistencePeriod: 30,           // 30 days
    });
  } catch (e) {
    writeError(`Failed to create storage service: ${e.message}. ` +
               `Ensure the wallet has sufficient USDFC on ${network}.`);
    process.exit(1);
  }

  // Upload the file bytes
  let uploadResult;
  try {
    // The Synapse SDK upload method accepts a Uint8Array or Buffer
    uploadResult = await storageService.upload(fileBytes);
  } catch (e) {
    writeError(`Upload failed: ${e.message}`);
    process.exit(1);
  }

  // uploadResult contains { pieceCID, commp, paddedPieceSize, ... }
  const cid = uploadResult.pieceCID || uploadResult.cid || uploadResult.commp;
  if (!cid) {
    writeError(`Upload succeeded but no CID returned. Result: ${JSON.stringify(uploadResult)}`);
    process.exit(1);
  }

  // Success
  const output = {
    ok: true,
    cid: cid.toString(),
    size: fileSize,
    network,
    file: filePath,
    txHash: uploadResult.txHash || null,
  };
  process.stdout.write(JSON.stringify(output) + "\n");
}

function writeError(msg) {
  process.stderr.write(JSON.stringify({ ok: false, error: msg }) + "\n");
}

main().catch((e) => {
  writeError(`Unexpected error: ${e.message}\n${e.stack}`);
  process.exit(1);
});
