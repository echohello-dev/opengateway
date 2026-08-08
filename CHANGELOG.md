# Changelog

## [0.2.0](https://github.com/echohello-dev/opengateway/compare/v0.1.1...v0.2.0) (2026-08-08)


### Features

* db-backed virtual keys and redis rate limiting in the bridge ([#30](https://github.com/echohello-dev/opengateway/issues/30)) ([ac467ec](https://github.com/echohello-dev/opengateway/commit/ac467ec0083b550cd128ccaecb2bf4c6b67375f3))
* in-binary TLS proxy library (with honest re-scope) ([#32](https://github.com/echohello-dev/opengateway/issues/32)) ([c12f395](https://github.com/echohello-dev/opengateway/commit/c12f39527f9b52cad0235ce2b9ac1b0bdb4e2a77))
* metrics and rate-limit middleware on the mojo server ([#27](https://github.com/echohello-dev/opengateway/issues/27)) ([4443100](https://github.com/echohello-dev/opengateway/commit/4443100f41c642bcf305eee912df7d9e84db3a20))
* Mojo-on-flare default server with SSE streaming (ADR-003) ([#26](https://github.com/echohello-dev/opengateway/issues/26)) ([3a1778c](https://github.com/echohello-dev/opengateway/commit/3a1778cd4a01a784dca6be62c5e125c5ccb06c17))
* native TLS termination via flare's reactor-side serve_tls ([#36](https://github.com/echohello-dev/opengateway/issues/36)) ([a9fb34a](https://github.com/echohello-dev/opengateway/commit/a9fb34ac3da5da1f0be7f45bfa89bce56d78cee8))
* pass raw upstream SSE chunks through verbatim ([#28](https://github.com/echohello-dev/opengateway/issues/28)) ([deed620](https://github.com/echohello-dev/opengateway/commit/deed620e4489935170a87b5d2d4ab4556e100d1b))
* token-denominated spend recording + sliding-window rate limit ([#31](https://github.com/echohello-dev/opengateway/issues/31)) ([f32d60c](https://github.com/echohello-dev/opengateway/commit/f32d60c727c3caa69af3c5cea9552e94516b51e9))


### Documentation

* compact banner with Mojo flame logo ([#24](https://github.com/echohello-dev/opengateway/issues/24)) ([c633c72](https://github.com/echohello-dev/opengateway/commit/c633c72269a901b68fe21de3933038ad5f29516f))
* link ADR-003 [#4](https://github.com/echohello-dev/opengateway/issues/4) to the upstream flare and Mojo-runtime issues ([#34](https://github.com/echohello-dev/opengateway/issues/34)) ([f6c40d7](https://github.com/echohello-dev/opengateway/commit/f6c40d71b1963646fcfecb2f6ca0fcca7d103b29))
* reimagine banner as editorial dashboard (4:1, smaller, stats + sparkline) ([#21](https://github.com/echohello-dev/opengateway/issues/21)) ([008560a](https://github.com/echohello-dev/opengateway/commit/008560abfaff4f22df05e6776430a9264bfd9576))
* reimagine banner as marketing hero (dashboard mockup + stats) ([#22](https://github.com/echohello-dev/opengateway/issues/22)) ([27e3606](https://github.com/echohello-dev/opengateway/commit/27e36069617f00cb7af5dd87ab37372021f8b0d8))
* replace ASCII banner with fal.ai-generated image ([#18](https://github.com/echohello-dev/opengateway/issues/18)) ([3ee675d](https://github.com/echohello-dev/opengateway/commit/3ee675d57d80e1a95e601bd482a900b12d32c0d6))
* replace incorrect ASCII banner with figlet-generated art ([#16](https://github.com/echohello-dev/opengateway/issues/16)) ([6476d5a](https://github.com/echohello-dev/opengateway/commit/6476d5a2daa9335c5ef26b8f18b9cf8488a54424))
* restyle banner to editorial wordmark (flatter, no icon) ([#20](https://github.com/echohello-dev/opengateway/issues/20)) ([946a169](https://github.com/echohello-dev/opengateway/commit/946a16986a436b37fc194931140721e8a1f14af6))
* restyle banner, add drop-in + integrations + repo structure ([#19](https://github.com/echohello-dev/opengateway/issues/19)) ([58a8ef4](https://github.com/echohello-dev/opengateway/commit/58a8ef44221ca39b4ebdc233e480d5082dfd9d46))
* simplify banner to grid + archway logo + wordmark ([#23](https://github.com/echohello-dev/opengateway/issues/23)) ([3f75685](https://github.com/echohello-dev/opengateway/commit/3f756850eec431fa55d8314366586005cfbb9880))

## [0.1.1](https://github.com/echohello-dev/opengateway/compare/v0.1.0...v0.1.1) (2026-06-21)


### Bug Fixes

* **ci:** add id-token: write for PyPI trusted publishing ([#14](https://github.com/echohello-dev/opengateway/issues/14)) ([06493b2](https://github.com/echohello-dev/opengateway/commit/06493b227c8c18c7e6b1bb76ff1d2460454f6ffb))

## 0.1.0 (2026-06-21)


### Features

* initial OpenGateway setup ([#5](https://github.com/echohello-dev/opengateway/issues/5)) ([b97e0e8](https://github.com/echohello-dev/opengateway/commit/b97e0e8a040262409c9b3d8a613839992902b75f))
* Mojo (flare) API surface, release-please, CI, and positioning README ([#6](https://github.com/echohello-dev/opengateway/issues/6)) ([7e69537](https://github.com/echohello-dev/opengateway/commit/7e695375a9d811fa1f89f06ba7e77295c3a92da1))


### Bug Fixes

* **ci:** drop osx-64 pixi platform and apply ruff format ([#9](https://github.com/echohello-dev/opengateway/issues/9)) ([5faee88](https://github.com/echohello-dev/opengateway/commit/5faee88efb549b22c1c0a660490b8817d3cbd4e0))
* **ci:** handle Mojo versions without `mojo format --check` ([#10](https://github.com/echohello-dev/opengateway/issues/10)) ([2ab7050](https://github.com/echohello-dev/opengateway/commit/2ab70507c5f7b562add5cf61ad2d097184c9c29a))
* **ci:** make entire mojo job non-blocking ([#13](https://github.com/echohello-dev/opengateway/issues/13)) ([88c0474](https://github.com/echohello-dev/opengateway/commit/88c0474850d2433abdba5e07e855b8c8835ec715))
* **ci:** make mojo format check best-effort, not blocking ([#11](https://github.com/echohello-dev/opengateway/issues/11)) ([1f0c729](https://github.com/echohello-dev/opengateway/commit/1f0c7297137c36ae1dc39616f4d17d9e92577110))
* **ci:** pin real action SHAs and add linux-64 pixi platform ([#7](https://github.com/echohello-dev/opengateway/issues/7)) ([43a83c4](https://github.com/echohello-dev/opengateway/commit/43a83c46964f2909ed44d37432b85983516da559))
