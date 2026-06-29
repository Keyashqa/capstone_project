from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from typing import Any, Dict, List


@dataclass
class GoldenTestSuite:
    tool_name: str
    description: str
    test_cases: List[Dict[str, Any]]
    created_at: str  # ISO string
    source: str  # e.g. "design" | "trajectory"


class GoldenSetStore:
    """
    Very lightweight persistent store for Golden Set test suites.

    - Persists everything into a single JSON file.
    - Keeps an in-memory cache for fast read.
    - On every write, re-serializes the full store to disk.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._by_tool: Dict[str, List[GoldenTestSuite]] = {}
        self._load_from_disk()

    # ------------------------------
    # Persistence
    # ------------------------------
    def _load_from_disk(self) -> None:
        if not os.path.exists(self._path):
            self._by_tool = {}
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self._by_tool = {}
            return

        self._by_tool = {}
        for tool_name, suites_raw in raw.items():
            suites: List[GoldenTestSuite] = []
            for s in suites_raw:
                suites.append(
                    GoldenTestSuite(
                        tool_name=tool_name,
                        description=s.get("description", ""),
                        test_cases=s.get("test_cases", []),
                        created_at=s.get("created_at", datetime.now(UTC).isoformat()),
                        source=s.get("source", "unknown"),
                    )
                )
            self._by_tool[tool_name] = suites

    def _save_to_disk(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

        serializable: Dict[str, List[Dict[str, Any]]] = {}
        for tool_name, suites in self._by_tool.items():
            serializable[tool_name] = [
                asdict(suite) for suite in suites
            ]

        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    # ------------------------------
    # Public API
    # ------------------------------
    def add_suite(self, tool_name: str, description: str, test_cases: List[Dict[str, Any]], source: str) -> None:
        suite = GoldenTestSuite(
            tool_name=tool_name,
            description=description,
            test_cases=test_cases,
            created_at=datetime.now(UTC).isoformat(),
            source=source,
        )
        self._by_tool.setdefault(tool_name, []).append(suite)
        self._save_to_disk()

    def get_all_for_tool(self, tool_name: str) -> List[GoldenTestSuite]:
        return list(self._by_tool.get(tool_name, []))

    def get_flat_test_cases(self, tool_name: str) -> List[Dict[str, Any]]:
        cases: List[Dict[str, Any]] = []
        for suite in self._by_tool.get(tool_name, []):
            cases.extend(suite.test_cases)
        return cases
