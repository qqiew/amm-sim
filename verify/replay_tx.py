"""Replay every Raydium CPMM swap inside a Solana transaction through the AMM math.

Works on multi-hop / routed transactions too: instead of guessing which token
accounts are the pool's vaults, it reads the SwapEvent that the CPMM program
logs for each swap. That event contains the pool's reserves right before the
swap (already net of accrued protocol/fund/creator fees), the input amount and
the actual output.

Usage (from the amm-sim folder):
    python3 verify/replay_tx.py <signature>
"""
import base64
import hashlib
import json
import struct
import sys
import urllib.request

from amm.constant_product import get_amount_out_int

RPC = "https://api.mainnet-beta.solana.com"
CPMM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
FEE_DEN = 1_000_000  # Raydium CPMM fee denominator (curve/fees.rs)

# Anchor tags each event with the first 8 bytes of sha256("event:<Name>")
SWAP_EVENT_TAG = hashlib.sha256(b"event:SwapEvent").digest()[:8]


# ---------- small helpers ----------

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["result"]


B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + s


def u64(buf, off):
    return struct.unpack_from("<Q", buf, off)[0]


# ---------- decoding (layouts from raydium-cp-swap source) ----------

def decode_swap_event(data: bytes):
    """states/events.rs -> SwapEvent, after the 8-byte tag."""
    o = 8
    ev = {"pool_id": b58(data[o:o + 32])}; o += 32
    for name in ("input_vault_before", "output_vault_before", "input_amount",
                 "output_amount", "input_transfer_fee", "output_transfer_fee"):
        ev[name] = u64(data, o); o += 8
    ev["base_input"] = bool(data[o]); o += 1
    ev["input_mint"] = b58(data[o:o + 32]); o += 32
    ev["output_mint"] = b58(data[o:o + 32]); o += 32
    if len(data) >= o + 17:  # newer program versions add fee fields
        ev["trade_fee"] = u64(data, o); o += 8
        ev["creator_fee"] = u64(data, o); o += 8
        ev["creator_fee_on_input"] = bool(data[o])
    return ev


def decode_amm_config(data: bytes):
    """states/config.rs -> AmmConfig: 8 tag, bump u8, disable bool, index u16, then u64 rates."""
    return {
        "trade_fee_rate": u64(data, 12),
        "protocol_fee_rate": u64(data, 20),
        "fund_fee_rate": u64(data, 28),
        "creator_fee_rate": u64(data, 108),  # after create_pool_fee + two 32-byte owners
    }


def swap_events(tx):
    evs = []
    for line in tx["meta"].get("logMessages") or []:
        if line.startswith("Program data: "):
            data = base64.b64decode(line[len("Program data: "):])
            if data[:8] == SWAP_EVENT_TAG:
                evs.append(decode_swap_event(data))
    return evs


def cpmm_configs(tx):
    """amm_config is account #2 of every CPMM swap instruction (payer, authority, amm_config, ...)."""
    ixs = list(tx["transaction"]["message"]["instructions"])
    for inner in tx["meta"].get("innerInstructions") or []:
        ixs += inner["instructions"]
    return [ix["accounts"][2] for ix in ixs if ix.get("programId") == CPMM and len(ix.get("accounts", [])) >= 13]


def fetch_account(pubkey):
    info = rpc("getAccountInfo", [pubkey, {"encoding": "base64"}])
    return base64.b64decode(info["value"]["data"][0])


# ---------- the actual check ----------

def predict(ev, cfg):
    x, y = ev["input_vault_before"], ev["output_vault_before"]
    dx = ev["input_amount"]
    trade = cfg["trade_fee_rate"]
    creator = cfg["creator_fee_rate"] if ev.get("creator_fee", 0) > 0 else 0

    if creator and ev.get("creator_fee_on_input"):
        # creator fee is charged together with the trade fee, on the input
        return get_amount_out_int(x, y, dx, trade + creator, FEE_DEN)

    out = get_amount_out_int(x, y, dx, trade, FEE_DEN)
    if creator:
        # creator fee charged on the output, rounded up (fees.rs: creator_fee uses ceil_div)
        out -= -(-out * creator // FEE_DEN)
    return out


def main():
    sig = sys.argv[1]
    tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                                      "maxSupportedTransactionVersion": 1}])
    if tx is None:
        sys.exit("Transaction not found (public RPC may have pruned it; try a newer one).")
    if tx["meta"]["err"]:
        sys.exit(f"Transaction failed on-chain: {tx['meta']['err']}")

    events = swap_events(tx)
    configs = cpmm_configs(tx)
    if not events:
        sys.exit("No Raydium CPMM SwapEvent found in this transaction's logs.")
    if len(configs) != len(events):
        print(f"note: {len(events)} swap events but {len(configs)} CPMM swap instructions; pairing in order")

    for i, ev in enumerate(events):
        print(f"\n=== CPMM swap #{i + 1}  pool {ev['pool_id']}")
        print(f"  {ev['input_mint'][:6]}… -> {ev['output_mint'][:6]}…")
        if not ev["base_input"]:
            print("  swap_base_output (exact-out) — our get_amount_out model doesn't apply, skipping")
            continue

        cfg = decode_amm_config(fetch_account(configs[min(i, len(configs) - 1)]))
        print(f"  fee rates: trade {cfg['trade_fee_rate']}/{FEE_DEN}, creator {cfg['creator_fee_rate']}/{FEE_DEN}"
              f" (creator fee {'ON' if ev.get('creator_fee', 0) else 'off'} for this pool)")
        print(f"  reserves before (net of fees)  x={ev['input_vault_before']:,}  y={ev['output_vault_before']:,}")
        print(f"  dx (after token transfer fee)  {ev['input_amount']:,}")
        if "trade_fee" in ev:
            print(f"  trade fee charged on-chain     {ev['trade_fee']:,}")

        predicted = predict(ev, cfg)
        actual = ev["output_amount"]
        print(f"  actual dy                      {actual:,}")
        print(f"  predicted dy                   {predicted:,}")
        diff = predicted - actual
        print(f"  difference                     {diff:+,}")
        print("  EXACT MATCH" if diff == 0 else "  MISMATCH — figure out why before changing anything")


if __name__ == "__main__":
    main()
