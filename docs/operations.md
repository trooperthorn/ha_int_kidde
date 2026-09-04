# Operations

The test gate and the release path. Wire-level facts live in `protocol.md`.

## Test gate

The gate is the same on a workstation and in CI: `ruff check custom_components tests
scripts tools`, `pytest tests/ -v`, then `python scripts/build_release_artifacts.py
--validate-only`. Pins live in `requirements_test.txt`.

The suite covers the pure-Python protocol, capture, identity, and model modules and
imports no Home Assistant runtime, so it runs with plain `pytest`. Do not install the
Home Assistant test harness for it: the harness registers an async autouse fixture that
turns every synchronous test into a setup error under pytest 9. Entity and config-flow
behavior is exercised against a live instance (see `design.md`), not in this suite.

## Release path

A merge to `main` is the only release path. Nobody edits the manifest version or pushes a
tag by hand.

1. `Release` runs on every push to `main`. It calls the Test and Validate workflows, then
   reads the version from `custom_components/kidde_homesafe/manifest.json` through
   `.release.json`. If a published release for that version already exists it stops.
   Otherwise it builds the deterministic archive, signs it with sigstore through the
   workflow's OIDC identity, generates the SPDX SBOM and checksums, attests the archive
   and the SBOM, creates the `v<version>` tag on the exact commit, drafts the release
   with every asset attached, and publishes it. HACS installs from the release archive
   (`hacs.json` sets `hide_default_branch`), so the archive is the shipped product.
2. `Prepare release` runs after every successful `Release` on `main`. When the manifest
   version equals the latest published release and `custom_components/kidde_homesafe` changed
   since that tag, it runs `scripts/set_version.py --next-from-tags`, pushes the bump to
   `automation/calver-release` with a GitHub App token, opens a PR, and arms squash
   auto-merge. The merge triggers `Release` again, which publishes the new version. Docs,
   tests, and workflow changes do not bump the version.
3. Without the GitHub App credentials the second step fails at its credential check and
   nothing else happens. The repository still releases: run
   `python scripts/set_version.py --next-from-tags` on a branch, open the PR, and the
   merge publishes.

`.release.json` is the single statement of what ships: the tag prefix (`v`), the time zone
the CalVer date is taken in, the release-bearing path, and the version field.
`scripts/set_version.py` is the only writer of that field; `scripts/release_config.py`
behind `build_release_artifacts.py --validate-only` is the independent reader, so a writer
defect cannot validate itself. Versions are `YYYY.MM.DD.N` in `America/Chicago`.

### Verifying a release

The release summary prints the commands: download the archive, its `.sigstore.json`,
and `SHA256SUMS`; check the sums; run `gh attestation verify` for provenance; and run
`python -m sigstore verify github` with the workflow identity for the signature.

### GitHub App for zero-touch version PRs

`Prepare release` needs the release GitHub App (Contents: Read and write, Pull requests:
Read and write) installed on this repository, plus the repository variable
`RELEASE_AUTOMATION_CLIENT_ID` and the Actions secret `RELEASE_AUTOMATION_PRIVATE_KEY`.
The same App serves every trooperthorn Home Assistant repository; each repository holds
its own copy of the variable and secret. The token is minted only after the workflow has
proved a bump is needed, expires on its own, and is scoped to this repository. The
workflow's own `GITHUB_TOKEN` stays read-only.

### Branch and protection settings

`main` is the only long-lived branch. Work happens on short-lived branches that end in a
squash-merged PR and are deleted on merge. Branch protection requires the job display
names `pytest (Python 3.14)`, `HACS validation`, `hassfest (manifest sanity)`,
`CodeQL (python)`, and `Python static security checks`, with strict up-to-date checks,
enforced for administrators, no force pushes, no deletions, and no required approvals.

## Line endings

`.gitattributes` pins every text file to LF so Windows checkouts and WSL or Linux tools
see the same bytes.
