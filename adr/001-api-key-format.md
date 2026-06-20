# ADR-001: API Key Format

**Status:** Accepted

**Date:** 2026-05-11

**Author:** Johnny Huynh

---

## Context

OpenGateway needs a standard format for API keys (virtual keys) that:
- Is immediately recognisable as an OpenGateway key
- Follows industry conventions so users feel at home
- Is URL-safe and copy-paste friendly
- Provides sufficient entropy for security
- Distinguishes between secret keys, publishable keys, and test keys

## Decision

We will use the format:

```
sk-og-{token}
```

Where:
- `sk` = secret key (indicates this should not be exposed client-side)
- `og` = OpenGateway (branded prefix)
- `token` = 32 characters from `[A-Za-z0-9]` (190 bits of entropy)

### Examples

```
sk-og-aBcDeFgHiJkLmNoPqRsTuVwXyZ123456
sk-og-test-xYzAbCdEfGhIjKlMnOpQrStUvWx
```

### Variants

| Prefix | Purpose | Example |
|--------|---------|---------|
| `sk-og` | Production secret key | `sk-og-aBcDeFgHiJk...` |
| `pk-og` | Publishable key (if ever needed) | `pk-og-xYzAbCdEfGh...` |
| `sk-og-test` | Test/development keys | `sk-og-test-MnOpQrStUv...` |

## Consequences

### Positive

- **Familiar**: Matches OpenAI (`sk-...`), Stripe (`sk_live_...`), and Anthropic (`sk-ant-...`) conventions
- **Branded**: `og` makes it clear which service issued the key
- **Short**: Only 4 chars of prefix — keys stay readable in logs and env vars
- **URL-safe**: No characters requiring percent-encoding
- **Sufficient entropy**: 32 chars from 62-symbol alphabet = ~190 bits, far above the 128-bit minimum for cryptographic tokens

### Negative

- **Not self-documenting**: Unlike `sk_live_` or `sk_test_`, `sk-og` does not encode the environment
- **Collision risk with "og"**: If another service uses `sk-og`, keys could be confused (mitigated by the full token)

## Alternatives Considered

| Format | Why Rejected |
|--------|-------------|
| `sk-ogw` | One char longer, no meaningful gain in clarity |
| `sk-open-gateway` | Too verbose for env vars and logs |
| `og-{token}` | Missing `sk-` prefix breaks user expectations from OpenAI/Stripe |
| `sk-og-live-{token}` | Over-engineered for a single-tenant gateway; environment belongs in config, not the key |
| UUIDv4 | No branded prefix; harder to identify in logs and support tickets |

## References

- [OpenAI API key format](https://platform.openai.com/docs/api-reference/authentication)
- [Stripe API key format](https://stripe.com/docs/keys)
- [NIST SP 800-57: Recommendation for Key Management](https://csrc.nist.gov/publications/detail/sp/800-57/final)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
