import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(dotenv_path="google_workspace_mcp/.env")

server_params = StdioServerParameters(
    command="uv",
    args=["run", "workspace-mcp", "--transport", "stdio"],
    cwd="google_workspace_mcp",
    env={
        "GOOGLE_OAUTH_CLIENT_ID": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "GOOGLE_OAUTH_CLIENT_SECRET": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "WORKSPACE_MCP_ENABLED_TOOLS": os.environ.get("WORKSPACE_MCP_ENABLED_TOOLS", "docs,drive"),
        "MCP_SINGLE_USER_MODE": os.environ.get("MCP_SINGLE_USER_MODE", "true"),
        "USER_GOOGLE_EMAIL": os.environ.get("USER_GOOGLE_EMAIL", ""),
        "PATH": os.environ["PATH"],
    },
)

import re

def extract_auth_url(text):
    match = re.search(r'https://accounts\.google\.com/o/oauth2/auth\S+', text)
    return match.group(0) if match else None

async def call_with_auth_retry(session, tool_name, arguments):
    while True:
        result = await session.call_tool(tool_name, arguments=arguments)
        text = ""
        for block in result.content:
            text += getattr(block, "text", "")
        auth_url = extract_auth_url(text)
        if auth_url:
            print("\n*** AUTHENTICATION REQUIRED ***")
            print(f"\nOpen this URL in your browser:\n\n{auth_url}\n")
            input("After you approve access in the browser and see a success page, press Enter here to retry... ")
        else:
            return result

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            DOC_TITLE = "hh"
            TAB_TITLE = "scripts"
            TAB_CONTENT = "This is a hardcoded sentence inside the scripts tab."

            # Step 1: create the doc
            print(f"Creating doc '{DOC_TITLE}'...")
            create_result = await call_with_auth_retry(
                session,
                "create_doc",
                arguments={"title": DOC_TITLE}
            )
            print("\n=== create_doc RAW RESULT ===")
            for block in create_result.content:
                print(getattr(block, "text", block))
            print("==============================\n")

            # Extract document_id from result
            doc_id = None
            for block in create_result.content:
                text = getattr(block, "text", "")
                for pattern in [
                    r'["\'](?:documentId|document_id)["\']\s*[:=]\s*["\']([a-zA-Z0-9_-]+)["\']',
                    r'\(ID:\s*([a-zA-Z0-9_-]+)\)',
                    r'/document/d/([a-zA-Z0-9_-]+)',
                ]:
                    match = re.search(pattern, text)
                    if match:
                        doc_id = match.group(1)
                        break
                if doc_id:
                    break

            if not doc_id:
                print("Could not extract doc_id — check raw output above.")
                return
            print(f"doc_id: {doc_id}")

            # Step 2: create a new tab
            print(f"\nCreating tab '{TAB_TITLE}'...")
            tab_result = await call_with_auth_retry(
                session,
                "manage_doc_tab",
                arguments={
                    "document_id": doc_id,
                    "action": "create",
                    "title": TAB_TITLE,
                    "index": 1,
                }
            )
            print("\n=== manage_doc_tab (create) RAW RESULT ===")
            tab_text = ""
            for block in tab_result.content:
                t = getattr(block, "text", "")
                print(t)
                tab_text += t
            print("==========================================\n")

            # Extract tab_id from result
            tab_id = None
            for pattern in [
                r'["\']tab_id["\']\s*:\s*["\']([a-zA-Z0-9_.\-]+)["\']',
                r'Tab ID:\s*([a-zA-Z0-9_.\-]+)',
            ]:
                match = re.search(pattern, tab_text)
                if match:
                    tab_id = match.group(1).rstrip('.')
                    break
            print(f"tab_id: {tab_id}")

            # Step 3: populate the tab with the hardcoded sentence
            if tab_id:
                print(f"\nPopulating tab '{TAB_TITLE}'...")
                populate_result = await call_with_auth_retry(
                    session,
                    "manage_doc_tab",
                    arguments={
                        "document_id": doc_id,
                        "action": "populate_from_markdown",
                        "tab_id": tab_id,
                        "markdown_text": TAB_CONTENT,
                    }
                )
                print("\n=== manage_doc_tab (populate) RAW RESULT ===")
                for block in populate_result.content:
                    print(getattr(block, "text", block))
                print("============================================\n")
            else:
                print("Could not extract tab_id — skipping populate step.")

            print(f"Done. Check your Google Drive for a doc named '{DOC_TITLE}'.")

asyncio.run(main())