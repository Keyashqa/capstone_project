import os

from daedalus_toolsmith.models.toolsmith.golden_set import GoldenSetStore

BASE_DIR = os.path.dirname(__file__)
GOLDEN_SET_PATH = os.path.join(BASE_DIR, "data", "golden_tests.json")

golden_set_store = GoldenSetStore(path=GOLDEN_SET_PATH)

from typing import Any, Dict, List
from types import FunctionType

from daedalus_toolsmith.models.toolsmith.models import tool_design_from_dict


def run_tool_tests(
        tool_design: Dict[str, Any],
        tool_code: str,
        test_suite: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministically execute a generated tool implementation against a test suite.

    Args:
        tool_design: JSON-like dict describing the tool (as produced by ToolPlanner).
        tool_code:   Full Python source code string with a single function definition.
        test_suite:  JSON-like dict with a "test_cases" list, each containing:
                     - name: str
                     - description: str
                     - input_args: dict
                     - expected_keys: list[str]
                     - expected_contains: Optional[str]

    Returns:
        {
          "status": "success" | "error",
          "all_passed": bool,
          "num_tests": int,
          "results": [
            {
              "name": str,
              "passed": bool,
              "error_message": Optional[str],
              "details": Optional[str],
            },
            ...
          ],
          "error_message": Optional[str]  # only when status == "error"
        }
    """
    results: List[Dict[str, Any]] = []

    # 0) Parse tool design
    try:
        design = tool_design_from_dict(tool_design)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "all_passed": False,
            "num_tests": 0,
            "results": [],
            "error_message": f"Failed to parse tool design: {exc}",
        }

    tool_name = design.name  # <-- FIX: use correct field

    # 1) Exec the code in a dedicated namespace
    namespace: Dict[str, Any] = {}
    try:
        exec(tool_code, namespace)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "all_passed": False,
            "num_tests": 0,
            "results": [],
            "error_message": f"Error executing generated code: {exc}",
        }

    func = namespace.get(tool_name)
    if not isinstance(func, FunctionType):
        return {
            "status": "error",
            "all_passed": False,
            "num_tests": 0,
            "results": [],
            "error_message": (
                f"Function '{tool_name}' not found in generated code. "
                f"Available callables: "
                f"{[k for k, v in namespace.items() if isinstance(v, FunctionType)]}"
            ),
        }

    # 2) Combine fresh + golden tests
    fresh_suite = test_suite or {}
    combined_suite = build_combined_test_suite(tool_name=tool_name, fresh_suite=fresh_suite)
    test_cases = combined_suite.get("test_cases", []) or []

    all_passed = True

    for case in test_cases:
        name = case.get("name", "unnamed_test")
        input_args: Dict[str, Any] = case.get("input_args", {}) or {}
        expected_keys: List[str] = case.get("expected_keys", []) or []
        expected_contains = case.get("expected_contains")

        passed = True
        error_message = None
        details = None

        try:
            output = func(**input_args)
        except Exception as exc:  # noqa: BLE001
            passed = False
            all_passed = False
            error_message = f"Exception during tool call: {exc}"
            results.append(
                {
                    "name": name,
                    "passed": passed,
                    "error_message": error_message,
                    "details": None,
                }
            )
            continue

        # Basic shape check
        if not isinstance(output, dict):
            passed = False
            all_passed = False
            error_message = (
                f"Tool returned {type(output).__name__}, expected dict."
            )
        else:
            # Check required keys
            missing = [k for k in expected_keys if k not in output]
            if missing:
                passed = False
                all_passed = False
                error_message = f"Missing expected keys: {missing}"

            # Check substring expectation (if provided)
            if expected_contains is not None:
                as_text = str(output)
                if expected_contains not in as_text:
                    passed = False
                    all_passed = False
                    extra = (
                        f"Expected substring '{expected_contains}' "
                        f"not found in output."
                    )
                    error_message = (
                        f"{error_message} | {extra}"
                        if error_message
                        else extra
                    )

        results.append(
            {
                "name": name,
                "passed": passed,
                "error_message": error_message,
                "details": details,
            }
        )

    # 3) Persist fresh tests into golden set only if everything passed
    if all_passed:
        fresh_cases = fresh_suite.get("test_cases", []) or []
        if fresh_cases:
            try:
                golden_set_store.add_suite(
                    tool_name=tool_name,
                    description=fresh_suite.get(
                        "description",
                        "Generated by ToolGym after successful run",
                    ),
                    test_cases=fresh_cases,
                    source="toolgym",
                )
            except Exception as exc:  # noqa: BLE001
                # Persistence failure should not mark tests as failed,
                # just add diagnostic info.
                results.append(
                    {
                        "name": "__golden_set_persist__",
                        "passed": False,
                        "error_message": (
                            f"Tests passed but failed to persist golden set: {exc}"
                        ),
                        "details": None,
                    }
                )

    return {
        "status": "success",
        "all_passed": all_passed,
        "num_tests": len(test_cases),
        "results": results,
    }


def save_golden_tests(state: dict) -> None:
    status = state.get("tool_validation_status")
    if status != "ok":
        # Do not save anything if ToolGym never went green
        return

    tool_design = state.get("tool_design") or {}
    tool_test_suite = state.get("tool_test_suite") or {}

    tool_name = tool_design.get("tool_name") or tool_test_suite.get("tool_name")
    if not tool_name:
        return

    description = tool_test_suite.get("description", "Design-based tests")
    test_cases = tool_test_suite.get("test_cases", [])

    if not test_cases:
        return

    golden_set_store.add_suite(
        tool_name=tool_name,
        description=description,
        test_cases=test_cases,
        source="design",
    )


def load_golden_test_cases(tool_name: str) -> Dict[str, Any]:
    """
    Tool: returns all persisted golden test cases for a given tool.

    This is meant to be called by the ToolTestPlannerAgent so it can
    see what tests already exist and avoid generating duplicates.
    """
    cases = golden_set_store.get_flat_test_cases(tool_name)
    return {
        "tool_name": tool_name,
        "golden_test_cases": cases,
    }


def build_combined_test_suite(
        tool_name: str,
        fresh_suite: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge fresh LLM-generated tests with all persisted golden tests."""
    fresh_cases: List[Dict[str, Any]] = fresh_suite.get("test_cases", [])
    golden_cases: List[Dict[str, Any]] = golden_set_store.get_flat_test_cases(tool_name)

    return {
        "tool_name": tool_name,
        "description": fresh_suite.get("description", "Combined design + golden tests"),
        "test_cases": [*fresh_cases, *golden_cases],
    }
