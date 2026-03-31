"""
Custom tools for the Incident Intelligence Agent.

These tools give the agent structured metadata about the raw log input
before it begins writing the narrative, helping it anchor claims in
quantifiable evidence rather than guessing.
"""

import re
from datetime import datetime

TIMESTAMP_PATTERNS = [
    (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "%Y-%m-%dT%H:%M:%S"),
    (r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "%Y-%m-%d %H:%M:%S"),
    (r"[A-Z][a-z]{2} \d{1,2} \d{2}:\d{2}:\d{2}", "%b %d %H:%M:%S"),
    (r"\d{2}:\d{2}:\d{2}\.\d+", "%H:%M:%S.%f"),
]

SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _parse_timestamp(match: str) -> datetime | None:
    """Parse a matched timestamp into a comparable datetime."""
    for _, fmt in TIMESTAMP_PATTERNS:
        try:
            parsed = datetime.strptime(match, fmt)
            if fmt == "%b %d %H:%M:%S":
                parsed = parsed.replace(year=datetime.utcnow().year)
            if fmt == "%H:%M:%S.%f":
                today = datetime.utcnow()
                parsed = parsed.replace(
                    year=today.year,
                    month=today.month,
                    day=today.day,
                )
            return parsed
        except ValueError:
            continue
    return None


def _find_timestamp_in_line(line: str) -> tuple[str | None, datetime | None]:
    """Return the first timestamp match in a line and its parsed datetime."""
    for pattern, _ in TIMESTAMP_PATTERNS:
        match = re.search(pattern, line)
        if match:
            raw = match.group()
            return raw, _parse_timestamp(raw)
    return None, None


def _format_duration_seconds(duration_seconds: float | None) -> str | None:
    """Format a duration in seconds into a short human-readable string."""
    if duration_seconds is None:
        return None

    seconds = int(round(duration_seconds))
    if seconds < 60:
        return f"~{seconds}s"

    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"~{minutes} min"
    return f"~{minutes} min {remainder}s"


def analyze_log_structure(raw_logs: str) -> dict:
    """Analyze raw log text and return structural metadata.

    Counts total lines, identifies distinct log sources/prefixes,
    detects timestamp formats present, and flags potential gaps.
    Use this tool FIRST on every log input to ground the analysis
    in hard numbers before writing the narrative.
    """
    lines = [line for line in raw_logs.strip().split("\n") if line.strip()]
    total_lines = len(lines)
    total_characters = len(raw_logs)

    source_patterns = [
        r"\[([a-zA-Z0-9_-]+)\]",
        r'source="([^"]+)"',
        r'component="([^"]+)"',
        r"pod/([a-zA-Z0-9_-]+)",
        r'container="([^"]+)"',
    ]
    detected_sources = set()
    for line in lines:
        for pattern in source_patterns:
            detected_sources.update(re.findall(pattern, line))

    timestamps_found = []
    timestamp_count = 0
    for line in lines:
        for pattern, _ in TIMESTAMP_PATTERNS:
            match = re.search(pattern, line)
            if match:
                timestamp_count += 1
                timestamps_found.append(match.group())
                break

    parsed_timestamps = [
        (raw_match, parsed)
        for raw_match in timestamps_found
        for parsed in [_parse_timestamp(raw_match)]
        if parsed is not None
    ]
    earliest_entry = min(parsed_timestamps, key=lambda item: item[1]) if parsed_timestamps else None
    latest_entry = max(parsed_timestamps, key=lambda item: item[1]) if parsed_timestamps else None

    error_indicators = [
        "ERROR",
        "error",
        "ERR",
        "E ",
        "level=error",
        "severity=ERROR",
        '"level":"error"',
        "status=500",
    ]
    warning_indicators = [
        "WARNING",
        "WARN",
        "W ",
        "level=warn",
        "severity=WARNING",
        '"level":"warn"',
    ]
    fatal_indicators = [
        "FATAL",
        "PANIC",
        "panic:",
        "fatal",
        "level=fatal",
        "severity=CRITICAL",
    ]

    error_count = sum(
        1 for line in lines if any(indicator in line for indicator in error_indicators)
    )
    warning_count = sum(
        1 for line in lines if any(indicator in line for indicator in warning_indicators)
    )
    fatal_count = sum(
        1 for line in lines if any(indicator in line for indicator in fatal_indicators)
    )

    oom_patterns = ["OOMKilled", "oom-kill", "Out of memory", "OOM", "oom_kill"]
    oom_kill_detected = any(any(pattern in line for pattern in oom_patterns) for line in lines)

    restart_patterns = ["CrashLoopBackOff", "Restarting", "restarted", "BackOff"]
    restart_count = sum(
        1 for line in lines if any(pattern in line for pattern in restart_patterns)
    )

    http_status_codes = {}
    http_pattern = r"(?:status[_=: ]*|HTTP[/ ]*\d\.\d[\" ]*)\s*(\d{3})"
    for line in lines:
        for code in re.findall(http_pattern, line):
            http_status_codes[code] = http_status_codes.get(code, 0) + 1

    symptom_candidates = []
    detection_candidates = []
    recovery_candidates = []

    detection_markers = [
        "alertmanager",
        "FIRING",
        "severity=critical",
        "severity=CRITICAL",
        "critical",
    ]
    recovery_markers = [
        "recovered",
        "responding 200",
        "Connection established",
        "Pool initialized",
        "restored",
        "healthy",
    ]

    for line in lines:
        raw_ts, parsed_ts = _find_timestamp_in_line(line)
        if not raw_ts or parsed_ts is None:
            continue

        line_has_symptom = any(indicator in line for indicator in error_indicators + warning_indicators + fatal_indicators)
        if line_has_symptom:
            symptom_candidates.append((raw_ts, parsed_ts, line))

        if any(marker in line for marker in detection_markers):
            detection_candidates.append((raw_ts, parsed_ts, line))

        if any(marker in line for marker in recovery_markers):
            recovery_candidates.append((raw_ts, parsed_ts, line))

    first_symptom = min(symptom_candidates, key=lambda item: item[1]) if symptom_candidates else None
    first_detection = min(detection_candidates, key=lambda item: item[1]) if detection_candidates else None
    first_recovery = min(recovery_candidates, key=lambda item: item[1]) if recovery_candidates else None
    final_recovery = max(recovery_candidates, key=lambda item: item[1]) if recovery_candidates else None

    severity_score = 1
    if fatal_count > 0 or any("severity=critical" in line.lower() for line in lines):
        severity_score = 4
    elif restart_count > 0 or "503" in http_status_codes or error_count >= 3:
        severity_score = 3
    elif warning_count > 0 or error_count > 0:
        severity_score = 2

    severity = SEVERITY_LEVELS[severity_score - 1]

    detection_time_seconds = None
    recovery_time_seconds = None
    if first_symptom and first_detection:
        detection_time_seconds = (first_detection[1] - first_symptom[1]).total_seconds()
    if first_symptom and final_recovery:
        recovery_time_seconds = (final_recovery[1] - first_symptom[1]).total_seconds()

    return {
        "total_lines": total_lines,
        "total_characters": total_characters,
        "detected_sources": (
            sorted(detected_sources)
            if detected_sources
            else ["no distinct sources detected - logs may be single-source"]
        ),
        "timestamp_count": timestamp_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "fatal_count": fatal_count,
        "oom_kill_detected": oom_kill_detected,
        "restart_count": restart_count,
        "http_status_codes": (
            http_status_codes if http_status_codes else {"none": "no HTTP status codes found"}
        ),
        "earliest_timestamp": (
            earliest_entry[0] if earliest_entry else None
        ),
        "latest_timestamp": (
            latest_entry[0] if latest_entry else None
        ),
        "severity": severity,
        "incident_start_timestamp": first_symptom[0] if first_symptom else None,
        "first_symptom_timestamp": first_symptom[0] if first_symptom else None,
        "detection_timestamp": first_detection[0] if first_detection else None,
        "recovery_timestamp": final_recovery[0] if final_recovery else None,
        "detection_time_seconds": detection_time_seconds,
        "recovery_time_seconds": recovery_time_seconds,
        "detection_time_human": _format_duration_seconds(detection_time_seconds),
        "recovery_time_human": _format_duration_seconds(recovery_time_seconds),
        "detection_time_basis": (
            f"from {first_symptom[0]} to {first_detection[0]}"
            if first_symptom and first_detection
            else None
        ),
        "recovery_time_basis": (
            f"from {first_symptom[0]} to {final_recovery[0]}"
            if first_symptom and final_recovery
            else None
        ),
    }
