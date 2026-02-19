# Error Log for CGAE Filecoin Integration

This document tracks significant errors encountered during the setup and testing of the Filecoin integration (Synapse SDK) for the CGAE framework, along with their root causes and resolutions.

---

## 1. `.env` File Not Found

*   **Error Message:** `bash: line 1: ddft_framework/.env: No such file or directory`
*   **Cause:** Initial assumption that the `.env` file was located within the `ddft_framework/` subdirectory. The `.env` file was actually in the project's root directory.
*   **Fix:** Corrected script paths to reference the `.env` file at the project root.

---

## 2. `SyntaxError: Invalid or unexpected token` (Repeated)

*   **Error Message:** `SyntaxError: Invalid or unexpected token` pointing to `console.log("...` in multiple Node.js scripts.
*   **Cause:** A persistent issue with how the `write_file` tool was handling JavaScript string literals, likely due to unintended special characters or newlines.
*   **Fix:** Rewrote affected `console.log` statements to use only simple, single-quoted, single-line strings to ensure correct JavaScript syntax.

---

## 3. `Error: Cannot find module 'dotenv'`

*   **Error Message:** `Error: Cannot find module 'dotenv'` when attempting to run Node.js scripts, despite `npm install` completing successfully.
*   **Cause:** An unresolved Node.js module resolution issue within the `run_shell_command` execution environment.
*   **Fix:** Bypassed the problematic Node.js module system by using shell commands (`grep`, `cut`) to extract the private key directly from the `.env` file and passing it as a command-line argument to scripts.

---

## 4. `Unsupported chain: 314159`

*   **Error Message:** `An error occurred: Unsupported chain: 314159 ... Import chains from @filoz/synapse-core/chains to get the correct chain.`
*   **Cause:** The Synapse SDK requires its own specific chain definition object for initialization, not a generic one from `viem/chains`.
*   **Fix:** Modified scripts to import the `calibration` chain object directly from `@filoz/synapse-core/chains`.

---

## 5. `InsufficientLockupFunds` / `Insufficient USDFC: have 0`

*   **Error Message (Initial):** `InsufficientLockupFunds(..., available: 0)`
*   **Error Message (Final):** `PaymentsService deposit failed: Insufficient USDFC: have 0`
*   **Investigation Path:**
    1.  Hypothesized a lack of `tFIL`. Disproven by balance check (~99 tFIL).
    2.  Hypothesized a lack of `tUSDFC`. Confirmed user had 10 `tUSDFC` on contract `0xb304...cDf0`.
    3.  Hypothesized a missing ERC-20 `approve`. Performed approval, but error persisted.
    4.  Hypothesized funds needed to be `deposit`ed into a service account. Implemented deposit script.
*   **Root Cause:** The `PaymentsService.deposit` function revealed the true issue. The Synapse SDK is hardcoded or defaulted to check for a `tUSDFC` balance at a **different contract address** than the one where the user's funds are located. The SDK was checking its default address, finding a balance of `0`, and throwing the error.
*   **Solution:**
    1.  **Identify the correct token address:** The SDK is likely using the other known `tUSDFC` address for Calibration: `0x80B98d3aa09ffff255c3ba4A241111Ff1262F045`.
    2.  **Acquire funds:** The user must acquire `tUSDFC` at this specific contract address.
    3.  **Update and run script:** The `TUSDFC_ADDRESS` constant in `storage/deposit_to_synapse.mjs` must be updated to this new address, and the script run again to perform the deposit. This will fund the Synapse service account, resolving the error.
