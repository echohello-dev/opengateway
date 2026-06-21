# Release Process

OpenGateway uses [release-please](https://github.com/googleapis/release-please)
to automate versioning, changelogs, and PyPI publishing from
conventional commits on `main`.

## How a release happens

1. Commits land on `main` following the [Conventional Commits](https://www.conventionalcommits.org/)
   spec. The commit type determines the version bump.

   | Commit type | Bump |
   |---|---|
   | `feat:` | minor (0.x.0) |
   | `fix:` | patch (0.0.x) |
   | `perf:`, `refactor:`, `docs:` | patch |
   | `feat!:` or `BREAKING CHANGE:` footer | major (x.0.0) |
   | `chore:`, `test:`, `build:`, `ci:` | no release |

2. On every push to `main`, the [Release Please](./.github/workflows/release-please.yml)
   workflow runs.

3. Release-please opens (or updates) a "Release PR" titled
   `chore(main): release <version>`. The PR body is the curated
   changelog grouped by commit type.

4. When the Release PR is merged, release-please:
   - Tags the merge commit with `v<version>`.
   - Creates a GitHub Release with notes from the changelog.
   - Builds and publishes the Python wheel + sdist to PyPI via
     [pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish).

5. The container image (Docker Hub / GHCR) is rebuilt from the new
   tag by an external workflow.

## Versioning

- Current state: **0.1.0** (alpha, per the README).
- Until `1.0.0`, **every `feat:` is a minor bump**. This matches the
  `bump-minor-pre-major` flag in the workflow.
- Pre-1.0 breaking changes still bump the minor — by convention we
  treat the `0.x` line as a single API surface.

## Writing commit messages

The format is `<type>(<scope>): <description>`. Examples:

```
feat(router): add Anthropic provider routing rule
fix(auth): accept empty bearer header as missing
docs: document the hybrid Mojo + Python architecture
perf(providers): reuse httpx client across requests
chore(deps): bump pydantic to 2.10.3
```

Scopes are free-form but encouraged: `router`, `auth`, `providers`,
`bridge`, `ci`, `release`, `docs`.

Breaking changes need a `!` after the type/scope and a `BREAKING CHANGE:`
footer:

```
feat(auth)!: drop support for legacy sk-* root key format

BREAKING CHANGE: root keys must now match the sk-og-{32 chars}
format documented in ADR-001.
```

## Local release dry-run

Release-please runs entirely in CI — there is nothing to do locally
beyond writing good commit messages. If you want to preview what the
next release would look like:

```bash
# Use release-please locally
npx release-please release-pr \
  --token="$GITHUB_TOKEN" \
  --repo-url=echohello-dev/opengateway \
  --release-type=python
```

Or just look at the "Release PR" body after the next push to `main`.

## PyPI publishing

The PyPI publish step uses the trusted publisher flow — no API token
is stored in the repo. To configure it:

1. In PyPI, navigate to the project → Publishing → Add a new pending
   publisher.
2. Set:
   - Owner: `echohello-dev`
   - Repository: `opengateway`
   - Workflow filename: `release-please.yml`
   - Environment name: (leave blank)

Once configured, every release-please run on `main` will publish to
PyPI without any secrets.

## Tagging the Mojo binary

The Mojo binary is built inside the `mojo` job in `ci.yml` but is
**not** published as a release artifact yet. To add binary releases:

1. Add a `release-please-config.json` with a `extra-files` entry
   pointing at `dist-mojo/opengateway-mojo-<os>-<arch>`.
2. Build the binary in a release-only job and attach it to the
   GitHub Release via the `upload-assets` action.

Tracked as a follow-up — the current shape is source-only PyPI
publishing.

## Rolling back a release

If a release ships broken code:

1. `git revert` the offending merge commit on `main`. This opens a
   patch-bump PR via release-please.
2. **For PyPI**: the bumped patch version is published. You cannot
   re-upload a deleted version on PyPI — that's why releases are
   immutable.
3. If the bad release needs to be yanked immediately, do it manually
   from the PyPI project page.

For **Mojo binary** rollbacks: just cut a new release with the fix;
don't try to retroactively rebuild the bad tag.
