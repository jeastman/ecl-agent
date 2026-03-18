from __future__ import annotations

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("FixtureEcho")


@mcp.tool()
def echo_text(text: str) -> str:
    """Return the input text with a fixture prefix."""
    return f"fixture:{text}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
