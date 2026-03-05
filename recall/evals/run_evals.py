"""
Run evaluations against Recall.

Usage:
    python -m recall.evals.run_evals
    python -m recall.evals.run_evals --category basic
    python -m recall.evals.run_evals --verbose
    python -m recall.evals.run_evals --llm-grader
    python -m recall.evals.run_evals --compare-results
    python -m recall.evals.run_evals --output results.json
"""

import argparse
import asyncio
import json
import time
from typing import TypedDict

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text
from sqlalchemy import create_engine, text

from recall.evals.test_cases import CATEGORIES, TEST_CASES, TestCase
from db import db_url


class EvalResult(TypedDict, total=False):
    status: str
    question: str
    category: str
    missing: list[str] | None
    duration: float
    response: str | None
    error: str
    # New fields for enhanced evaluation
    llm_grade: float | None
    llm_reasoning: str | None
    result_match: bool | None
    result_explanation: str | None


console = Console()


def execute_golden_sql(sql: str) -> list[dict]:
    """Execute a golden SQL query and return results as list of dicts."""
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def check_strings_in_response(response: str, expected: list[str]) -> list[str]:
    """Check which expected strings are missing from the response."""
    response_lower = response.lower()
    return [v for v in expected if v.lower() not in response_lower]


async def run_single_test(
    test_case: TestCase,
    semaphore: asyncio.Semaphore,
    verbose: bool,
    llm_grader: bool,
    compare_results: bool,
    timeout: float = 60.0,
) -> EvalResult:
    """Run a single test case with semaphore-controlled concurrency and per-test timeout."""
    from recall.agents import recall

    async with semaphore:
        test_start = time.time()
        try:
            run_coro = recall.arun(test_case.question)
            result = await asyncio.wait_for(run_coro, timeout=timeout)
            # InsightResponse content: if it's an InsightResponse, extract answer
            content = result.content if hasattr(result, 'content') else result
            if hasattr(content, 'answer'):
                response = content.answer
            elif isinstance(content, str):
                response = content
            else:
                response = str(content)
            duration = time.time() - test_start

            eval_result = evaluate_response(
                test_case=test_case,
                response=response,
                llm_grader=llm_grader,
                compare_results=compare_results,
            )

            return {
                "status": eval_result["status"],
                "question": test_case.question,
                "category": test_case.category,
                "missing": eval_result.get("missing"),
                "duration": duration,
                "response": response if verbose else None,
                "llm_grade": eval_result.get("llm_grade"),
                "llm_reasoning": eval_result.get("llm_reasoning"),
                "result_match": eval_result.get("result_match"),
                "result_explanation": eval_result.get("result_explanation"),
            }

        except asyncio.TimeoutError:
            return {
                "status": "ERROR",
                "question": test_case.question,
                "category": test_case.category,
                "missing": None,
                "duration": timeout,
                "error": f"Timed out after {timeout:.0f}s",
                "response": None,
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "question": test_case.question,
                "category": test_case.category,
                "missing": None,
                "duration": time.time() - test_start,
                "error": str(e),
                "response": None,
            }


async def run_evals_async(
    category: str | None = None,
    verbose: bool = False,
    llm_grader: bool = False,
    compare_results: bool = False,
    output: str | None = None,
    concurrency: int = 3,
    timeout: float = 60.0,
) -> list[EvalResult]:
    """Run evaluation suite in parallel using asyncio.gather()."""
    # Filter tests
    tests = TEST_CASES
    if category:
        tests = [tc for tc in tests if tc.category == category]

    if not tests:
        console.print(f"[red]No tests found for category: {category}[/red]")
        return []

    mode_info = []
    if llm_grader:
        mode_info.append("LLM grading")
    if compare_results:
        mode_info.append("Result comparison")
    if not mode_info:
        mode_info.append("String matching")

    console.print(
        Panel(
            f"[bold]Running {len(tests)} tests[/bold] (parallel ×{concurrency}, timeout {timeout:.0f}s)\nMode: {', '.join(mode_info)}",
            style="blue",
        )
    )

    semaphore = asyncio.Semaphore(concurrency)
    start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task_bar = progress.add_task("Evaluating...", total=len(tests))

        async def run_and_advance(tc: TestCase) -> EvalResult:
            r = await run_single_test(tc, semaphore, verbose, llm_grader, compare_results, timeout)
            progress.advance(task_bar)
            return r

        results: list[EvalResult] = await asyncio.gather(
            *[run_and_advance(tc) for tc in tests]
        )

    total_duration = time.time() - start

    display_results(results, verbose, llm_grader, compare_results)
    display_summary(results, total_duration, category)

    if output:
        with open(output, "w") as f:
            json.dump(
                {
                    "meta": {
                        "timestamp": time.time(),
                        "category": category,
                        "total_duration_s": total_duration,
                        "concurrency": concurrency,
                        "timeout_s": timeout,
                    },
                    "results": list(results),
                },
                f,
                indent=2,
                default=str,
            )
        console.print(f"[green]Results written to {output}[/green]")

    return results


def run_evals(
    category: str | None = None,
    verbose: bool = False,
    llm_grader: bool = False,
    compare_results: bool = False,
    output: str | None = None,
):
    """Entry point: runs the async evaluation suite synchronously."""
    return asyncio.run(
        run_evals_async(
            category=category,
            verbose=verbose,
            llm_grader=llm_grader,
            compare_results=compare_results,
            output=output,
        )
    )


def evaluate_response(
    test_case: TestCase,
    response: str,
    llm_grader: bool = False,
    compare_results: bool = False,
) -> dict:
    """
    Evaluate an agent response using configured methods.

    Returns a dict with:
        - status: "PASS" or "FAIL"
        - missing: list of missing expected strings (for string matching)
        - llm_grade: float score from LLM grader
        - llm_reasoning: string explanation from LLM
        - result_match: bool if golden SQL results match
        - result_explanation: string explanation of result comparison
    """
    result: dict = {}

    # 1. String matching (always run, for backward compatibility)
    missing = check_strings_in_response(response, test_case.expected_strings)
    result["missing"] = missing if missing else None
    string_pass = len(missing) == 0

    # 2. Result comparison (if enabled and golden SQL exists)
    result_pass: bool | None = None
    if compare_results and test_case.golden_sql:
        try:
            golden_result = execute_golden_sql(test_case.golden_sql)
            result["golden_result"] = golden_result

            # Simple check: do expected values appear in golden result?
            # For now, just verify golden SQL runs and check expected strings
            # A more sophisticated version could extract agent's SQL and compare results

            # Check if expected strings match golden result values
            golden_values = [str(v) for row in golden_result for v in row.values()]
            result_pass = all(
                any(exp.lower() in gv.lower() for gv in golden_values)
                for exp in test_case.expected_strings
                if exp and isinstance(exp, str)  # Check all non-empty strings including numeric values
            )
            result["result_match"] = result_pass
            result["result_explanation"] = (
                "Golden SQL validates expected values" if result_pass else "Golden SQL result doesn't match expected"
            )
        except Exception as e:
            result["result_match"] = None
            result["result_explanation"] = f"Error executing golden SQL: {e}"

    # 3. LLM grading (if enabled)
    llm_pass: bool | None = None
    if llm_grader:
        try:
            from recall.evals.grader import grade_response

            llm_golden_result: list[dict] | None = result.get("golden_result")
            if not llm_golden_result and test_case.golden_sql:
                try:
                    llm_golden_result = execute_golden_sql(test_case.golden_sql)
                except Exception:
                    llm_golden_result = None

            grade = grade_response(
                question=test_case.question,
                response=response,
                expected_values=test_case.expected_strings,
                golden_result=llm_golden_result,
            )
            result["llm_grade"] = grade.score
            result["llm_reasoning"] = grade.reasoning
            llm_pass = grade.passed
        except Exception as e:
            result["llm_grade"] = None
            result["llm_reasoning"] = f"Error: {e}"

    # Determine final status
    # Priority: LLM grader > result comparison > string matching
    if llm_grader and llm_pass is not None:
        result["status"] = "PASS" if llm_pass else "FAIL"
    elif compare_results and result_pass is not None:
        result["status"] = "PASS" if result_pass else "FAIL"
    else:
        result["status"] = "PASS" if string_pass else "FAIL"

    return result


def display_results(
    results: list[EvalResult],
    verbose: bool,
    llm_grader: bool,
    compare_results: bool,
):
    """Display results table."""
    table = Table(title="Results", show_lines=True)
    table.add_column("Status", style="bold", width=6)
    table.add_column("Category", style="dim", width=12)
    table.add_column("Question", width=45)
    table.add_column("Time", justify="right", width=6)
    table.add_column("Notes", width=35)

    for r in results:
        if r["status"] == "PASS":
            status = Text("PASS", style="green")
            notes = ""
            if llm_grader and r.get("llm_grade") is not None:
                notes = f"LLM: {r['llm_grade']:.1f}"
        elif r["status"] == "FAIL":
            status = Text("FAIL", style="red")
            llm_reasoning = r.get("llm_reasoning")
            missing = r.get("missing")
            if llm_grader and llm_reasoning:
                notes = llm_reasoning[:35]
            elif missing:
                notes = f"Missing: {', '.join(missing[:2])}"
            else:
                notes = ""
        else:
            status = Text("ERR", style="yellow")
            notes = (r.get("error") or "")[:35]

        table.add_row(
            status,
            r["category"],
            r["question"][:43] + "..." if len(r["question"]) > 43 else r["question"],
            f"{r['duration']:.1f}s",
            notes,
        )

    console.print(table)

    # Verbose output for failures
    if verbose:
        failures = [r for r in results if r["status"] == "FAIL" and r.get("response")]
        if failures:
            console.print("\n[bold red]Failed Responses:[/bold red]")
            for r in failures:
                resp = r["response"] or ""
                panel_content = resp[:500] + "..." if len(resp) > 500 else resp

                # Add grading info if available
                if r.get("llm_reasoning"):
                    panel_content += f"\n\n[dim]LLM Reasoning: {r['llm_reasoning']}[/dim]"
                if r.get("result_explanation"):
                    panel_content += f"\n[dim]Result Check: {r['result_explanation']}[/dim]"

                console.print(
                    Panel(
                        panel_content,
                        title=f"[red]{r['question'][:60]}[/red]",
                        border_style="red",
                    )
                )


def display_summary(results: list[EvalResult], total_duration: float, category: str | None):
    """Display summary statistics."""
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total = len(results)
    rate = (passed / total * 100) if total else 0

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()

    summary.add_row("Total:", f"{total} tests in {total_duration:.1f}s")
    summary.add_row("Passed:", Text(f"{passed} ({rate:.0f}%)", style="green"))
    summary.add_row("Failed:", Text(str(failed), style="red" if failed else "dim"))
    summary.add_row("Errors:", Text(str(errors), style="yellow" if errors else "dim"))
    summary.add_row("Avg time:", f"{total_duration / total:.1f}s per test" if total else "N/A")

    # Add LLM grading average if available
    llm_grades: list[float] = [
        r["llm_grade"] for r in results if r.get("llm_grade") is not None and isinstance(r["llm_grade"], (int, float))
    ]
    if llm_grades:
        avg_grade = sum(llm_grades) / len(llm_grades)
        summary.add_row("Avg LLM Score:", f"{avg_grade:.2f}")

    console.print(
        Panel(
            summary,
            title="[bold]Summary[/bold]",
            border_style="green" if rate == 100 else "yellow",
        )
    )

    # Category breakdown
    if not category and len(CATEGORIES) > 1:
        cat_table = Table(title="By Category", show_header=True)
        cat_table.add_column("Category")
        cat_table.add_column("Passed", justify="right")
        cat_table.add_column("Total", justify="right")
        cat_table.add_column("Rate", justify="right")

        for cat in CATEGORIES:
            cat_results = [r for r in results if r["category"] == cat]
            cat_passed = sum(1 for r in cat_results if r["status"] == "PASS")
            cat_total = len(cat_results)
            cat_rate = (cat_passed / cat_total * 100) if cat_total else 0

            rate_style = "green" if cat_rate == 100 else "yellow" if cat_rate >= 50 else "red"
            cat_table.add_row(
                cat,
                str(cat_passed),
                str(cat_total),
                Text(f"{cat_rate:.0f}%", style=rate_style),
            )

        console.print(cat_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Recall evaluations")
    parser.add_argument("--category", "-c", choices=CATEGORIES, help="Filter by category")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full responses on failure")
    parser.add_argument(
        "--llm-grader",
        "-g",
        action="store_true",
        help="Use LLM to grade responses (requires OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--compare-results",
        "-r",
        action="store_true",
        help="Compare against golden SQL results where available",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write results as a structured JSON artifact to this file path",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        metavar="N",
        help="Number of tests to run in parallel (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        metavar="SECS",
        help="Per-test timeout in seconds (default: 60)",
    )
    args = parser.parse_args()

    run_evals(
        category=args.category,
        verbose=args.verbose,
        llm_grader=args.llm_grader,
        compare_results=args.compare_results,
        output=args.output,
    )
