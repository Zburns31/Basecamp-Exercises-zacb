#!/usr/bin/env python3
"""
Developer Platform — Support Ticket Agent
Complete implementation with all blanks filled in.
Run with: python run_agent.py
"""

import json
import os
import sys
import pathlib
import anthropic

# ── Configuration ──
def _resolve_env_file():
    """Find .env file in repo root or create one."""
    here = pathlib.Path.cwd().resolve()
    for d in [here, *here.parents]:
        if (d / ".env").is_file():
            return d / ".env"
    root = next((d for d in [here, *here.parents]
                 if (d / "SETUP.md").exists() or (d / ".git").exists()), here)
    return root / ".env"

_env_file = _resolve_env_file()
if not _env_file.exists():
    template = (
        "ANTHROPIC_API_KEY=paste-your-key-here\n"
        "# AWS_BEARER_TOKEN_BEDROCK=paste-your-bedrock-api-key-here\n"
        "# AWS_REGION=us-east-1\n"
    )
    _env_file.write_text(template)
    print(f"Created {_env_file.name} — paste your API key and re-run")
    sys.exit(1)

# Parse .env
_file = {}
for _line in (_env_file.read_text().splitlines() if _env_file.exists() else []):
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        _file[_k.strip()] = _v.strip().strip('"').strip("'")
for _k, _v in _file.items():
    os.environ.setdefault(_k, _v)

# Determine provider
_anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
_bedrock_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()
_bedrock_region = os.environ.get("AWS_REGION", "").strip()

if _anthropic_key.startswith("sk-ant-"):
    PROVIDER = "anthropic"
    client = anthropic.Anthropic(api_key=_anthropic_key, timeout=600.0)
    MODEL = "claude-sonnet-5"
elif _bedrock_token:
    PROVIDER = "bedrock"
    from anthropic import AnthropicBedrockMantle
    client = AnthropicBedrockMantle(aws_region=_bedrock_region, timeout=600.0)
    MODEL = "anthropic.claude-sonnet-5"
else:
    print("❌ No API credentials found. Check .env file.")
    sys.exit(1)

print(f"✓ Connected to Claude via {PROVIDER} ({MODEL})\n")

# ── Mock Data & Tools ──
TICKETS = {
    "TKT-1042": {
        "id": "TKT-1042", "customer": "Acme Corp", "priority": "high",
        "product_area": "billing",
        "description": "We were charged twice for our March invoice. Invoice #INV-2024-0342 shows $4,500 but our bank shows two identical charges on March 3rd. Need immediate refund of the duplicate charge.",
        "status": "open"
    },
    "TKT-1043": {
        "id": "TKT-1043", "customer": "DataFlow Inc", "priority": "medium",
        "product_area": "api",
        "description": "Our webhook endpoint stopped receiving events after we rotated API keys yesterday. We've verified the new key works for REST calls but webhooks are still failing. Getting 401 errors in the webhook logs.",
        "status": "open"
    },
    "TKT-1044": {
        "id": "TKT-1044", "customer": "CloudScale Ltd", "priority": "low",
        "product_area": "feature_request",
        "description": "Would love to see bulk export functionality in the dashboard. Currently we have to export reports one at a time which is painful when we need quarterly summaries across 50+ projects.",
        "status": "open"
    },
    "TKT-1045": {
        "id": "TKT-1045", "customer": "SecureNet Systems", "priority": "critical",
        "product_area": "account",
        "description": "Our admin account (admin@securenet.io) is locked out after failed MFA attempts. We have 47 team members who can't access the platform because SSO is tied to this admin account. This is blocking all work.",
        "status": "open"
    },
    "TKT-1046": {
        "id": "TKT-1046", "customer": "MedTech Solutions", "priority": "high",
        "product_area": "api",
        "description": "Our production integration started returning intermittent 500 errors around 2am last night. About 15% of API calls are failing. We haven't changed anything on our end. Errors seem random - sometimes the same request works on retry. Our team in Singapore is blocked and we need this resolved ASAP.",
        "status": "open"
    },
}

KB_ARTICLES = {
    "KB-001": {"title": "Processing Duplicate Payment Refunds", "content": "For duplicate charges: 1) Verify the duplicate in the billing system, 2) Issue refund through the payment processor (takes 3-5 business days), 3) Send confirmation email with refund reference number. Escalate if amount exceeds $10,000."},
    "KB-002": {"title": "Webhook Authentication After Key Rotation", "content": "When API keys are rotated, webhook signing secrets must also be updated. Go to Settings > Webhooks > Edit endpoint, and regenerate the signing secret. The old secret is invalidated immediately on key rotation. Common mistake: rotating the API key but not the webhook signing secret."},
    "KB-003": {"title": "Bulk Export Feature (Roadmap)", "content": "Bulk export is on the Q3 roadmap. Workaround: Use the REST API's /reports/export endpoint with date range parameters to programmatically export multiple reports. See API docs for batch export examples."},
    "KB-004": {"title": "Admin Account Lockout Recovery", "content": "For locked admin accounts: 1) Verify identity through the secondary email on file, 2) Reset MFA through the admin recovery flow at /admin/recover, 3) Temporary access can be granted through support-level override (requires manager approval). Critical: If SSO is blocked, enable the bypass login at /login/direct for affected users."},
    "KB-005": {"title": "API Rate Limiting Best Practices", "content": "Default rate limits: 100 requests/minute for standard plans, 1000/minute for enterprise. Use exponential backoff with jitter for retries. Monitor usage via the X-RateLimit headers in responses."},
    "KB-006": {"title": "Invoice Discrepancy Resolution", "content": "For billing discrepancies: Check the billing audit log for the account, compare with payment processor records, and verify no pending transactions. Contact finance team for adjustments over $5,000."},
    "KB-007": {"title": "Intermittent 500 Errors Troubleshooting", "content": "For intermittent server errors: 1) Check the status page for known outages, 2) Review rate limit headers - 429s can masquerade as 500s behind load balancers, 3) Check if errors correlate with payload size or specific endpoints, 4) Enable request ID logging and contact support with specific request IDs for investigation. If >10% error rate persists for >1 hour, escalate to engineering."},
}

def get_ticket(ticket_id: str) -> str:
    ticket = TICKETS.get(ticket_id)
    return json.dumps(ticket) if ticket else json.dumps({"error": f"Ticket {ticket_id} not found"})

def search_kb(query: str) -> str:
    query_lower = query.lower()
    results = []
    for article_id, article in KB_ARTICLES.items():
        if any(word in article["title"].lower() or word in article["content"].lower()
               for word in query_lower.split() if len(word) > 2):
            results.append({"id": article_id, **article})
    if not results:
        results = [{"id": "KB-000", "title": "No matches found", "content": "No relevant articles found."}]
    return json.dumps(results[:3])

def resolve_ticket(ticket_id: str, resolution: str, status: str = "resolved") -> str:
    ticket = TICKETS.get(ticket_id)
    if ticket:
        ticket["status"] = status
        ticket["resolution"] = resolution
        return json.dumps({"success": True, "ticket_id": ticket_id, "new_status": status})
    return json.dumps({"error": f"Ticket {ticket_id} not found"})

TOOL_FUNCTIONS = {"get_ticket": get_ticket, "search_kb": search_kb, "resolve_ticket": resolve_ticket}

def execute_tool(name: str, input_data: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    return func(**input_data) if func else json.dumps({"error": f"Unknown tool: {name}"})

# ── Tool Schemas (FILLED IN) ──
tools = [
    {
        "name": "get_ticket",
        "description": "Retrieve full details for a support ticket by its ID, including customer, priority, product area, and description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket ID, e.g. TKT-1042"}
            },
            "required": ["ticket_id"]
        }
    },
    # FILLED IN: search_kb
    {
        "name": "search_kb",
        "description": "Search the knowledge base for articles related to a support issue. Use this to find solutions, procedures, workarounds, and escalation criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms or keywords related to the issue (e.g., 'duplicate charge', 'webhook auth', 'account lockout')"}
            },
            "required": ["query"]
        }
    },
    # FILLED IN: resolve_ticket
    {
        "name": "resolve_ticket",
        "description": "Resolve a support ticket by providing the resolution steps and setting the final status. Use this after gathering all information and determining the solution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket ID"},
                "resolution": {"type": "string", "description": "Detailed resolution steps and guidance for the customer"},
                "status": {"type": "string", "enum": ["resolved", "escalated", "pending_customer"], "description": "Final status of the ticket"}
            },
            "required": ["ticket_id", "resolution", "status"]
        }
    }
]

SYSTEM_PROMPT = """You are a Tier 1 support agent for TechFlow, a B2B SaaS platform.

Your process:
1. ALWAYS look up the ticket first to understand the full context
2. Search the knowledge base for relevant solutions
3. Resolve the ticket with specific, actionable guidance

Guidelines:
- Be thorough: always search the KB before resolving
- Be specific: include exact steps, links, and timeframes
- Escalate when needed: if confidence is low or issue needs engineering
- Categorize accurately: billing, technical, account, or feature_request

Escalation Criteria:
- Financial issues over $10,000
- Security-related account compromises
- Issues requiring engineering intervention
- Ambiguous or complex technical issues"""

RESOLUTION_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "diagnosis": {"type": "string", "description": "Root cause analysis of the issue"},
            "solution_steps": {"type": "array", "items": {"type": "string"}, "description": "Ordered steps to resolve"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "escalation_needed": {"type": "boolean"},
            "category": {"type": "string", "enum": ["billing", "technical", "account", "feature_request"]}
        },
        "required": ["diagnosis", "solution_steps", "confidence", "escalation_needed", "category"],
        "additionalProperties": False
    }
}

def get_structured_result(response) -> dict:
    """Extract structured JSON from the last text block."""
    text_blocks = [b for b in response.content if hasattr(b, 'type') and b.type == "text" and hasattr(b, 'text') and b.text.strip()]
    if text_blocks:
        try:
            return json.loads(text_blocks[-1].text)
        except json.JSONDecodeError:
            return None
    return None

# ── FILLED IN: run_agent() ──
def run_agent(user_message: str):
    """Run the support ticket agent."""
    messages = [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        tools=tools,
        thinking={"type": "adaptive"},
        messages=messages
    )

    # Loop while Claude wants to call tools
    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result)
                })

        # Append assistant response + tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Call API again
        response = client.messages.create(
            model=MODEL,
            max_tokens=32000,
            system=SYSTEM_PROMPT,
            tools=tools,
            thinking={"type": "adaptive"},
            messages=messages
        )

    return response

# ── FILLED IN: run_agent_structured() ──
def run_agent_structured(user_message: str) -> dict:
    """Run the agent with structured JSON output."""
    # Step 1: Run the tool loop (NO output_config)
    messages = [{"role": "user", "content": user_message}]
    response = client.messages.create(
        model=MODEL, max_tokens=32000, system=SYSTEM_PROMPT,
        tools=tools, thinking={"type": "adaptive"}, messages=messages
    )

    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(
            model=MODEL, max_tokens=32000, system=SYSTEM_PROMPT,
            tools=tools, thinking={"type": "adaptive"}, messages=messages
        )

    # Step 2: Final call with structured output
    messages.append({"role": "user", "content": "Provide your structured resolution as JSON."})
    final = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        output_config={"format": RESOLUTION_SCHEMA},
        tool_choice={"type": "none"},
        thinking={"type": "adaptive"},
        messages=messages
    )
    return get_structured_result(final)

# ── FILLED IN: run_agent_thinking() ──
def run_agent_thinking(user_message: str, effort: str = "high") -> dict:
    """Run agent with effort-controlled adaptive thinking."""
    messages = [{"role": "user", "content": user_message}]
    response = client.messages.create(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        tools=tools,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=messages
    )

    # Tool loop with thinking display
    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if hasattr(block, 'type'):
                if block.type == "thinking" and hasattr(block, 'thinking'):
                    print(f"[thinking] {block.thinking[:200]}...")
                elif block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=MODEL,
            max_tokens=32000,
            system=SYSTEM_PROMPT,
            tools=tools,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            messages=messages
        )

    # Final call with structured output
    messages.append({"role": "user", "content": "Provide your structured resolution as JSON."})
    final = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        output_config={"effort": effort, "format": RESOLUTION_SCHEMA},
        tool_choice={"type": "none"},
        thinking={"type": "adaptive"},
        messages=messages
    )
    return get_structured_result(final)

# ── Demo ──
if __name__ == "__main__":
    print("=" * 70)
    print("DEVELOPER PLATFORM — SUPPORT TICKET AGENT")
    print("=" * 70)

    # Test 1: Basic agent
    print("\n[1] Running basic agent on TKT-1042 (duplicate charge)...")
    response = run_agent("Resolve ticket TKT-1042")
    for block in response.content:
        if hasattr(block, 'type') and block.type == "text" and hasattr(block, 'text'):
            print(f"✓ Response:\n{block.text[:500]}...\n")
            break

    # Test 2: Structured output
    print("[2] Running with structured output on TKT-1044 (feature request)...")
    result = run_agent_structured("Resolve ticket TKT-1044")
    if result:
        print(f"✓ Category: {result.get('category')}")
        print(f"  Confidence: {result.get('confidence')}")
        print(f"  Escalate: {result.get('escalation_needed')}")
        print(f"  Steps: {len(result.get('solution_steps', []))}\n")

    # Test 3: Thinking with effort
    print("[3] Running with high-effort thinking on TKT-1046 (ambiguous API errors)...")
    result = run_agent_thinking("Resolve ticket TKT-1046", effort="high")
    if result:
        print(f"✓ Category: {result.get('category')}")
        print(f"  Confidence: {result.get('confidence')}")
        print(f"  Escalate: {result.get('escalation_needed')}")
        print(f"  Full resolution:\n{json.dumps(result, indent=2)}\n")

    print("=" * 70)
    print("✓ All tests complete!")
