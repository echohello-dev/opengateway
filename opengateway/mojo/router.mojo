"""Model → provider routing for the Mojo API surface.

Maps an inbound model name (e.g. ``"gpt-4"`` or ``"openai/gpt-4o-mini"``)
to the fully-qualified Python module that handles the upstream call.
The Python bridge imports the module on demand and dispatches.

Adding a new provider:

1. Implement a :class:`BaseProvider` subclass in
   ``opengateway/providers/<name>.py``.
2. Append a routing rule below that returns the provider module path.
3. Configure the API key in :class:`Settings`.
"""


fn select_provider_module(model: String) -> String:
    """Return the Python module that handles ``model``, or ``""`` if unknown.

    Routing rules are evaluated in declaration order. The first match wins.

    Args:
        model: The OpenAI-compatible model identifier from the request.

    Returns:
        Fully-qualified Python module path (e.g. ``"opengateway.providers.openai"``),
        or an empty string when no provider can serve the requested model.
    """
    if model.startswith("gpt-") or model.startswith("openai/"):
        return "opengateway.providers.openai"
    if model.startswith("claude-") or model.startswith("anthropic/"):
        return "opengateway.providers.anthropic"
    if model.startswith("bedrock/") or model.startswith("amazon."):
        return "opengateway.providers.bedrock"
    return ""
