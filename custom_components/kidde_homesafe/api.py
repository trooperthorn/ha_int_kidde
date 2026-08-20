"""Async client for the Kidde HomeSafe cloud API.

This is a vendored, improved client (originally inspired by the
``kidde-homesafe`` PyPI package by 865charlesw, MIT licensed).

Improvements over the upstream package:

* Re-uses Home Assistant's shared ``aiohttp.ClientSession`` instead of
  opening a brand-new TCP+TLS connection for every request, which
  substantially reduces per-poll latency.
* Fetches devices/events for all locations concurrently.
* Applies an explicit per-request timeout.
* Distinguishes authentication errors from transport errors.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, Literal

import aiohttp

API_PREFIX = "https://api.homesafe.kidde.com/api/v4"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20)


class KiddeCommand(StrEnum):
    """Known device commands."""

    IDENTIFY = auto()
    IDENTIFYCANCEL = auto()
    TEST = auto()
    HUSH = auto()


class KiddeClientError(Exception):
    """Base exception for Kidde client errors."""


class KiddeClientAuthError(KiddeClientError):
    """The Kidde cloud rejected the credentials or session cookies."""


class KiddeClientCommunicationError(KiddeClientError):
    """The Kidde cloud could not be reached or returned an error."""


def _dict_by_ids(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Create a dictionary from a list of items, keyed by ID.

    Later duplicates overwrite earlier ones rather than raising, so a
    transient API glitch cannot take the whole integration down.
    """
    return {item["id"]: item for item in items}


@dataclass(frozen=True)
class KiddeDataset:
    """Dataset of locations, devices, and events.

    Attributes
    ----------
    locations : dict[int, dict[str, Any]]
        Dicts of location data, keyed by id.
    devices : dict[int, dict[str, Any]]
        Dicts of device data, keyed by id.
    events : dict[int, dict[str, Any]]
        Dicts of event data, keyed by id.
    """

    locations: dict[int, dict[str, Any]]
    devices: dict[int, dict[str, Any]]
    events: dict[int, dict[str, Any]]


class KiddeClient:
    """API client for Kidde HomeSafe."""

    def __init__(
        self,
        cookies: dict[str, str],
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize client with session cookies."""
        self.cookies = cookies
        self._session = session

    @classmethod
    async def from_login(
        cls,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> KiddeClient:
        """Create a client from an email/password login."""
        url = f"{API_PREFIX}/auth/login"
        payload = {"email": email, "password": password}
        try:
            if session is not None:
                async with session.post(
                    url, json=payload, timeout=DEFAULT_TIMEOUT
                ) as response:
                    cookies = await cls._cookies_from_login_response(response)
            else:
                async with aiohttp.request(
                    "POST", url, json=payload, timeout=DEFAULT_TIMEOUT
                ) as response:
                    cookies = await cls._cookies_from_login_response(response)
        except KiddeClientError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise KiddeClientCommunicationError(str(err)) from err
        return cls(cookies, session)

    @staticmethod
    async def _cookies_from_login_response(
        response: aiohttp.ClientResponse,
    ) -> dict[str, str]:
        """Validate a login response and extract session cookies."""
        if response.status in (401, 403):
            raise KiddeClientAuthError
        if response.status >= 400:
            raise KiddeClientCommunicationError(f"HTTP {response.status}")
        return {c.key: c.value for c in response.cookies.values()}

    async def _request(
        self, path: str, method: Literal["GET", "POST"] = "GET"
    ) -> Any:
        """Make an authenticated request and return the JSON payload."""
        url = f"{API_PREFIX}/{path}"
        try:
            if self._session is not None:
                async with self._session.request(
                    method, url, cookies=self.cookies, timeout=DEFAULT_TIMEOUT
                ) as response:
                    return await self._parse_response(response)
            async with aiohttp.request(
                method, url, cookies=self.cookies, timeout=DEFAULT_TIMEOUT
            ) as response:
                return await self._parse_response(response)
        except KiddeClientError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise KiddeClientCommunicationError(str(err)) from err

    @staticmethod
    async def _parse_response(response: aiohttp.ClientResponse) -> Any:
        """Validate a response and return its JSON payload (or None)."""
        if response.status in (401, 403):
            raise KiddeClientAuthError
        if response.status >= 400:
            raise KiddeClientCommunicationError(f"HTTP {response.status}")
        if response.status == 204:
            return None
        return await response.json()

    async def get_data(
        self, get_devices: bool = True, get_events: bool = True
    ) -> KiddeDataset:
        """Fetch locations plus (concurrently) their devices and events."""
        location_list = await self._request("location")
        locations = _dict_by_ids(location_list)

        device_tasks = (
            [self._request(f"location/{lid}/device") for lid in locations]
            if get_devices
            else []
        )
        event_tasks = (
            [self._request(f"location/{lid}/event") for lid in locations]
            if get_events
            else []
        )
        results = await asyncio.gather(*device_tasks, *event_tasks)

        devices: dict[int, dict[str, Any]] = {}
        events: dict[int, dict[str, Any]] = {}
        if get_devices:
            device_lists = results[: len(device_tasks)]
            devices = _dict_by_ids(
                [device for sub in device_lists for device in sub]
            )
        if get_events:
            event_lists = results[len(device_tasks) :]
            events = _dict_by_ids(
                [event for sub in event_lists for event in sub["events"]]
            )
        return KiddeDataset(locations, devices, events)

    async def device_command(
        self, location_id: int, device_id: int, command: KiddeCommand
    ) -> None:
        """Send a command to a device."""
        await self._request(
            f"location/{location_id}/device/{device_id}/{command}", "POST"
        )
