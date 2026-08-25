# USD per million tokens, (input, output)
_PRICING_PER_MTOK: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-sonnet-4-5"): (3.0, 15.0),
    ("anthropic", "claude-opus-4-5"): (15.0, 75.0),
    ("anthropic", "claude-haiku-4-5"): (0.8, 4.0),
}

# Anthropic prices cache writes/reads as a multiple of the base input price.
_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.1


def estimate_cost_usd(
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_creation_input_tokens: int | None = None,
    cache_read_input_tokens: int | None = None,
) -> float | None:
    prices = _PRICING_PER_MTOK.get((provider, model))
    if prices is None or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = prices

    cost = input_tokens * input_price + output_tokens * output_price
    if cache_creation_input_tokens:
        cost += cache_creation_input_tokens * input_price * _CACHE_WRITE_MULTIPLIER
    if cache_read_input_tokens:
        cost += cache_read_input_tokens * input_price * _CACHE_READ_MULTIPLIER
    return cost / 1_000_000
