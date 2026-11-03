import json
import math
import sys
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

E2E_P95_LIMIT = 1.5

METRICS = [
    "e2e_latency",
    "end_of_turn_delay",
    "llm_node_ttft",
    "tts_node_ttfb",
]


# ============================================================
# HELPERS
# ============================================================

def is_valid_number(value):
    """Return True when value is a finite number."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def percentile(values, percentile_value):
    """Calculate percentile using linear interpolation."""
    if not values:
        return None

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * (percentile_value / 100.0)

    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return sorted_values[lower_index]

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]

    fraction = position - lower_index

    return lower_value + (
        upper_value - lower_value
    ) * fraction


# ============================================================
# LOAD REPORTS
# ============================================================

def load_reports():
    """Load all JSON reports from the reports directory."""
    files = sorted(REPORTS_DIR.glob("*.json"))

    if not files:
        print("No JSON reports found.")
        print(f"Expected reports inside: {REPORTS_DIR}")
        return []

    reports = []

    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            reports.append(
                {
                    "file": file,
                    "data": data,
                }
            )

        except (json.JSONDecodeError, OSError) as exc:
            print(
                f"Warning: could not read {file.name}: {exc}"
            )

    return reports


# ============================================================
# SESSION REPORT METRICS
# ============================================================

def collect_session_report_metrics(data, values):
    """
    Collect metrics from LiveKit session reports.

    These reports normally contain chat_history items.
    Text simulations can provide LLM metrics but normally
    do not contain real audio e2e/TTS measurements.
    """

    chat_history = data.get("chat_history", {})

    if not isinstance(chat_history, dict):
        return

    items = chat_history.get("items", [])

    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(item, dict):
            continue

        role = item.get("role")

        metrics = item.get("metrics", {})

        if not isinstance(metrics, dict):
            continue

        # User-side metric
        if role == "user":
            value = metrics.get("end_of_turn_delay")

            if is_valid_number(value):
                values["end_of_turn_delay"].append(
                    float(value)
                )

        # Assistant-side metrics
        elif role == "assistant":

            for metric in [
                "e2e_latency",
                "llm_node_ttft",
                "tts_node_ttfb",
            ]:
                value = metrics.get(metric)

                if is_valid_number(value):
                    values[metric].append(
                        float(value)
                    )


# ============================================================
# AUDIO SIMULATION METRICS
# ============================================================

def collect_audio_simulation_metrics(data, values):
    """
    Collect metrics from exported LiveKit audio simulation runs.

    Only turn-level assistant metrics are collected.

    This avoids double-counting job-level aggregate metrics.
    """

    run = data.get("run", {})

    if not isinstance(run, dict):
        return

    jobs = run.get("jobs", [])

    if not isinstance(jobs, list):
        return

    for job in jobs:

        if not isinstance(job, dict):
            continue

        metrics = job.get("metrics", {})

        if not isinstance(metrics, dict):
            continue

        turns = metrics.get("turns", [])

        if not isinstance(turns, list):
            continue

        for turn in turns:

            if not isinstance(turn, dict):
                continue

            # We only use assistant turns for these metrics.
            if turn.get("role") != "ASSISTANT":
                continue

            # ------------------------------------------------
            # LLM TTFT
            # ------------------------------------------------

            llm_ttft_ms = turn.get("llm_ttft_ms")

            if is_valid_number(llm_ttft_ms):
                values["llm_node_ttft"].append(
                    float(llm_ttft_ms) / 1000.0
                )

            # ------------------------------------------------
            # TTS TTFB
            # ------------------------------------------------

            tts_ttfb_ms = turn.get("tts_ttfb_ms")

            if is_valid_number(tts_ttfb_ms):
                values["tts_node_ttfb"].append(
                    float(tts_ttfb_ms) / 1000.0
                )

            # ------------------------------------------------
            # End-to-end latency
            # ------------------------------------------------

            e2e_latency_ms = turn.get("e2e_latency_ms")

            if is_valid_number(e2e_latency_ms):
                values["e2e_latency"].append(
                    float(e2e_latency_ms) / 1000.0
                )


# ============================================================
# COLLECT ALL METRICS
# ============================================================

def collect_metrics(reports):
    """Collect all supported metrics from all reports."""

    values = {
        metric: []
        for metric in METRICS
    }

    for report in reports:

        data = report["data"]

        # Normal LiveKit session report
        if "chat_history" in data:
            collect_session_report_metrics(
                data,
                values,
            )

        # Exported LiveKit simulation report
        if "run" in data:
            collect_audio_simulation_metrics(
                data,
                values,
            )

    return values


# ============================================================
# PRINT METRIC
# ============================================================

def print_metric(name, values):
    """Print p50, p95 and sample count."""

    print(name)

    if not values:
        print("  p50: N/A")
        print("  p95: N/A")
        print("  samples: 0")
        print()

        return

    p50 = percentile(values, 50)
    p95 = percentile(values, 95)

    print(f"  p50: {p50:.3f} s")
    print(f"  p95: {p95:.3f} s")
    print(f"  samples: {len(values)}")
    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print("Latency Report")
    print("==============")
    print()

    # --------------------------------------------------------
    # Load reports
    # --------------------------------------------------------

    reports = load_reports()

    if not reports:
        sys.exit(1)

    print(f"Reports found: {len(reports)}")
    print()

    # --------------------------------------------------------
    # Collect metrics
    # --------------------------------------------------------

    values = collect_metrics(reports)

    # --------------------------------------------------------
    # Print metrics
    # --------------------------------------------------------

    for metric in METRICS:
        print_metric(
            metric,
            values[metric],
        )

    # --------------------------------------------------------
    # Validate e2e latency requirement
    # --------------------------------------------------------

    e2e_values = values["e2e_latency"]

    if not e2e_values:

        print(
            "WARNING: No e2e_latency values were found."
        )

        print(
            "Audio simulation reports are required "
            "to measure real speech-to-response latency."
        )

        return

    e2e_p95 = percentile(
        e2e_values,
        95,
    )

    print(
        f"e2e_latency p95 limit: "
        f"{E2E_P95_LIMIT:.3f} s"
    )

    print(
        f"e2e_latency p95 actual: "
        f"{e2e_p95:.3f} s"
    )

    # --------------------------------------------------------
    # PASS / FAIL
    # --------------------------------------------------------

    if e2e_p95 > E2E_P95_LIMIT:

        print()

        print(
            "FAIL: p95 e2e_latency exceeds "
            "the 1.5 second limit."
        )

        sys.exit(1)

    print()

    print(
        "PASS: p95 e2e_latency is within "
        "the 1.5 second limit."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()