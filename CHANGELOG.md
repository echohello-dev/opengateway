# Changelog

## 0.1.0 (2026-08-09)


### Features

* db-backed virtual keys and redis rate limiting in the bridge ([#30](https://github.com/echohello-dev/opengateway/issues/30)) ([8136d5e](https://github.com/echohello-dev/opengateway/commit/8136d5ee7be450485e2558415ba70ac7386c1dc6))
* guard h3 + honest ADR update on the reactor driver gap ([#38](https://github.com/echohello-dev/opengateway/issues/38)) ([5b96b70](https://github.com/echohello-dev/opengateway/commit/5b96b702e290a3b7bc1a07484ba5479222863e87))
* in-binary TLS proxy library (with honest re-scope) ([#32](https://github.com/echohello-dev/opengateway/issues/32)) ([9abe687](https://github.com/echohello-dev/opengateway/commit/9abe6872eb85755c08f3fa2b5e9fcc797dab1996))
* initial OpenGateway setup ([#5](https://github.com/echohello-dev/opengateway/issues/5)) ([6c50f05](https://github.com/echohello-dev/opengateway/commit/6c50f05399a6a625b5f1e8807d791ef6df455763))
* metrics and rate-limit middleware on the mojo server ([#27](https://github.com/echohello-dev/opengateway/issues/27)) ([4a7b141](https://github.com/echohello-dev/opengateway/commit/4a7b141783ee3db780240636bee699519d0a607d))
* Mojo (flare) API surface, release-please, CI, and positioning README ([#6](https://github.com/echohello-dev/opengateway/issues/6)) ([44cbb3a](https://github.com/echohello-dev/opengateway/commit/44cbb3aef877802681003fe1aed6fdb59b941cff))
* Mojo-on-flare default server with SSE streaming (ADR-003) ([#26](https://github.com/echohello-dev/opengateway/issues/26)) ([37dc66d](https://github.com/echohello-dev/opengateway/commit/37dc66d89d8f6c85ddefec3610b0f45ba9b9fb78))
* native TLS termination via flare's reactor-side serve_tls ([#36](https://github.com/echohello-dev/opengateway/issues/36)) ([5b79070](https://github.com/echohello-dev/opengateway/commit/5b79070a95e44b978b6fd3fd1f491b11ab1d253d))
* pass raw upstream SSE chunks through verbatim ([#28](https://github.com/echohello-dev/opengateway/issues/28)) ([b8fbfa3](https://github.com/echohello-dev/opengateway/commit/b8fbfa3c77a373168e5cd1706d4bbd02d81ccae4))
* token-denominated spend recording + sliding-window rate limit ([#31](https://github.com/echohello-dev/opengateway/issues/31)) ([e7b9f93](https://github.com/echohello-dev/opengateway/commit/e7b9f93cb679cfce805e44e32525edc3853635a9))


### Bug Fixes

* appease ruff 0.16+ in _repro_tls.py ([86854c9](https://github.com/echohello-dev/opengateway/commit/86854c9cd495af9890bd3c7f26887181a1ffb9f9))
* **ci:** add id-token: write for PyPI trusted publishing ([#14](https://github.com/echohello-dev/opengateway/issues/14)) ([767d424](https://github.com/echohello-dev/opengateway/commit/767d424edaef771126118a0c8974fbaa2938c379))
* **ci:** drop osx-64 pixi platform and apply ruff format ([#9](https://github.com/echohello-dev/opengateway/issues/9)) ([a7d404e](https://github.com/echohello-dev/opengateway/commit/a7d404e92503a828c4e16376a0f16c4264d45991))
* **ci:** handle Mojo versions without `mojo format --check` ([#10](https://github.com/echohello-dev/opengateway/issues/10)) ([8175eb1](https://github.com/echohello-dev/opengateway/commit/8175eb15208960eba7ad52cc2a476b5c37d0f859))
* **ci:** make entire mojo job non-blocking ([#13](https://github.com/echohello-dev/opengateway/issues/13)) ([713a240](https://github.com/echohello-dev/opengateway/commit/713a240f8cf74c3a2f6efdd76159114a3ab00627))
* **ci:** make mojo format check best-effort, not blocking ([#11](https://github.com/echohello-dev/opengateway/issues/11)) ([ef71bea](https://github.com/echohello-dev/opengateway/commit/ef71beae0edd46a21c10c272f281f8acd762cce5))
* **ci:** pin real action SHAs and add linux-64 pixi platform ([#7](https://github.com/echohello-dev/opengateway/issues/7)) ([0b68d7e](https://github.com/echohello-dev/opengateway/commit/0b68d7ecf3c5d02e3b64bcad1ab7e92615c34ad3))


### Documentation

* compact banner with Mojo flame logo ([#24](https://github.com/echohello-dev/opengateway/issues/24)) ([83b6382](https://github.com/echohello-dev/opengateway/commit/83b6382071501d5f904c30df7cb4e1c6cd8e6ea1))
* document in-binary TLS termination + self-signed cert gotcha ([0217ece](https://github.com/echohello-dev/opengateway/commit/0217ece7199abc487fa358d33f7cdb375d43deec))
* link ADR-003 [#4](https://github.com/echohello-dev/opengateway/issues/4) to the upstream flare and Mojo-runtime issues ([#34](https://github.com/echohello-dev/opengateway/issues/34)) ([aa47158](https://github.com/echohello-dev/opengateway/commit/aa471583c45df94dfd8875dd1fbc4f0656effdf5))
* reimagine banner as editorial dashboard (4:1, smaller, stats + sparkline) ([#21](https://github.com/echohello-dev/opengateway/issues/21)) ([a319b24](https://github.com/echohello-dev/opengateway/commit/a319b249ae4f6d7a7887d0a532afb90f4c396447))
* reimagine banner as marketing hero (dashboard mockup + stats) ([#22](https://github.com/echohello-dev/opengateway/issues/22)) ([0ba16fc](https://github.com/echohello-dev/opengateway/commit/0ba16fcf31f91ffffeda48f8acc2b23149703374))
* replace ASCII banner with fal.ai-generated image ([#18](https://github.com/echohello-dev/opengateway/issues/18)) ([382580f](https://github.com/echohello-dev/opengateway/commit/382580fd8b12cb3c1ad79d6bed9745b6c48484b7))
* replace incorrect ASCII banner with figlet-generated art ([#16](https://github.com/echohello-dev/opengateway/issues/16)) ([9372252](https://github.com/echohello-dev/opengateway/commit/93722527192fa641c6e807febb6785810322a997))
* restyle banner to editorial wordmark (flatter, no icon) ([#20](https://github.com/echohello-dev/opengateway/issues/20)) ([2a23a9c](https://github.com/echohello-dev/opengateway/commit/2a23a9caee362ddc0d763a67dfce8d291ce9436f))
* restyle banner, add drop-in + integrations + repo structure ([#19](https://github.com/echohello-dev/opengateway/issues/19)) ([6634443](https://github.com/echohello-dev/opengateway/commit/6634443b75d3f16640dc2f56a2d38db704f28254))
* simplify banner to grid + archway logo + wordmark ([#23](https://github.com/echohello-dev/opengateway/issues/23)) ([2634bd7](https://github.com/echohello-dev/opengateway/commit/2634bd7f7e8c777cc36277ebac7ac0aee18d7abd))

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
