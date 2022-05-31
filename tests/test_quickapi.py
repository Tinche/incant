"""Tests for the quickapi module."""
from asyncio import create_task, sleep
from sys import version_info
from time import perf_counter

import pytest

from httpx import AsyncClient
from uvicorn import Config, Server  # type: ignore

from .quickapi import app


class UvicornTestServer(Server):
    def install_signal_handlers(self) -> None:
        return


@pytest.fixture
async def quickapi_server(unused_tcp_port_factory):
    port = unused_tcp_port_factory()
    s = UvicornTestServer(Config(app=app, port=port))
    create_task(s.serve())
    yield f"http://localhost:{port}"
    s.should_exit = True
    await sleep(0.2)


async def test_index(quickapi_server: str):
    async with AsyncClient() as client:
        resp = (await client.get(f"{quickapi_server}/")).text
        assert resp == "OK"


async def test_async_context_manager(quickapi_server: str):
    async with AsyncClient() as client:
        resp = (await client.get(f"{quickapi_server}/taskgroup")).text
        assert resp == "nice"


async def test_payload_handler(quickapi_server: str):
    async with AsyncClient() as client:
        resp = (await client.get(f"{quickapi_server}/header")).text
        assert resp == "The header was: none"

        resp = (
            await client.post(f"{quickapi_server}/payload", content=b'{"field": 1}')
        ).text
        assert resp == "After payload"


async def test_header_handler(quickapi_server: str):
    async with AsyncClient() as client:
        resp = (await client.get(f"{quickapi_server}/header")).text
        assert resp == "The header was: none"

        resp = (
            await client.get(
                f"{quickapi_server}/header", headers={"content-type": "test"}
            )
        ).text
        assert resp == "The header was: test"


@pytest.mark.skipif(
    version_info[:2] <= (3, 8), reason="Quattro cancellation not supported on 3.8"
)
async def test_timeout(quickapi_server: str):
    async with AsyncClient() as client:
        start = perf_counter()
        resp = await client.get(
            f"{quickapi_server}/slow", headers={"timeout": "0.1"}, timeout=1.0
        )
        duration = perf_counter() - start
        assert resp.status_code == 500
        assert duration <= 0.5
