import asyncio
from types import SimpleNamespace

import pytest

from chat import parse_arguments, to_openai_tools
from ollama import OllamaClient


def _tool(name="list_files", description="List files", schema=None):
    return {
        "name": name,
        "description": description,
        "input_schema": schema or {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    }


def test_to_openai_tools_maps_each_tool():
    tools = to_openai_tools([_tool(), _tool("read_file", "Read a file")])
    assert len(tools) == 2
    first = tools[0]
    assert first["type"] == "function"
    assert first["function"]["name"] == "list_files"
    assert first["function"]["description"] == "List files"
    assert first["function"]["parameters"]["type"] == "object"


def test_to_openai_tools_coerces_non_object_schema():
    tools = to_openai_tools([_tool(schema={"type": "string"})])
    assert tools[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_parse_arguments_empty_returns_empty_object():
    assert parse_arguments("") == {}
    assert parse_arguments("   ") == {}


def test_parse_arguments_valid_json_object():
    assert parse_arguments('{"path": "notes"}') == {"path": "notes"}


def test_parse_arguments_rejects_bad_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_arguments("{oops")


def test_parse_arguments_rejects_non_object():
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_arguments("[1, 2, 3]")


@staticmethod
def _chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


@staticmethod
def _tool_call(index, id, name_parts, args_parts):
    return SimpleNamespace(
        index=index,
        id=id,
        function=SimpleNamespace(
            name=name_parts,
            arguments=args_parts,
        ),
    )


def _stream_events(chunks):
    ollama = OllamaClient("http://localhost:11434/v1", "test-model")
    ollama._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda *args, **kwargs: _fake_create(chunks)
            )
        )
    )

    async def _collect():
        result = []
        async for event in ollama.stream_chat(
            [{"role": "user", "content": "hi"}], tools=None
        ):
            result.append(event)
        return result

    return asyncio.run(_collect())


async def _fake_create(chunks):
    async def gen():
        for chunk in chunks:
            yield chunk

    return gen()


def test_stream_chat_emits_deltas_then_message():
    events = _stream_events([_chunk(content="Hel"), _chunk(content="lo")])
    assert [e for e in events if e["type"] == "delta"] == [
        {"type": "delta", "content": "Hel"},
        {"type": "delta", "content": "lo"},
    ]
    message = events[-1]
    assert message["type"] == "message"
    assert message["message"] == {"role": "assistant", "content": "Hello"}


def test_stream_chat_assembles_split_tool_calls():
    events = _stream_events(
        [
            _chunk(tool_calls=[_tool_call(0, "call_1", "list_", '{"path":')]),
            _chunk(tool_calls=[_tool_call(0, "", "files", ' ""}')]),
        ]
    )
    message = events[-1]
    assert message["type"] == "message"
    tool_call = message["message"]["tool_calls"][0]
    assert tool_call == {
        "id": "call_1",
        "type": "function",
        "function": {"name": "list_files", "arguments": '{"path": ""}'},
    }