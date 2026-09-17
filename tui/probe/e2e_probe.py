import asyncio

from main import ObsidianTui


async def main() -> None:
    app = ObsidianTui(
        "http://localhost:8000/mcp", "http://localhost:11434/v1", "gemma4:12b-it-qat"
    )
    async with app.run_test(headless=True, size=(172, 44)) as pilot:
        for _ in range(600):
            await pilot.pause()
            status = str(app.query_one("#status").render())
            if "tools" in status and "Connecting" not in status:
                break
        print("STATUS  :", status)
        lv = app.query_one("#tool-list")
        items = app.query_one("#tool-list").children
        labels = [
            child.render()
            for item in items
            for child in item.children
            if hasattr(child, "render") and child.__class__.__name__ == "Label"
        ]
        print("LEVEL-1 children:", len(items))
        print("LABELS  :", labels)
        print("SCROLL? :", await app.query_one("#tool-list").get_content_height(None, None))
        await app.export_screenshot("/tmp/tui_probe.png")


asyncio.run(main())
