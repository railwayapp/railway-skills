#!/usr/bin/env python3
"""Shared Railway infrastructure helpers for database analysis scripts."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

LOG_LINES_DEFAULT = 1000  # Number of log lines to fetch via API


class ProgressTimer:
    """Track elapsed time for progress messages."""
    def __init__(self):
        self.start_time = None
        self.step_start_time = None

    def start(self):
        """Start the overall timer."""
        self.start_time = datetime.now()
        self.step_start_time = self.start_time

    def step_elapsed(self) -> str:
        """Get elapsed time since last step, then reset step timer."""
        if self.step_start_time is None:
            return ""
        now = datetime.now()
        elapsed = (now - self.step_start_time).total_seconds()
        self.step_start_time = now
        if elapsed < 0.1:
            return ""
        return f" ({elapsed:.1f}s)"

    def total_elapsed(self) -> str:
        """Get total elapsed time."""
        if self.start_time is None:
            return ""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return f" (total: {elapsed:.1f}s)"


# Global timer instance
_progress_timer = ProgressTimer()


@dataclass
class RailwayContext:
    """Explicit Railway IDs that bypass railway link."""
    project_id: Optional[str] = None
    environment_id: Optional[str] = None
    service_id: Optional[str] = None

    def ssh_flags(self) -> List[str]:
        """Return CLI flags for railway ssh."""
        flags = ["--native"]
        if self.project_id:
            flags.extend(["--project", self.project_id])
        if self.environment_id:
            flags.extend(["--environment", self.environment_id])
        if self.service_id:
            flags.extend(["--service", self.service_id])
        return flags

    def logs_flags(self) -> List[str]:
        """Return CLI flags for railway logs."""
        flags = []
        if self.environment_id:
            flags.extend(["--environment", self.environment_id])
        return flags


# Global context — set once at startup, used by all CLI calls
_ctx = RailwayContext()


def _init_context(args) -> None:
    """Initialize global context from CLI args or railway config."""
    global _ctx
    if args.environment_id and args.service_id:
        _ctx = RailwayContext(
            project_id=getattr(args, 'project_id', None),
            environment_id=args.environment_id,
            service_id=args.service_id,
        )
    else:
        railway_status = get_railway_status()
        if railway_status:
            _ctx = RailwayContext(
                project_id=railway_status.get("projectId"),
                environment_id=railway_status.get("environmentId"),
                service_id=railway_status.get("serviceId"),
            )


def progress(step: int, total: int, message: str, quiet: bool = False):
    """Print progress message to stderr with elapsed time."""
    if not quiet:
        # Show elapsed time from previous step (before current step message)
        elapsed = _progress_timer.step_elapsed()
        if elapsed:
            print(f"        done{elapsed}", file=sys.stderr, flush=True)
        print(f"  [{step}/{total}] {message}", file=sys.stderr, flush=True)


def run_railway_command(args: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Run a railway CLI command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["railway"] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except FileNotFoundError:
        return 127, "", "railway CLI not found"


def _cli_fatal_error(returncode: int, stderr: str) -> Optional[str]:
    """Return a friendly error string if the CLI itself is broken, else None.

    These errors are unrecoverable — retrying won't help.
    """
    if returncode == 127 or "railway CLI not found" in stderr:
        return (
            "Railway CLI not found. "
            "Install it with: npm i -g @railway/cli  "
            "or  brew install railway"
        )
    lower = stderr.lower()
    if "unknown flag" in lower or "flag provided but not defined" in lower:
        return (
            "Railway CLI is outdated — the --native SSH flag is not supported. "
            "Update it with: npm i -g @railway/cli@latest  "
            "or  brew upgrade railway"
        )
    return None


def run_ssh_query(service: str, command: str, timeout: int = 60,
                  max_attempts: int = 3) -> Tuple[int, str, str]:
    """Run a command via railway ssh, retrying up to max_attempts times.

    Passes the command as a single argument after '--'. Railway ssh
    interprets it through a shell on the remote end, so pipes, env vars,
    and redirects all work without an explicit sh -c wrapper.

    Retries on non-zero exit code or empty stdout (covers transient errors
    like 'exec request failed on channel 0').  Never retries when the CLI
    itself is missing or outdated — those errors are unrecoverable.
    """
    flags = _ctx.ssh_flags()
    # Only pass --service <name> if context didn't already provide --service <id>
    if not _ctx.service_id:
        flags += ["--service", service]
    args = ["ssh"] + flags + ["--", command]
    last_code, last_stdout, last_stderr = 1, "", ""
    for attempt in range(1, max_attempts + 1):
        last_code, last_stdout, last_stderr = run_railway_command(args, timeout)
        if last_code == 0 and last_stdout.strip():
            return last_code, last_stdout, last_stderr
        fatal = _cli_fatal_error(last_code, last_stderr)
        if fatal:
            return last_code, last_stdout, fatal
        if attempt < max_attempts:
            print(
                f"        SSH attempt {attempt}/{max_attempts} failed "
                f"({last_stderr.strip() or 'empty response'}), retrying...",
                file=sys.stderr, flush=True,
            )
    return last_code, last_stdout, last_stderr


def run_psql_query(service: str, query: str, timeout: int = 60) -> Tuple[int, str]:
    """Run a psql query via railway ssh and return (returncode, output).

    Normalizes query whitespace and suppresses psql warnings (e.g. collation
    version mismatch) that would otherwise pollute stdout.
    """
    query = " ".join(query.split())
    command = f'''PAGER='' psql $DATABASE_URL -P pager=off -t -A -c "{query}" 2>/dev/null'''
    code, stdout, stderr = run_ssh_query(service, command, timeout)
    if code != 0:
        return code, stderr or stdout
    return 0, stdout


def get_railway_status() -> Optional[Dict[str, Any]]:
    """Get environment and service IDs from Railway config file.

    Reads directly from ~/.railway/config.json instead of calling CLI (~15s saved).
    """
    config_path = os.path.expanduser("~/.railway/config.json")
    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        # Get linked project for current directory
        cwd = os.getcwd()
        projects = config.get("projects", {})

        # Find project config for current directory or parent
        project_config = None
        check_path = cwd
        while check_path != "/":
            if check_path in projects:
                project_config = projects[check_path]
                break
            check_path = os.path.dirname(check_path)

        if not project_config:
            return None

        return {
            "projectId": project_config.get("project"),
            "environmentId": project_config.get("environment"),
            "serviceId": project_config.get("service"),
            "serviceName": project_config.get("name", ""),
        }
    except (json.JSONDecodeError, IOError):
        return None


def get_deployment_status(service: str, service_id: Optional[str] = None) -> str:
    """Get deployment status for service.

    Uses direct API call if service_id provided (~1s), falls back to CLI (~15s).
    """
    # Fast path: use API directly if we have service_id
    if service_id:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_script = os.path.join(script_dir, "railway-api.sh")

        if os.path.exists(api_script):
            query = '''query svc($id: String!) {
                service(id: $id) {
                    deployments(first: 1) {
                        edges { node { status } }
                    }
                }
            }'''
            try:
                result = subprocess.run(
                    [api_script, query, json.dumps({"id": service_id})],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    edges = data.get("data", {}).get("service", {}).get("deployments", {}).get("edges", [])
                    if edges:
                        return edges[0].get("node", {}).get("status", "UNKNOWN")
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                pass

    # Fallback: use CLI (slow, ~15s)
    code, stdout, stderr = run_railway_command(
        ["service", "status", "--service", service, "--json"]
    )
    if code != 0:
        return "UNKNOWN"
    try:
        data = json.loads(stdout)
        status = data.get("status", "UNKNOWN")
        if data.get("stopped"):
            return f"{status} (stopped)"
        return status
    except json.JSONDecodeError:
        return "UNKNOWN"


def get_all_metrics_from_api(environment_id: str, service_id: str, hours: int = 24) -> Optional[Dict[str, Any]]:
    """Get disk, CPU, memory, and network usage from Railway metrics API.

    Fetches time-series data and computes trend analysis including
    min/max/avg, spike detection, and directional trends.

    Args:
        hours: Hours of history to fetch (default: 24, max: 168)
    """
    from datetime import timedelta

    start_date = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    api_script = os.path.join(script_dir, "railway-api.sh")

    if not os.path.exists(api_script):
        return None

    query = '''query metrics($environmentId: String!, $serviceId: String, $startDate: DateTime!, $measurements: [MetricMeasurement!]!) {
        metrics(environmentId: $environmentId, serviceId: $serviceId, startDate: $startDate, measurements: $measurements) {
            measurement values { ts value }
        }
    }'''

    variables = json.dumps({
        "environmentId": environment_id,
        "serviceId": service_id,
        "startDate": start_date,
        "measurements": [
            "DISK_USAGE_GB", "CPU_USAGE", "MEMORY_USAGE_GB",
            "MEMORY_LIMIT_GB", "CPU_LIMIT",
            "NETWORK_RX_GB", "NETWORK_TX_GB",
        ]
    })

    try:
        result = subprocess.run(
            [api_script, query, variables],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        metrics = data.get("data", {}).get("metrics", [])

        combined = {"disk_usage": None, "cpu_memory": {}, "metrics_history": None}

        # Raw time series keyed by measurement name
        raw_series: Dict[str, List[Dict[str, Any]]] = {}

        for metric in metrics:
            measurement = metric.get("measurement")
            values = metric.get("values", [])
            if values:
                raw_series[measurement] = values
                latest = values[-1].get("value", 0)
                if measurement == "DISK_USAGE_GB":
                    combined["disk_usage"] = {
                        "used_gb": round(latest, 2),
                        "used": f"{round(latest, 1)} GB"
                    }
                elif measurement == "CPU_USAGE":
                    combined["cpu_memory"]["cpu_percent"] = round(latest, 1)
                elif measurement == "MEMORY_USAGE_GB":
                    combined["cpu_memory"]["memory_gb"] = round(latest, 2)
                elif measurement == "MEMORY_LIMIT_GB":
                    combined["cpu_memory"]["memory_limit_gb"] = round(latest, 2)
                elif measurement == "CPU_LIMIT":
                    combined["cpu_memory"]["cpu_limit"] = round(latest, 1)

        if not combined["cpu_memory"]:
            combined["cpu_memory"] = None

        # Build time-series history with trend analysis
        if raw_series:
            combined["metrics_history"] = _build_metrics_history(raw_series, hours=hours)

        return combined
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    return None


def _analyze_window(values: List[Dict[str, Any]], nums: List[float], d: int,
                    unit: str) -> Dict[str, Any]:
    """Analyze a single time window of metric data.

    Returns summary stats, trend, spike detection, and downsampled series.
    """
    if not nums:
        return {}

    avg_val = sum(nums) / len(nums)
    min_val = min(nums)
    max_val = max(nums)

    entry: Dict[str, Any] = {
        "unit": unit,
        "current": round(nums[-1], d),
        "min": round(min_val, d),
        "max": round(max_val, d),
        "avg": round(avg_val, d),
        "samples": len(nums),
    }

    # Trend: compare first quarter avg to last quarter avg
    q_size = max(len(nums) // 4, 1)
    first_q = nums[:q_size]
    last_q = nums[-q_size:]
    first_avg = sum(first_q) / len(first_q)
    last_avg = sum(last_q) / len(last_q)

    if first_avg > 0:
        change_pct = round(((last_avg - first_avg) / first_avg) * 100, 1)
    elif last_avg > 0:
        change_pct = 100.0
    else:
        change_pct = 0.0

    if change_pct > 10:
        trend_dir = "increasing"
    elif change_pct < -10:
        trend_dir = "decreasing"
    else:
        trend_dir = "stable"

    entry["trend"] = {
        "direction": trend_dir,
        "change_pct": change_pct,
        "first_quarter_avg": round(first_avg, d),
        "last_quarter_avg": round(last_avg, d),
    }

    # Spike detection
    if len(nums) >= 10:
        variance = sum((x - avg_val) ** 2 for x in nums) / len(nums)
        stddev = variance ** 0.5
        threshold = avg_val + 2 * stddev
        if stddev > 0 and threshold > 0:
            spikes = []
            for v in values:
                val = v.get("value")
                if val is not None and val > threshold:
                    spikes.append({"ts": v["ts"], "value": round(val, d)})
            if spikes:
                entry["spikes"] = {
                    "count": len(spikes),
                    "threshold": round(threshold, d),
                    "peaks": spikes[:10],
                }

    # Compact time series: downsample to ~48 points
    series_points = []
    for v in values:
        ts = v.get("ts")
        val = v.get("value")
        if ts is not None and val is not None:
            series_points.append({"ts": ts, "value": round(val, d)})

    if len(series_points) > 48:
        step = len(series_points) / 48
        downsampled = []
        for i in range(48):
            idx = int(i * step)
            downsampled.append(series_points[idx])
        downsampled.append(series_points[-1])
        entry["series"] = downsampled
    else:
        entry["series"] = series_points

    return entry


def _build_metrics_history(raw_series: Dict[str, List[Dict[str, Any]]], hours: int = 168) -> Dict[str, Any]:
    """Build multi-window time-series history with trend analysis.

    Always produces a full-window analysis. If the window is > 24h, also
    produces a 24h short-window analysis from the tail of the data so the
    LLM can compare long-term vs short-term trends.
    """
    from datetime import timedelta

    metric_info = {
        "CPU_USAGE": {"name": "cpu", "unit": "vCPU", "decimals": 2},
        "MEMORY_USAGE_GB": {"name": "memory", "unit": "GB", "decimals": 2},
        "MEMORY_LIMIT_GB": {"name": "memory_limit", "unit": "GB", "decimals": 2},
        "CPU_LIMIT": {"name": "cpu_limit", "unit": "vCPU", "decimals": 2},
        "DISK_USAGE_GB": {"name": "disk", "unit": "GB", "decimals": 2},
        "NETWORK_RX_GB": {"name": "network_rx", "unit": "GB", "decimals": 3},
        "NETWORK_TX_GB": {"name": "network_tx", "unit": "GB", "decimals": 3},
    }

    # Determine the 24h cutoff timestamp
    now_ts = int(datetime.now(timezone.utc).timestamp())
    cutoff_24h = now_ts - (24 * 3600)

    produce_short_window = hours > 24

    full_window: Dict[str, Any] = {}
    short_window: Dict[str, Any] = {}

    for measurement, values in raw_series.items():
        info = metric_info.get(measurement)
        if not info or len(values) < 2:
            continue

        nums = [v["value"] for v in values if v.get("value") is not None]
        if not nums:
            continue

        d = info["decimals"]
        name = info["name"]

        # Full window analysis
        full_window[name] = _analyze_window(values, nums, d, info["unit"])

        # Short window (last 24h) analysis
        if produce_short_window:
            recent_values = [v for v in values if v.get("ts", 0) >= cutoff_24h]
            recent_nums = [v["value"] for v in recent_values if v.get("value") is not None]
            if len(recent_nums) >= 2:
                short_window[name] = _analyze_window(recent_values, recent_nums, d, info["unit"])

    # Build the result with named windows
    windows: Dict[str, Any] = {}

    # Label the full window
    if hours >= 168:
        full_label = "7d"
    elif hours >= 72:
        full_label = f"{hours // 24}d"
    else:
        full_label = f"{hours}h"

    windows[full_label] = {
        "window_hours": hours,
        "metrics": full_window,
    }

    if produce_short_window and short_window:
        windows["24h"] = {
            "window_hours": 24,
            "metrics": short_window,
        }

    return {"windows": windows}


# ---------------------------------------------------------------------------
# Railway support scope
# ---------------------------------------------------------------------------

SUPPORT_SCOPE_DOCS = "https://docs.railway.com/databases#database-support-scope"

# The images Railway's database templates deploy. A service running one of
# them is an official Railway database: Railway runs the template as shipped,
# and support covers it only while its configuration is the template's. An
# image this allowlist does not name (pgvector, TimescaleDB, a fork, a repo
# build) is the user's to manage. The list mirrors the dashboard's engine
# registry; add to it, never widen it by pattern.
OFFICIAL_IMAGE_PREFIXES = (
    "ghcr.io/railwayapp-templates/",
    "ghcr.io/railway/",
)
OFFICIAL_DOCKER_HUB_PATHS = frozenset({
    "mysql", "library/mysql",
    "redis", "library/redis", "railwayapp/redis", "bitnami/redis",
    "mongo", "library/mongo",
})


def _image_repository(image: str) -> Tuple[Optional[str], str]:
    """Split an image reference into (registry or None, repository path)."""
    ref = image.strip()
    if "@" in ref:
        ref = ref.split("@", 1)[0]
    # A tag is the part after the last ':' when it follows the last '/'.
    last_slash = ref.rfind("/")
    last_colon = ref.rfind(":")
    if last_colon > last_slash:
        ref = ref[:last_colon]
    first, _, rest = ref.partition("/")
    looks_like_registry = "." in first or ":" in first or first == "localhost"
    if rest and looks_like_registry:
        return first.lower(), rest
    return None, ref


def is_official_database_image(image: Optional[str]) -> bool:
    """Whether `image` is one Railway's database templates deploy."""
    if not image:
        return False
    registry, path = _image_repository(image)
    if registry is None and image.strip().lower().startswith(OFFICIAL_IMAGE_PREFIXES):
        return True
    if registry is not None and f"{registry}/{path}".lower().startswith(OFFICIAL_IMAGE_PREFIXES):
        return True
    if registry in (None, "docker.io", "index.docker.io"):
        return path.lower() in OFFICIAL_DOCKER_HUB_PATHS
    return False


def fetch_service_image(environment_id: Optional[str], service_id: Optional[str]) -> Optional[str]:
    """The image a service is configured with, from the environment config."""
    if not environment_id or not service_id:
        return None
    script_dir = os.path.dirname(os.path.abspath(__file__))
    api_script = os.path.join(script_dir, "railway-api.sh")
    if not os.path.exists(api_script):
        return None
    query = """query cfg($id: String!) {
        environment(id: $id) { config(decryptVariables: false) }
    }"""
    try:
        result = subprocess.run(
            [api_script, query, json.dumps({"id": environment_id})],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        config = data.get("data", {}).get("environment", {}).get("config") or {}
        if isinstance(config, str):
            config = json.loads(config)
        service = (config.get("services") or {}).get(service_id) or {}
        image = (service.get("source") or {}).get("image")
        return image if isinstance(image, str) and image else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError, OSError):
        return None


def resolve_support_scope(environment_id: Optional[str], service_id: Optional[str]) -> Dict[str, Any]:
    """Whether the database is an official Railway database (support scope applies).

    An image that cannot be read is treated as official: the safe failure is a
    recommendation withheld, never a configuration change proposed on a
    database Railway supports.
    """
    image = fetch_service_image(environment_id, service_id)
    if image is None:
        return {
            "managed": True,
            "image": None,
            "reason": "the service image could not be read; treated as an official Railway database",
            "docs": SUPPORT_SCOPE_DOCS,
        }
    managed = is_official_database_image(image)
    return {
        "managed": managed,
        "image": image,
        "reason": ("official Railway database template image" if managed
                   else "custom image; the database is the user's to manage"),
        "docs": SUPPORT_SCOPE_DOCS,
    }


# What a recommendation may tell the user to run on an official Railway
# database: the user's own domain (schema, indexes, queries, data, sessions)
# and reads. Anything else (settings, roles, extensions, server config,
# restarts of the engine from inside) is the template's configuration and
# takes the database out of Railway support, so it is dropped. Allowlist,
# deliberately: a statement kind this list does not name is out.
_IN_SCOPE_SQL_PREFIXES = (
    "select", "explain", "show", "with",
    "vacuum", "analyze", "reindex", "cluster",
    "create index", "create unique index", "drop index", "alter index",
    "alter table", "create table", "drop table",
    "optimize table", "analyze table", "check table",
    "kill ",
)
_IN_SCOPE_REDIS_PREFIXES = (
    "scan", "info", "slowlog", "memory", "object", "ttl", "type", "dbsize",
    "client list", "client kill", "config get", "del ", "unlink", "expire",
)
_IN_SCOPE_MONGO_PATTERNS = (
    r"^db\.[A-Za-z0-9_]+\.(createIndex|createIndexes|dropIndex|dropIndexes|getIndexes|stats|find|aggregate|explain|reIndex|totalIndexSize)\(",
    r"^db\.(currentOp|killOp|getProfilingStatus|serverStatus|stats|getCollectionNames)\(",
)


def is_in_scope_command(command: str) -> bool:
    """Whether a single recommended command stays inside Railway support scope."""
    import re
    text = command.strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered.startswith("--") or lowered.startswith("#") or lowered.startswith("//"):
        return True
    if lowered.startswith(_IN_SCOPE_SQL_PREFIXES):
        return True
    if lowered.startswith(_IN_SCOPE_REDIS_PREFIXES):
        return True
    return any(re.match(pattern, text) for pattern in _IN_SCOPE_MONGO_PATTERNS)


def _filter_commands(commands: List[str]) -> Tuple[List[str], int]:
    """Keep in-scope commands; a comment stays with the command it annotates."""
    kept: List[str] = []
    dropped = 0
    pending_comments: List[str] = []
    for line in commands:
        stripped = line.strip().lower()
        if stripped.startswith(("--", "#", "//")):
            pending_comments.append(line)
            continue
        if is_in_scope_command(line):
            kept.extend(pending_comments)
            kept.append(line)
        else:
            dropped += 1
        pending_comments = []
    return kept, dropped


def support_scope_note(setting: Optional[str] = None, in_scope: Optional[str] = None) -> str:
    what = f"changing {setting}" if setting else "a configuration change"
    note = (f"Outside Railway support scope: {what} on an official Railway database by hand "
            f"takes it out of support ({SUPPORT_SCOPE_DOCS}). Not applied, and no command is given for it.")
    if in_scope:
        note += f" In scope instead: {in_scope}"
    return note


def describe_support_scope(scope: Dict[str, Any]) -> str:
    """One line for a report header."""
    image = f" (image: {scope['image']})" if scope.get("image") else ""
    if scope.get("managed"):
        return ("official Railway database; its configuration is the template's, so findings whose remedy "
                f"is a configuration change are informational{image}")
    return f"custom image; the database is yours to manage{image}"


def apply_support_scope(recommendations: List[Dict[str, Any]], scope: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rewrite recommendations for an official Railway database.

    A recommendation tagged `scope: "config"` (its remedy is a setting, an
    extension, a role or the service's own configuration) loses its remedy and
    commands and becomes an informational finding that says why. Any other
    recommendation keeps only the commands that stay in scope. On a custom
    image nothing changes.
    """
    if not scope or not scope.get("managed"):
        return recommendations
    out: List[Dict[str, Any]] = []
    for original in recommendations:
        rec = dict(original)
        commands = rec.get("commands")
        if isinstance(commands, list):
            kept, dropped = _filter_commands(commands)
            if dropped:
                rec["commands_outside_scope"] = dropped
            if kept:
                rec["commands"] = kept
            else:
                rec.pop("commands", None)
        if rec.get("scope") == "config":
            note = support_scope_note(rec.get("setting"), rec.get("in_scope"))
            rec["support_scope"] = "outside"
            rec.pop("commands", None)
            rec.pop("restart_required", None)
            if "observation" in rec:
                rec["message"] = f"{rec['observation']} {note}"
            elif "action" in rec:
                rec["action"] = note
            elif "message" in rec:
                rec["message"] = f"{rec['message']} {note}"
            if not rec.get("keep_priority"):
                if "priority" in rec:
                    rec["priority"] = "info"
                if "severity" in rec:
                    rec["severity"] = "info"
        elif rec.get("commands_outside_scope"):
            rec["support_scope"] = "partial"
        out.append(rec)
    return out


def info(msg: str) -> None:
    """Print an [INFO] message to stdout."""
    print(f"[INFO] {msg}")


def error(msg: str) -> None:
    """Print an [ERROR] message to stderr and exit."""
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def confirm_with_user(prompt: str) -> bool:
    """Get confirmation directly from the terminal.

    Reads from /dev/tty to ensure it's an actual user at a terminal,
    not piped input. This prevents automated scripts from bypassing confirmation.
    """
    try:
        with open('/dev/tty', 'r') as tty:
            print(prompt, end=' ', flush=True)
            response = tty.readline().strip().lower()
            return response in ('y', 'yes')
    except (OSError, IOError):
        print("\n[ERROR] This command requires interactive terminal confirmation.")
        print("It cannot be run with piped input or in non-interactive mode.")
        print("Please run this command directly in a terminal.")
        return False


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _format_uptime(seconds: int) -> str:
    """Format uptime seconds into a human-readable string."""
    if seconds <= 0:
        return "N/A"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "< 1m"


def _trend_indicator(metrics_history: Optional[Dict[str, Any]], metric_name: str) -> str:
    """Return a compact trend string like ' (^ +15.2% 24h)' for use in summary rows."""
    if not metrics_history:
        return ""
    windows = metrics_history.get("windows", {})
    window_data = windows.get("24h") or next(iter(windows.values()), None) if windows else None
    if not window_data or not window_data.get("metrics"):
        return ""
    m = window_data["metrics"].get(metric_name)
    if not m or "trend" not in m:
        return ""
    t = m["trend"]
    direction = t.get("direction", "stable")
    change = t.get("change_pct", 0)
    window_label = "24h" if "24h" in windows else next(iter(windows), "")
    arrow = {"increasing": "^", "decreasing": "v", "stable": "~"}.get(direction, "")
    if direction == "stable":
        return f" ({arrow} stable {window_label})"
    return f" ({arrow} {change:+.1f}% {window_label})"


def get_recent_logs(service: str, lines: int = LOG_LINES_DEFAULT,
                    environment_id: Optional[str] = None,
                    service_id: Optional[str] = None) -> List[str]:
    """Get recent logs for LLM analysis.

    Uses API if environment_id and service_id provided (~3s),
    retries once with longer timeout on failure,
    falls back to CLI (~27s for 100 lines).
    """
    # Fast path: use API directly
    if environment_id and service_id:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_script = os.path.join(script_dir, "railway-api.sh")

        if os.path.exists(api_script):
            # Use environmentLogs API with service filter
            query = f'''query {{
                environmentLogs(
                    environmentId: "{environment_id}",
                    beforeLimit: {lines},
                    filter: "@service:{service_id}"
                ) {{
                    timestamp
                    message
                }}
            }}'''
            # Try API twice: first with 15s timeout, retry with 30s
            for attempt_timeout in [15, 30]:
                try:
                    result = subprocess.run(
                        [api_script, query],
                        capture_output=True,
                        text=True,
                        timeout=attempt_timeout
                    )
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        logs_data = data.get("data", {}).get("environmentLogs", [])
                        if logs_data:
                            return [f"{log['timestamp']} {log['message']}" for log in logs_data]
                except (subprocess.TimeoutExpired, json.JSONDecodeError):
                    pass

    # Fallback: use CLI (slow, ~27s)
    code, stdout, stderr = run_railway_command(
        ["logs"] + _ctx.logs_flags() + ["--service", service, "--lines", str(lines)],
        timeout=30
    )
    if code != 0:
        return []

    logs = []
    for line in stdout.strip().split("\n"):
        if line.strip():
            logs.append(line.strip())
    return logs
