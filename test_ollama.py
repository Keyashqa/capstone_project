import time, json, ollama

MODEL = "gemma2:2b"

def timed(label, messages, fmt=None):
    print(f"\n--- {label} ---")
    t0 = time.time()
    resp = ollama.chat(
        model=MODEL,
        messages=messages,
        format=fmt,                       # "json" forces valid JSON output
        options={"temperature": 0.4},
    )
    dt = time.time() - t0
    out = resp["message"]["content"]
    print(out)
    print(f"[latency: {dt:.1f}s]")
    return out, dt

# Test 1 — the specialist's actual work (tweet writing)
timed("TWEET TASK", [
    {"role": "user",
     "content": "Write a single tweet (max 280 chars) announcing that I'm "
                "building an AI agent orchestrator called Marvis. Casual, no hashtags spam."}
])

# Test 2 — intake_task structured parsing (THE risk node)
out, _ = timed("INTAKE → JSON", [
    {"role": "user",
     "content": 'Parse this request into JSON with keys "type", "topic", '
                '"tone", "acceptance_criteria" (a list). Request: '
                '"Hire a content writer to make my twitter post about Marvis launch"'}
], fmt="json")

# Confirm the JSON actually parses — this is what intake reliability hinges on
try:
    parsed = json.loads(out)
    print("\n✅ Valid JSON. Keys:", list(parsed.keys()))
except json.JSONDecodeError as e:
    print("\n❌ JSON parse failed:", e)