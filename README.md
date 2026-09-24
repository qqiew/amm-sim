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