#!/usr/bin/env python3
"""One local stdio MCP server; host context/authorization never come from model input.

Requires the separately qualified pinned MCP SDK. No live ad integrations exist.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.state import StateHost
from aurora.tools import CATALOG, HostContext, ToolHost


async def serve(host: ToolHost) -> None:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    server = Server("aurora-local-mock")

    @server.list_tools()
    async def list_tools():
        return [Tool(name=name, description=f"AURORA {name}: source-tagged local mock workflow; missing models return MODEL_NOT_QUALIFIED", inputSchema=arguments.model_json_schema()) for name, arguments in CATALOG.items()]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = host.call(name, arguments)
        return [TextContent(type="text", text=result.model_dump_json())]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--caller", required=True)
    parser.add_argument("--mock-preauthorized", action="store_true", help="Explicit host-side MOCK_ONLY authorization; never a model argument")
    parser.add_argument("--register-s1-models", action="store_true", help="Host-only frozen observed-S1 model registry; no evaluator truth")
    args = parser.parse_args()
    runtime = Path.home() / ".local/share/aurora-ads"
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Runtime ownership mismatch")
    state = StateHost(runtime / "state/tool_host.sqlite")
    state.verify()
    models = None
    artifact = None
    if args.register_s1_models:
        from aurora.policy_registry import load_bundle
        models, _, report = load_bundle(ROOT)
        artifact = report["artifact"]
    host = ToolHost(state, HostContext(args.tenant, args.caller, args.mock_preauthorized), runtime / "runs/tool_artifacts", models=models, model_artifact=artifact)
    asyncio.run(serve(host))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
