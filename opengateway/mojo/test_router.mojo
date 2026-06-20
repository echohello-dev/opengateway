"""Tests for opengateway.mojo.router.

Run with ``pixi run -e mojo mojo run opengateway/mojo/test_router.mojo``
(or as part of the ``mojo test`` job in CI). The router is pure
string-prefix logic so it doesn't need a flare server fixture.
"""
from std.testing import assert_equal, assert_true

from .router import select_provider_module


fn test_routes_gpt_models_to_openai() raises:
    let m = select_provider_module("gpt-4")
    assert_equal(m, "opengateway.providers.openai")


fn test_routes_gpt_4o_mini_to_openai() raises:
    let m = select_provider_module("gpt-4o-mini")
    assert_equal(m, "opengateway.providers.openai")


fn test_routes_openai_prefix_to_openai() raises:
    let m = select_provider_module("openai/gpt-4")
    assert_equal(m, "opengateway.providers.openai")


fn test_routes_claude_models_to_anthropic() raises:
    let m = select_provider_module("claude-3-5-sonnet")
    assert_equal(m, "opengateway.providers.anthropic")


fn test_routes_anthropic_prefix_to_anthropic() raises:
    let m = select_provider_module("anthropic/claude-3-opus")
    assert_equal(m, "opengateway.providers.anthropic")


fn test_routes_bedrock_prefix_to_bedrock() raises:
    let m = select_provider_module("bedrock/anthropic.claude-3-sonnet")
    assert_equal(m, "opengateway.providers.bedrock")


fn test_routes_amazon_prefix_to_bedrock() raises:
    let m = select_provider_module("amazon.nova-pro-v1:0")
    assert_equal(m, "opengateway.providers.bedrock")


fn test_returns_empty_for_unknown_model() raises:
    let m = select_provider_module("mystery-model-9000")
    assert_equal(m, "")


fn main() raises:
    test_routes_gpt_models_to_openai()
    test_routes_gpt_4o_mini_to_openai()
    test_routes_openai_prefix_to_openai()
    test_routes_claude_models_to_anthropic()
    test_routes_anthropic_prefix_to_anthropic()
    test_routes_bedrock_prefix_to_bedrock()
    test_routes_amazon_prefix_to_bedrock()
    test_returns_empty_for_unknown_model()
    print("opengateway.mojo.router: all tests passed")

