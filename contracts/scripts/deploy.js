/**
 * CGAE Deployment Script — Filecoin Calibration Testnet
 * ======================================================
 * Deploys CGAERegistry and CGAEEscrow to Calibnet and writes
 * the resulting contract addresses to deployed.json.
 *
 * Usage:
 *   cd contracts
 *   npm install
 *   export PRIVATE_KEY=<hex_private_key_no_0x>
 *   npm run deploy:calibnet
 *
 * The deployed.json file is read by the Python engine at runtime to
 * call on-chain certify() after each live audit.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();
  const chainId = Number(network.chainId);

  console.log("=".repeat(60));
  console.log("CGAE Contract Deployment");
  console.log("=".repeat(60));
  console.log(`Network:  ${network.name} (chain ${chainId})`);
  console.log(`Deployer: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Balance:  ${ethers.formatEther(balance)} FIL\n`);

  if (balance === 0n) {
    console.error("ERROR: Deployer wallet has 0 FIL.");
    console.error(`Get testnet FIL from: https://faucet.calibnet.chainsafe-fil.io/funds.html`);
    process.exit(1);
  }

  // -----------------------------------------------------------------------
  // Deploy CGAERegistry
  // -----------------------------------------------------------------------
  console.log("Deploying CGAERegistry...");
  const RegistryFactory = await ethers.getContractFactory("CGAERegistry");
  const registry = await RegistryFactory.deploy();
  await registry.waitForDeployment();
  const registryAddress = await registry.getAddress();
  console.log(`  CGAERegistry deployed to: ${registryAddress}`);

  // -----------------------------------------------------------------------
  // Deploy CGAEEscrow (depends on CGAERegistry address)
  // -----------------------------------------------------------------------
  console.log("Deploying CGAEEscrow...");
  const EscrowFactory = await ethers.getContractFactory("CGAEEscrow");
  const escrow = await EscrowFactory.deploy(registryAddress);
  await escrow.waitForDeployment();
  const escrowAddress = await escrow.getAddress();
  console.log(`  CGAEEscrow deployed to:   ${escrowAddress}`);

  // -----------------------------------------------------------------------
  // Authorize escrow as a registry auditor
  // -----------------------------------------------------------------------
  console.log("Authorizing CGAEEscrow as auditor in CGAERegistry...");
  const authTx = await registry.authorizeAuditor(escrowAddress);
  await authTx.wait();
  console.log(`  Authorized (tx: ${authTx.hash})`);

  // -----------------------------------------------------------------------
  // Write deployment manifest
  // -----------------------------------------------------------------------
  const timestamp = new Date().toISOString();
  const deployedPath = path.join(__dirname, "..", "deployed.json");

  const manifest = {
    network: network.name,
    chainId,
    deployedAt: timestamp,
    deployer: deployer.address,
    contracts: {
      CGAERegistry: {
        address: registryAddress,
        deployTx: registry.deploymentTransaction()?.hash || null,
      },
      CGAEEscrow: {
        address: escrowAddress,
        deployTx: escrow.deploymentTransaction()?.hash || null,
      },
    },
    rpc: process.env.CALIBNET_RPC_URL || "https://api.calibration.node.glif.io/rpc/v1",
    explorer: chainId === 314159
      ? "https://calibration.filscan.io"
      : "http://localhost",
  };

  fs.writeFileSync(deployedPath, JSON.stringify(manifest, null, 2));
  console.log(`\nDeployment manifest written to: deployed.json`);

  // -----------------------------------------------------------------------
  // Summary
  // -----------------------------------------------------------------------
  console.log("\n" + "=".repeat(60));
  console.log("Deployment complete!");
  console.log("=".repeat(60));
  console.log(`CGAERegistry : ${manifest.explorer}/address/${registryAddress}`);
  console.log(`CGAEEscrow   : ${manifest.explorer}/address/${escrowAddress}`);
  console.log("\nNext steps:");
  console.log("  1. Add the deployed addresses to your .env:");
  console.log(`     CGAE_REGISTRY_ADDRESS=${registryAddress}`);
  console.log(`     CGAE_ESCROW_ADDRESS=${escrowAddress}`);
  console.log("  2. Run the live simulation — it will write certifications on-chain:");
  console.log("     python -m simulation.live_runner");
  console.log("=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("Deployment failed:", err);
    process.exit(1);
  });
