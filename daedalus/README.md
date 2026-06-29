# **Daedalus Toolsmith**

*A self-expanding agent system built with Google ADK & Gemini*

Daedalus Toolsmith is an agentic framework that can **design, implement, test, and register new Python function tools
and multi-agent pipelines** entirely through LLM-driven workflows. It combines structured agent pipelines, ForgeAgent
patterns, a persistent Golden Set for regression testing, and an orchestrator that never answers directly but always
delegates to tools and pipelines.

This repository contains the full implementation of Daedalus, including the orchestrator agent, ToolsmithPipeline,
AgentSmithPipeline, ToolGym testing framework, dynamic registries, and supporting models and utilities.

---

## 🚀 **Core Idea**

Most agents today are static: they can only use capabilities that developers manually wrote. Daedalus removes that
bottleneck.

When the system receives a request:

* If an existing **tool** or **pipeline** can handle it -> Daedalus uses it.
* If not -> Daedalus **creates a new tool or a new multi-agent pipeline** automatically.

Daedalus evolves over time, expanding its registry of validated tools and workflows.

---

## ⚙️ **Features**

### 🔧 **Dynamic Python Tool Creation (ToolsmithPipeline)**

Daedalus can autonomously:

1. Plan a tool specification
2. Generate Python code
3. Create test cases
4. Run those tests in a deterministic ToolGym environment
5. Repair code if needed
6. Register the passing tool for future use
7. Add passing tests to a persistent Golden Set

### 🧠 **Dynamic Pipeline Creation (AgentSmithPipeline)**

Daedalus can also create LLM-only multi-agent pipelines:

* Sequential workflows
* Iterative refinement loops
* Parallel gather pipelines
* Generator–critic patterns

Pipelines are validated, registered, and become callable like built-in tools.

### 🧩 **Orchestrator Agent**

The orchestrator:

* Never answers directly
* Inspects available tools and pipelines
* Chooses the correct execution path
* Invokes ToolsmithPipeline or AgentSmithPipeline when new capabilities are needed

### 🧪 **ToolGym + Golden Set**

Every generated tool is evaluated in a controlled environment:

* Deterministic execution
* Structured test cases
* Automated regression storage
* Continuous expansion of validation data

### 🏗️ **In-Memory Registries**

* `InMemoryToolRegistry` - stores Python function tools
* `InMemoryAgentRegistry` - stores multi-agent pipelines

Both persist across the orchestrator’s lifetime.

---

Here is the updated **Run section**, rewritten cleanly with **Docker instructions added**, without rewriting the rest of
the README:

## ▶️ Running Daedalus

### **Option 1 — Run Locally**

#### 1. Install dependencies

```bash
pip install -r requirements.txt
````

#### 2. Configure environment

Create a `.env` file:

```
GOOGLE_API_KEY=your_key_here
```

#### 3. Start the application

```bash
python main.py
```

---

## 🐳 **Option 2 — Run with Docker**

### 1. Build the Docker image

```bash
docker build -t daedalus-toolsmith .
```

### 2. Run the container

```bash
docker run -p 8000:8000 --env-file .env daedalus-toolsmith
```

This starts the FastAPI + ADK application inside a container, exposing it on `http://localhost:8000`.

---

## ▶️ Running ADK web

To interact with Daedalus via a web interface, start the ADK web server:

```bash
adk web
```

Then navigate to `http://localhost:8000` in your browser.

## 🧪 **Running Tests**

### Integration + evalset tests:

```bash
pytest tests/
```

This uses Google ADK’s evaluation engine to validate tool and pipeline execution.

---

## 🎨 **Assets**

Uploaded images were generated using **Gemini AI Image Generator**.
The demo video was created using **Google AI Studio TTS** and **Adobe Free Animation Maker**.

---

## 💡 **Roadmap / Future Improvements**

* Automatic updates for already-registered tools and pipelines
* Improved use of registry tools inside generated pipelines
* Persistent storage (SQLite / Firestore) for tools, pipelines, and golden tests
* Static analysis + sandboxing for generated code
* Dashboard for ToolGym runs and pipeline introspection

---

## 🙌 **Acknowledgments**

Built using:

* **Google Agent Development Kit (ADK)**
* **Google Gemini** (reasoning, code generation, evaluation)
* **FastAPI** as the runtime interface

Special thanks to the Google Agentic AI Intensive Course instructors and community.
