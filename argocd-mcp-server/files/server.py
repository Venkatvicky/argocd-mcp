from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
import os
import json
import requests
import urllib3
import asyncio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ------------------------------
# Load environment variables
# ------------------------------
BASE_DIR = os.path.dirname(_file_)
ENV_PATH = os.path.join(BASE_DIR, "env", ".env")

load_dotenv(ENV_PATH)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ARGOCD_BASE_URL = os.getenv("ARGOCD_BASE_URL")
ARGOCD_API_TOKEN = os.getenv("ARGOCD_API_TOKEN")

if not ARGOCD_BASE_URL or not ARGOCD_API_TOKEN:
    raise ValueError("❌ Missing ARGOCD_BASE_URL or ARGOCD_API_TOKEN in .env file")

# ------------------------------
# FastAPI App + MCP instance
# ------------------------------
app = FastAPI()
mcp = FastMCP("ArgoCD MCP Server")

# ------------------------------
# ArgoCD Client
# ------------------------------
class ArgoCDClient:
    def _init_(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def list_applications(self, search: Optional[str] = None):
        params = {"search": search} if search else {}
        resp = requests.get(
            f"{self.base_url}/api/v1/applications",
            headers=self.headers,
            params=params,
            verify=False
        )
        resp.raise_for_status()
        return resp.json()

    def get_application(self, name: str):
        resp = requests.get(
            f"{self.base_url}/api/v1/applications/{name}",
            headers=self.headers,
            verify=False
        )
        resp.raise_for_status()
        return resp.json()

    def get_application_resource_tree(self, name: str):
        resp = requests.get(
            f"{self.base_url}/api/v1/applications/{name}/resource-tree",
            headers=self.headers,
            verify=False
        )
        resp.raise_for_status()
        return resp.json()

# ------------------------------
# Initialize ArgoCD Client
# ------------------------------
argocd_client = ArgoCDClient(ARGOCD_BASE_URL, ARGOCD_API_TOKEN)

# ------------------------------
# MCP Tools (manual definitions)
# ------------------------------
@mcp.tool(name="list_applications")
def list_applications(search: Optional[str] = None):
    return argocd_client.list_applications(search)

@mcp.tool(name="get_application")
def get_application(application_name: str):
    return argocd_client.get_application(application_name)

@mcp.tool(name="get_application_resource_tree")
def get_application_resource_tree(application_name: str):
    return argocd_client.get_application_resource_tree(application_name)

# Example stub tool
@mcp.tool(name="sync_application")
def sync_application(application_name: str):
    return {"status": "todo", "message": f"Sync {application_name} not implemented yet"}

# ------------------------------
# Load tools.json dynamically (fixed version)
# ------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(_file_))   # absolute dir of server.py
TOOLS_FILE_PATH = os.path.join(BASE_DIR, "tools.json")  # tools.json in same folder

print(f"🔎 Looking for tools.json at: {TOOLS_FILE_PATH}")

if os.path.exists(TOOLS_FILE_PATH):
    try:
        with open(TOOLS_FILE_PATH, "r") as f:
            tools_config = json.load(f)

        for tool in tools_config.get("tools", []):
            tool_name = tool.get("name")

            if tool_name:
                def make_tool(name):
                    @mcp.tool(name=name)
                    def generic_tool(**kwargs):
                        return {
                            "status": "todo",
                            "message": f"Tool '{name}' is defined in tools.json but not implemented in server.py",
                            "params": kwargs
                        }
                    return generic_tool

                make_tool(tool_name)

        print(f"✅ Loaded {len(tools_config.get('tools', []))} tools from tools.json")
    except Exception as e:
        print(f"❌ Failed to load tools.json: {e}")
else:
    print(f"⚠ tools.json not found at {TOOLS_FILE_PATH}")

# ------------------------------
# JSON-RPC Endpoint for MCP
# ------------------------------
@app.post("/jsonrpc")
async def jsonrpc_handler(request: Request):
    raw_body = await request.body()
    print("🔍 Incoming /jsonrpc request:", raw_body.decode())

    if not raw_body.strip():
        return {"error": "Empty request body"}

    try:
        body = await request.json()
    except Exception as e:
        return {"error": f"Invalid JSON: {str(e)}"}

    try:
        # ✅ Correct call
        response = await mcp.handle_jsonrpc(body)
        return response
    except Exception as e:
        print(f"❌ MCP error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32000, "message": str(e)},
        }

# ------------------------------
# SSE Endpoint (streams tools.json)
# ------------------------------
async def event_generator():
    while True:
        try:
            with open(TOOLS_FILE_PATH, "r") as f:
                tools_event = json.load(f)

            jsonrpc_msg = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": tools_event
            }
            yield f"data: {json.dumps(jsonrpc_msg)}\n\n"
        except Exception as e:
            error_msg = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_msg)}\n\n"

        await asyncio.sleep(2)

@app.get("/sse")
async def sse_endpoint():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
# ------------------------------
# Health Check
# ------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "tools_json": TOOLS_FILE_PATH,
        "tools_json_exists": os.path.exists(TOOLS_FILE_PATH)
    }
# ------------------------------
# Run server
# ------------------------------
if _name_ == "_main_":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
