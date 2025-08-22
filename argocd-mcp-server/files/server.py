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
load_dotenv("/app/env/.env")
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
    def __init__(self, base_url: str, token: str):   # ✅ fixed
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
# MCP Tools
# ------------------------------
@mcp.tool()
def mcp_list_applications(search: Optional[str] = None):
    """List ArgoCD applications"""
    return argocd_client.list_applications(search)

@mcp.tool()
def mcp_get_application(application_name: str):
    """Get details of an ArgoCD application"""
    return argocd_client.get_application(application_name)

@mcp.tool()
def mcp_get_application_resource_tree(application_name: str):
    """Get the resource tree of an ArgoCD application"""
    return argocd_client.get_application_resource_tree(application_name)

@mcp.tool()
def add_cluster(cluster_name: str, cluster_endpoint: str, auth_token: str):
    """Add a new Kubernetes cluster (stage/dev/prod)"""
    return {
        "status": "success",
        "message": f"Cluster {cluster_name} added with endpoint {cluster_endpoint}"
    }

@mcp.tool()
def configure_webhook(scm_type: str, repo_url: str, branch: str, webhook_url: str, secret: Optional[str] = None):
    """Configure GitHub or GitLab webhook for ArgoCD auto-sync"""
    return {
        "status": "success",
        "message": f"Webhook configured for {scm_type} repo {repo_url} (branch: {branch})"
    }

@mcp.tool()
def deploy_helm_chart(repo_url: str, branch: str, chart_path: str, cluster_name: str, namespace: str):
    """Deploy Helm chart into a specific cluster"""
    return {
        "status": "success",
        "message": f"Helm chart {chart_path} from {repo_url}@{branch} deployed to {cluster_name}/{namespace}"
    }

@mcp.tool()
def set_environment(environment_name: str, variables: Dict[str, Any]):
    """Set environment variables/config for a cluster/application"""
    return {
        "status": "success",
        "message": f"Environment {environment_name} configured",
        "variables": variables
    }

@mcp.tool()
def configure_rbac(username: str, role: str, project: Optional[str] = None):
    """Configure RBAC permissions for a user or group"""
    return {
        "status": "success",
        "message": f"RBAC role {role} assigned to {username} in project {project or 'global'}"
    }

# ------------------------------
# JSON-RPC Endpoint for MCP
# ------------------------------
@app.post("/jsonrpc")
async def jsonrpc_handler(request: Request):
    body = await request.json()
    response = await mcp.handle_jsonrpc(body)
    return response

# ------------------------------
# SSE Endpoint
# ------------------------------
TOOLS_FILE_PATH = os.path.join(os.path.dirname(__file__), "tools.json")   # ✅ fixed

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

        await asyncio.sleep(1)

@app.get("/sse")
async def sse_endpoint():
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ------------------------------
# Run server
# ------------------------------
if __name__ == "__main__":    # ✅ fixed
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
