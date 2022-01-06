"""Tests for the quickapi module."""
from asyncio import create_task, sleep

import pytest

from httpx import AsyncClient
from uvicorn import Config, Server

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


@pytest.mark.asyncio
async def test_index(quickapi_server: str):
    async with AsyncClient() as client:
        resp = (await client.get(f"{quickapi_server}/")).text
        assert resp == "OK"


@pytest.mark.asyncio
async def test_header_handler(quickapi_server: str):
    async with AsyncClient() as client:
        resp = (await client.get(f"{quickapi_server}/header")).text
        assert resp == "The header was: none"
