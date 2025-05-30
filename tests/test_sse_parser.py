import asyncio
import pytest
from tests.test_api import SSEMessageParser, AsyncSSEMessageParser


def test_sse_message_parser_multi_message():
    lines = iter([
        "data: foo",
        "",
        "data: bar",
        "data: baz",
        "",
    ])
    parser = SSEMessageParser(lines)
    assert next(parser) == "foo"
    assert next(parser) == "bar\nbaz"
    with pytest.raises(StopIteration):
        next(parser)


@pytest.mark.asyncio
async def test_async_sse_message_parser_multi_message():
    async def line_gen():
        for line in ["data: foo", "", "data: bar", "", ""]:
            yield line
    parser = AsyncSSEMessageParser(line_gen())
    messages = []
    async for msg in parser:
        messages.append(msg)
    assert messages == ["foo", "bar"]
