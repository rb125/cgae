#!/usr/bin/env node
/**
 * anchor_certify.mjs
 * ------------------
 * Calls cgae_registry.certify() on Solana to anchor a Filecoin audit CID
 * in the agent's Certification PDA.
 *
 * Usage:
 *   SOLANA_PRIVATE_KEY=<base58_or_path> node anchor_certify.mjs <payload.json>
 *
 * payload.json fields:
 *   agent       - agent wallet pubkey (base58)
 *   cc, er, as_, ih - robustness scores as u16 (0-10000)
 *   audit_type  - string (max 32 chars)
 *   audit_cid   - Filecoin CID string (max 128 chars)
 *   rpc_url     - optional, defaults to devnet
 *
 * Outputs JSON: { ok: true, signature: "..." } or { ok: false, error: "..." }
 */

import { createRequire } from 'module';
import { readFileSync } from 'fs';
import { createHash } from 'crypto';

const require = createRequire(import.meta.url);
const NM = '../solana_contracts/node_modules';

const { Connection, PublicKey, Transaction, TransactionInstruction,
        Keypair, SystemProgram, sendAndConfirmTransaction }
  = require(`${NM}/@solana/web3.js`);
const borsh = require(`${NM}/@anchor-lang/borsh`);

// ── Program ID (matches declare_id! in cgae_registry/src/lib.rs) ─────────────
const REGISTRY_PROGRAM_ID = new PublicKey('DR59DsHsJGHTqHRG1SLcZStdzgw97mqVFxjWBozE4Fyp');

// ── Anchor instruction discriminator: sha256("global:certify")[0:8] ───────────
function discriminator(name) {
  return createHash('sha256').update(`global:${name}`).digest().slice(0, 8);
}
const CERTIFY_DISC = discriminator('certify');

// ── Borsh schema for certify instruction args ─────────────────────────────────
const CertifyArgs = borsh.struct([
  borsh.publicKey('agent'),
  borsh.u16('cc'),
  borsh.u16('er'),
  borsh.u16('as_'),
  borsh.u16('ih'),
  borsh.str('audit_type'),
  borsh.str('audit_cid'),
]);

// ── PDA helpers ───────────────────────────────────────────────────────────────
async function findPDA(seeds) {
  return PublicKey.findProgramAddressSync(seeds, REGISTRY_PROGRAM_ID);
}

// ── Keypair loader ────────────────────────────────────────────────────────────
function loadKeypair(keyEnv) {
  // If it looks like a file path, read it
  if (keyEnv.startsWith('/') || keyEnv.startsWith('~') || keyEnv.endsWith('.json')) {
    const path = keyEnv.replace(/^~/, process.env.HOME);
    const arr = JSON.parse(readFileSync(path, 'utf8'));
    return Keypair.fromSecretKey(Uint8Array.from(arr));
  }
  // Otherwise treat as base58
  const bs58 = require(`${NM}/@solana/web3.js`).default?.bs58 ?? require('bs58');
  return Keypair.fromSecretKey(bs58.decode(keyEnv));
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const payloadPath = process.argv[2];
  if (!payloadPath) throw new Error('Usage: anchor_certify.mjs <payload.json>');

  const payload = JSON.parse(readFileSync(payloadPath, 'utf8'));
  const { agent, cc, er, as_, ih, audit_type, audit_cid,
          rpc_url = 'https://api.devnet.solana.com' } = payload;

  const privateKeyEnv = process.env.SOLANA_PRIVATE_KEY;
  if (!privateKeyEnv) throw new Error('SOLANA_PRIVATE_KEY not set');

  const payer = loadKeypair(privateKeyEnv);
  const agentPubkey = new PublicKey(agent);
  const connection = new Connection(rpc_url, 'confirmed');

  // Derive PDAs
  const [configPDA]      = await findPDA([Buffer.from('config')]);
  const [auditorPDA]     = await findPDA([Buffer.from('auditor'), payer.publicKey.toBuffer()]);
  const [agentRecordPDA] = await findPDA([Buffer.from('agent'),   agentPubkey.toBuffer()]);
  const [certPDA]        = await findPDA([Buffer.from('cert'),    agentPubkey.toBuffer()]);

  // Encode instruction data: discriminator + borsh args
  const argsBuf = Buffer.alloc(1024);
  const argsLen = CertifyArgs.encode(
    { agent: agentPubkey, cc, er, as_, ih, audit_type, audit_cid },
    argsBuf
  );
  const data = Buffer.concat([CERTIFY_DISC, argsBuf.slice(0, argsLen)]);

  const ix = new TransactionInstruction({
    programId: REGISTRY_PROGRAM_ID,
    keys: [
      { pubkey: configPDA,      isSigner: false, isWritable: false },
      { pubkey: auditorPDA,     isSigner: false, isWritable: false },
      { pubkey: agentRecordPDA, isSigner: false, isWritable: true  },
      { pubkey: certPDA,        isSigner: false, isWritable: true  },
      { pubkey: payer.publicKey,isSigner: true,  isWritable: true  },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data,
  });

  const tx = new Transaction().add(ix);
  const sig = await sendAndConfirmTransaction(connection, tx, [payer]);
  console.log(JSON.stringify({ ok: true, signature: sig }));
}

main().catch(e => {
  console.log(JSON.stringify({ ok: false, error: e.message }));
  process.exit(1);
});
