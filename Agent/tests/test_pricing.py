from app.llm.pricing import estimate_cost_usd


def test_known_model_computes_cost():
    cost = estimate_cost_usd("anthropic", "claude-sonnet-4-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 3.0 + 15.0


def test_unknown_model_returns_none():
    assert estimate_cost_usd("anthropic", "not-a-real-model", input_tokens=100, output_tokens=100) is None


def test_missing_token_counts_returns_none():
    assert estimate_cost_usd("anthropic", "claude-sonnet-4-5", input_tokens=None, output_tokens=100) is None


def test_cache_tokens_add_to_cost():
    base = estimate_cost_usd("anthropic", "claude-sonnet-4-5", input_tokens=1000, output_tokens=0)
    with_cache_write = estimate_cost_usd(
        "anthropic", "claude-sonnet-4-5", input_tokens=1000, output_tokens=0,
        cache_creation_input_tokens=1000,
    )
    assert with_cache_write > base
