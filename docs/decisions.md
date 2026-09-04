# Decisions

Dated decisions with the alternative considered and why.

## CO sensor uses `SensorDeviceClass.CO`, not `CARBON_MONOXIDE`

Home Assistant's `SensorDeviceClass` enum has no `CARBON_MONOXIDE` member;
the carbon monoxide device class is `SensorDeviceClass.CO` (value
`"carbon_monoxide"`). Using `SensorDeviceClass.CARBON_MONOXIDE` raises an
`AttributeError` at import time. Both `co_level` (older models) and `co_ppm`
(DETECT-series) sensor descriptions in `sensor.py` use `SensorDeviceClass.CO`.

## Releases are cut automatically from every merge to main

A merge to `main` is the only release path. `Release` publishes the version already
written in `manifest.json`, validated through `.release.json`, with the signed archive,
SBOM, checksums, and attestations; `Prepare release` writes the next CalVer into the
manifest in a reviewed, auto-merged PR when release-bearing files changed. `operations.md`
has the full path. Nobody sets the version or pushes a tag by hand.

Rejected on 2026-09-04: the previous flow, where the release job computed the next
version, committed the manifest bump straight to `main` with `[skip ci]`, and tagged it.
That flow needed a partial-failure recovery rule (a bump pushed but never tagged), could
not coexist with branch protection, and put unreviewed bytes on the default branch.
