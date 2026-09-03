# Decisions

Dated decisions with the alternative considered and why.

## CO sensor uses `SensorDeviceClass.CO`, not `CARBON_MONOXIDE`

Home Assistant's `SensorDeviceClass` enum has no `CARBON_MONOXIDE` member;
the carbon monoxide device class is `SensorDeviceClass.CO` (value
`"carbon_monoxide"`). Using `SensorDeviceClass.CARBON_MONOXIDE` raises an
`AttributeError` at import time. Both `co_level` (older models) and `co_ppm`
(DETECT-series) sensor descriptions in `sensor.py` use `SensorDeviceClass.CO`.

## Releases are cut automatically from every merge to main

The release workflow (`.github/workflows/release.yaml`) computes a calendar
version (`YYYY.MM.DD.N`, `N` restarting at 1 each day), bumps
`manifest.json`, commits that bump with `[skip ci]` so it does not
re-trigger itself, tags the commit, and publishes the release with a
HACS-installable zip, a sigstore signature, and checksums. Nobody sets the
version or pushes a tag by hand. This matches the release-and-security
baseline used across the trooperthorn Home Assistant repositories: a merge
to `main` is the only release path.
