import math
import pytest

from amm.constant_product import get_amount_in, get_amount_out, get_amount_in_int, get_amount_out_int

# (x, y, dx, f) cases reused by several tests: small/deep pools, with/without fee
CASES = [
    (10, 1000, 1, 0.0025),
    (10, 1000, 10, 0),
    (1000, 150_000, 10, 0.0025),
    (1000, 150_000, 500, 0.01),
    (1, 1, 0.001, 0.003),
]


def test_fruit_stand_no_fee():
    # 10 apples in, pool doubles its apples -> half the bananas leave
    assert get_amount_out(10, 1000, 10, 0) == 500


def test_fee_reduces_output():
    no_fee = get_amount_out(10, 1000, 1, 0)
    with_fee = get_amount_out(10, 1000, 1, 0.0025)
    assert with_fee < no_fee


@pytest.mark.parametrize("x, y, dx, f", CASES)
def test_round_trip(x, y, dx, f):
    # amount_in should undo amount_out
    dy = get_amount_out(x, y, dx, f)
    assert math.isclose(get_amount_in(x, y, dy, f), dx)


@pytest.mark.parametrize("x, y, dx, f", CASES)
def test_k_never_decreases(x, y, dx, f):
    # the pool keeps the FULL dx, so k grows by the fee (or stays equal with f=0)
    dy = get_amount_out(x, y, dx, f)
    k_before = x * y
    k_after = (x + dx) * (y - dy)
    assert k_after >= k_before or math.isclose(k_after, k_before)


@pytest.mark.parametrize("x, y, dx, f", CASES)
def test_output_is_positive_and_below_reserve(x, y, dx, f):
    dy = get_amount_out(x, y, dx, f)
    assert 0 < dy < y


def test_huge_trade_cannot_drain_pool():
    dy = get_amount_out(10, 1000, 1_000_000_000, 0)
    assert dy < 1000


@pytest.mark.parametrize("dy", [1000, 1500])
def test_cannot_take_whole_reserve_or_more(dy):
    with pytest.raises(ValueError):
        get_amount_in(10, 1000, dy, 0.0025)
        
@pytest.mark.parametrize("dx", [1, 10, 1_000, 10**9])
def test_int_round_trip(dx):
    x, y = 1_000 * 10**9, 150_000 * 10**6   # 1,000 SOL / 150,000 USDT in base units
    dy = get_amount_out_int(x, y, dx)
    dx_back = get_amount_in_int(x, y, dy)
    assert dx_back <= dx          # rounding means you might need slightly less
    if dy > 0:
        assert dx_back > 0        # nothing is ever free
        
def test_int_never_pays_more_than_float():
    for dx in range(1, 1000):
        exact = get_amount_out(10_000, 1_000_000, dx, 0)
        rounded = get_amount_out_int(10_000, 1_000_000, dx, 0)
        assert rounded <= exact
        assert exact - rounded < 1