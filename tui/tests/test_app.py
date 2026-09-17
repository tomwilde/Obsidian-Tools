import asyncio

from main import ObsidianTui


def test_app_mounts_headless():
    async def _run():
        app = ObsidianTui(
            "http://localhost:1",
            "http://localhost:11434/v1",
            "test-model",
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#chat-input", object) is not None
            assert app.query_one("#tool-list", object) is not None
            await pilot.pause()

    asyncio.run(_run())