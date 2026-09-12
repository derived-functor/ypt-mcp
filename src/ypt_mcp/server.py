"""MCP server exposing the YPT (열품타) study-time tracker.

The server runs over the stdio transport and exposes YPT data and timer
control through Model Context Protocol tools backed by the
:mod:`ypt_python` client library.

Authentication:
    The server reuses the JWT token cached by ``ypt-cli`` at
    ``~/.cache/ypt-python/token``. When no token is cached, it authenticates
    with the ``YPT_EMAIL``/``YPT_PASSWORD`` environment variables and stores
    the acquired token. A stale token is refreshed transparently on
    ``AuthenticationError``.

Tools:
    get_profile, get_day_log, get_my_rank, get_leaderboard, browse_groups,
    get_my_groups, get_group_members, start_study, stop_study
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from ypt_python import YPTClient
from ypt_python._exceptions import AuthenticationError

mcp = MCPServer(
    "ypt-mcp",
    instructions=(
        "Study-time tracker for the YPT (열품타) service. All tools require "
        "authentication via the cached JWT token or the YPT_EMAIL and "
        "YPT_PASSWORD environment variables.\n"
        "Workflow tips:\n"
        "  - Call get_profile first to learn category_id and country_id; "
        "pass them to get_my_rank and get_leaderboard.\n"
        "  - Study timer: call start_study, keep the started_at value from "
        "the response, then call stop_study with that started_at.\n"
        "  - Dates are YYYY-MM-DD strings; time is reported both in hours "
        "(*_hours, float) and raw milliseconds (*_ms, int)."
    ),
)

_DEVICE_MODEL = "ypt-mcp"
_STATE_FILE = Path("~/.cache/ypt-python/study_started_at").expanduser()


def _env_credentials() -> tuple[str, str]:
    """Return YPT credentials from the environment.

    :returns: A ``(email, password)`` tuple read from ``YPT_EMAIL`` and
        ``YPT_PASSWORD``.
    :rtype: tuple[str, str]
    :raises RuntimeError: If either environment variable is unset or empty.
    """
    email = os.environ.get("YPT_EMAIL", "")
    password = os.environ.get("YPT_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "YPT credentials not found: set YPT_EMAIL and YPT_PASSWORD, "
            "or log in with ypt-python first"
        )
    return email, password


async def _authenticated() -> YPTClient:
    """Build an authenticated client.

    Uses the cached JWT token when available; otherwise logs in with the
    environment credentials. The returned client must be closed by the
    caller (via ``async with``).
    """
    client = YPTClient(cache_token=True)
    if client.token is None:
        email, password = _env_credentials()
        await client.auth.login(email, password, language="en")
    return client


async def _call(coro):
    """Run a client call, re-authenticating once and retrying on failure.

    :param coro: Awaitable taking an authenticated :class:`YPTClient` and
        returning the tool result.
    :returns: The result of ``coro``.
    :raises RuntimeError: If credentials are unavailable when re-authenticating.
    """
    try:
        async with await _authenticated() as client:
            return await coro(client)
    except AuthenticationError:
        email, password = _env_credentials()
        async with YPTClient() as client:
            await client.auth.login(email, password, language="en")
            return await coro(client)


def _day_log_dict(log) -> dict[str, Any]:
    """Convert a :class:`DayLog` model into a plain JSON-able dict.

    :param log: The ``ypt_python._models.DayLog`` instance.
    :returns: Mapping with ``date``, study/rest/max/added values in both
        milliseconds and hours, and a ``subjects`` breakdown list.
    :rtype: dict[str, Any]
    """
    data: dict[str, Any] = {
        "date": log.date,
        "study_ms": log.study_ms,
        "rest_ms": log.rest_ms,
        "max_study_ms": log.max_study_ms,
        "added_ms": log.added_ms,
        "study_hours": log.study_hours,
        "rest_hours": log.rest_hours,
        "max_study_hours": log.max_study_ms / 3_600_000,
        "added_hours": log.added_ms / 3_600_000,
        "subjects": [
            {
                "subject_id": s.subject_id,
                "subject_title": s.subject_title,
                "study_ms": s.study_ms,
                "study_hours": s.study_hours,
            }
            for s in log.subjects
        ],
    }
    return data


def _group_dict(g) -> dict[str, Any]:
    """Convert a :class:`Group` model into a plain JSON-able dict.

    :param g: The ``ypt_python._models.Group`` instance.
    :returns: Mapping with ``id``, ``title``, ``category``, ``owner``,
        ``slogan`` and ``member_count``.
    :rtype: dict[str, Any]
    """
    return {
        "id": g.id,
        "title": g.title,
        "category": g.category,
        "owner": g.owner,
        "slogan": g.slogan,
        "member_count": g.member_count,
    }


@mcp.tool()
async def get_profile() -> dict[str, Any]:
    """Return the logged-in YPT profile with today's study overview.

    :returns: Mapping with ``nickname``, ``email``, ``category_code``,
        ``category_id``, ``country_id``, the ``subjects`` list
        (``id``, ``title``, ``study_ms``/``study_hours``, ``archived``) and
        the ``day_log`` for today (see the day-log shape in
        ``get_day_log``).
    :rtype: dict[str, Any]
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> dict[str, Any]:
        resp = await client.auth.reload_info()
        return {
            "nickname": resp.nickname,
            "email": resp.email,
            "category_code": resp.category_code,
            "category_id": resp.category_id,
            "country_id": resp.country_id,
            "subjects": [
                {
                    "id": s.id,
                    "title": s.title,
                    "study_ms": s.study_ms,
                    "study_hours": s.study_hours,
                    "archived": s.archived,
                }
                for s in resp.subjects
            ],
            "day_log": _day_log_dict(resp.day_log) if resp.day_log else None,
        }

    return await _call(_impl)


@mcp.tool()
async def get_day_log(date: str) -> dict[str, Any]:
    """Return your study log for the given date.

    :param date: Date in YYYY-MM-DD format, e.g. ``"2026-09-12"``.
    :type date: str
    :returns: Mapping with ``date``, ``study_ms``/``study_hours``,
        ``rest_ms``/``rest_hours``, ``max_study_ms``/``max_study_hours``,
        ``added_ms``/``added_hours`` and a ``subjects`` list of
        ``{subject_id, subject_title, study_ms, study_hours}``.
    :rtype: dict[str, Any]
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> dict[str, Any]:
        return _day_log_dict(await client.logs.day(date))

    return await _call(_impl)


@mcp.tool()
async def get_my_rank(category_id: int, country_id: int) -> int | None:
    """Return your position in a category leaderboard.

    :param category_id: Category ID, as returned by ``get_profile``.
    :type category_id: int
    :param country_id: Country ID, as returned by ``get_profile``.
    :type country_id: int
    :returns: Your 1-based rank as ``int``, or ``None`` when no rank is
        available for the category.
    :rtype: int | None
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> int | None:
        return await client.ranks.my_rank(category_id, country_id)

    return await _call(_impl)


@mcp.tool()
async def get_leaderboard(
    category_id: int,
    country_id: int,
    date: str,
    page: int = 1,
    rank_type: str = "day",
    limit: int = 20,
) -> dict[str, Any]:
    """Return the category leaderboard (top studiers) for a date.

    :param category_id: Category ID, as returned by ``get_profile``.
    :type category_id: int
    :param country_id: Country ID, as returned by ``get_profile``.
    :type country_id: int
    :param date: Leaderboard date in YYYY-MM-DD format.
    :type date: str
    :param page: Page number, 20 entries per page. Default ``1``.
    :type page: int
    :param rank_type: Ranking period, ``"day"`` or ``"week"``. Default
        ``"day"``.
    :type rank_type: str
    :param limit: Maximum number of members to return. Default ``20``.
    :type limit: int
    :returns: Mapping with ``total_count`` and the ``members`` list of
        ``{nickname, user_id, study_ms, study_hours, studicon_id}``.
    :rtype: dict[str, Any]
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> dict[str, Any]:
        result = await client.ranks.category_members(
            category_id, country_id, date, page=page, type_=rank_type
        )
        return {
            "total_count": result.total_count,
            "members": [
                {
                    "nickname": m.nickname,
                    "user_id": m.user_id,
                    "study_ms": m.study_ms,
                    "study_hours": m.study_hours,
                    "studicon_id": m.studicon_id,
                }
                for m in result.members[:limit]
            ],
        }

    return await _call(_impl)


@mcp.tool()
async def browse_groups(
    category_id: int = 0,
    page: int = 1,
    country_id: int | None = None,
    order_type: str = "promotedAt",
    only_available: bool = False,
    only_open: bool = False,
    only_cam: bool = False,
) -> list[dict[str, Any]]:
    """Browse public study groups.

    :param category_id: Filter by category ID; ``0`` means all categories.
        Default ``0``.
    :type category_id: int
    :param page: Page number. Default ``1``.
    :type page: int
    :param country_id: Filter by country ID; omit for all countries.
    :type country_id: int | None
    :param order_type: Sort order, e.g. ``"promotedAt"``. Default
        ``"promotedAt"``.
    :type order_type: str
    :param only_available: Show only groups with free slots. Default
        ``False``.
    :type only_available: bool
    :param only_open: Show only open groups. Default ``False``.
    :type only_open: bool
    :param only_cam: Show only groups with camera verification. Default
        ``False``.
    :type only_cam: bool
    :returns: List of group mappings with ``id``, ``title``, ``category``,
        ``owner``, ``slogan`` and ``member_count``.
    :rtype: list[dict[str, Any]]
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> list[dict[str, Any]]:
        groups = await client.groups.browse(
            category_id=category_id,
            page=page,
            country_id=country_id,
            order_type=order_type,
            only_available=only_available,
            only_open=only_open,
            only_cam=only_cam,
        )
        return [_group_dict(g) for g in groups]

    return await _call(_impl)


@mcp.tool()
async def get_my_groups() -> list[dict[str, Any]]:
    """Return the list of study groups you have joined.

    :returns: List of group mappings with ``id``, ``title``, ``category``,
        ``owner``, ``slogan`` and ``member_count``.
    :rtype: list[dict[str, Any]]
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> list[dict[str, Any]]:
        groups = await client.groups.my_groups()
        return [_group_dict(g) for g in groups]

    return await _call(_impl)


@mcp.tool()
async def get_group_members(group_id: int, country_id: int) -> list[dict[str, Any]]:
    """Return the members of a study group with their study stats.

    :param group_id: Study group ID, e.g. from ``get_my_groups``.
    :type group_id: int
    :param country_id: Country ID, as returned by ``get_profile``.
    :type country_id: int
    :returns: List of member mappings with ``user_id``, ``nickname``,
        ``category``, ``study_ms``/``study_hours`` and ``studying``
        (bool, whether the member is currently studying).
    :rtype: list[dict[str, Any]]
    :raises RuntimeError: If YPT credentials are not configured.
    """

    async def _impl(client: YPTClient) -> list[dict[str, Any]]:
        members = await client.groups.members(group_id, country_id)
        return [
            {
                "user_id": m.user_id,
                "nickname": m.nickname,
                "category": m.category,
                "study_ms": m.study_ms,
                "study_hours": m.study_hours,
                "studying": m.studying,
            }
            for m in members
        ]

    return await _call(_impl)


@mcp.tool()
async def start_study(
    subject: str,
    device_model: str = _DEVICE_MODEL,
) -> dict[str, Any]:
    """Start studying a subject and record the session start time.

    The session start timestamp is stored on disk (so ``stop_study`` can be
    called without arguments) and also returned as ``started_at`` for the
    caller to keep.

    :param subject: Subject title to start studying, e.g. ``"Матеша"``.
    :type subject: str
    :param device_model: Device model reported to the YPT API. Defaults to
        ``"ypt-mcp"``.
    :type device_model: str
    :returns: Mapping with ``started_at`` (epoch ms) plus the full day-log
        shape described in ``get_day_log``.
    :rtype: dict[str, Any]
    :raises RuntimeError: If YPT credentials are not configured.
    """
    started_at = int(time.time() * 1000)

    async def _impl(client: YPTClient) -> dict[str, Any]:
        day = await client.study.start(subject, device_model)
        return {"started_at": started_at, **_day_log_dict(day)}

    result = await _call(_impl)
    _save_started_at(started_at)
    return result


@mcp.tool()
async def stop_study(
    started_at: int | None = None,
    device_model: str = _DEVICE_MODEL,
) -> dict[str, Any]:
    """Stop the study timer and finish the current session.

    If ``started_at`` is omitted the timestamp recorded by :func:`start_study`
    is used; the recorded value is cleared after a successful stop.

    :param started_at: Session start time in epoch milliseconds, as returned
        by ``start_study``. Optional; defaults to the recorded session.
    :type started_at: int | None
    :param device_model: Device model reported to the YPT API. Defaults to
        ``"ypt-mcp"``.
    :type device_model: str
    :returns: The full day-log shape described in ``get_day_log``.
    :rtype: dict[str, Any]
    :raises RuntimeError: If there is no recorded session and ``started_at``
        is not provided, or if YPT credentials are not configured.
    """
    if started_at is None:
        started_at = _load_started_at()
        if started_at is None:
            raise RuntimeError(
                "No recorded study session start. Pass started_at (epoch ms)."
            )

    async def _impl(client: YPTClient) -> dict[str, Any]:
        day = await client.study.stop(started_at, device_model)
        return _day_log_dict(day)

    try:
        return await _call(_impl)
    finally:
        _clear_started_at()


def _save_started_at(ts: int) -> None:
    """Persist the study session start timestamp to disk.

    :param ts: Start time in epoch milliseconds.
    :type ts: int
    """
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(str(ts), encoding="utf-8")


def _load_started_at() -> int | None:
    """Load the recorded study session start timestamp, if any.

    :returns: Epoch milliseconds, or ``None`` when no valid value is stored.
    :rtype: int | None
    """
    try:
        raw = _STATE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _clear_started_at() -> None:
    """Remove the recorded study session start timestamp from disk."""
    try:
        _STATE_FILE.unlink()
    except OSError:
        pass


def main() -> None:
    """Run the MCP server over the stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()