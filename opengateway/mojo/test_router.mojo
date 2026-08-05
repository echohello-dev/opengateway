"""Tests for opengateway.mojo.router.

Run with ``pixi run -e mojo mojo -I . opengateway/mojo/test_router.mojo``.
The router is pure string-prefix logic so it doesn't need a flare server
fixture.
"""
from std.testing import assert_equal


def select_provider_module(model: String) -> String:
    """Mirror of opengateway/mojo/router.mojo - kept inline so this
    script is runnable as a single file. Drift between this copy and
    router.mojo is checked by the Mojo router drift guard test in
    tests/test_mojo_bridge.py."""
    if model.startswith("gpt-") or model.startswith("openai/"):
        return "opengateway.providers.openai"
    if model.startswith("claude-") or model.startswith("anthropic/"):
        return "opengateway.providers.anthropic"
    if model.startswith("bedrock/") or model.startswith("amazon."):
        return "opengateway.providers.bedrock"
    return ""


def test_routes_gpt_models_to_openai() raises:
    var m = select_provider_module("gpt-4")
    assert_equal(m, "opengateway.providers.openai")


def test_routes_gpt_4o_mini_to_openai() raises:
    var m = select_provider_module("gpt-4o-mini")
    assert_equal(m, "opengateway.providers.openai")


def test_routes_openai_prefix_to_openai() raises:
    var m = select_provider_module("openai/gpt-4")
    assert_equal(m, "opengateway.providers.openai")


def test_routes_claude_models_to_anthropic() raises:
    var m = select_provider_module("claude-3-5-sonnet")
    assert_equal(m, "opengateway.providers.anthropic")


def test_routes_anthropic_prefix_to_anthropic() raises:
    var m = select_provider_module("anthropic/claude-3-opus")
    assert_equal(m, "opengateway.providers.anthropic")


def test_routes_bedrock_prefix_to_bedrock() raises:
    var m = select_provider_module("bedrock/anthropic.claude-3-sonnet")
    assert_equal(m, "opengateway.providers.bedrock")


def test_routes_amazon_prefix_to_bedrock() raises:
    var m = select_provider_module("amazon.nova-pro-v1:0")
    assert_equal(m, "opengateway.providers.bedrock")


def test_returns_empty_for_unknown_model() raises:
    var m = select_provider_module("mystery-model-9000")
    assert_equal(m, "")


def main() raises:
    test_routes_gpt_models_to_openai()
    test_routes_gpt_4o_mini_to_openai()
    test_routes_openai_prefix_to_openai()
    test_routes_claude_models_to_anthropic()
    test_routes_anthropic_prefix_to_anthropic()
    test_routes_bedrock_prefix_to_bedrock()
    test_routes_amazon_prefix_to_bedrock()
    test_returns_empty_for_unknown_model()
    print("opengateway.mojo.router: all 8 tests passed")