# amm-sim
 
A small Python simulator for **constant-product AMMs** (`x · y = k`), the pool model used by decentralized exchanges like Raydium and Uniswap v2.
 
Built as a learning project to understand how on-chain swaps are priced, from the core math down to integer rounding.
 
## What it does
 
- **`get_amount_out`** — how much you receive for a given input
- **`get_amount_in`** — how much you must put in to receive an exact amount
- **Integer versions** (`*_int`) that work in token base units (e.g. lamports) with fees as integer ratios, rounding in the pool's favor like real on-chain programs
- **Price impact plot** comparing a shallow and a deep pool

## Properties tested
 
- Output is always positive and smaller than the reserve — a pool can't be drained
- `k` never decreases after a swap (fees make it grow)
- `get_amount_in` undoes `get_amount_out` (round trip)
- Integer results never pay out more than the exact math allows
- Taking the whole reserve raises an error

## Verified against mainnet

`verify/replay_tx.py` checks the integer math against real Raydium CPMM swaps on Solana. Given a transaction signature, it fetches the transaction over RPC, decodes the `SwapEvent` the CPMM program logs for each swap (the pool's reserves just before the swap, net of accrued fees, plus the input and actual output), reads the pool's fee rates from its on-chain config account, and compares the actual output with what `get_amount_out_int` predicts. It also works on multi-hop routed transactions, because it reads each swap's event instead of guessing which token accounts are the pool vaults.

```bash
python3 verify/replay_tx.py <transaction-signature>
```

First result: a swap inside a bot's multi-hop route, in a pool with a 0.25% trade fee and a 1% creator fee, matched the on-chain output exactly (486,304,901 predicted vs. 486,304,901 actual).