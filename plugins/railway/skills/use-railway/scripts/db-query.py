#!/usr/bin/env python3
"""
Safe database query wrapper for Railway services.

Handles SSH complexity, escaping, and pager issues automatically.
Supports preset queries for common analysis tasks.

Usage:
    db-query.py --service <name> --type postgres --preset connections
    db-query.py --service <name> --type postgres --query "SELECT 1;"
    db-query.py --domain <domain> --type redis --query "INFO memory"
"""

import argparse
import re
import subprocess
import sys
import shlex
from typing import Optional, Dict, List

# Preset queries for common analysis tasks
POSTGRES_PRESETS: Dict[str, str] = {
    "connections": "SELECT state, count(*) FROM pg_stat_activity GROUP BY state ORDER BY count DESC",
    "connection_pool": """
        SELECT
            (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as current_connections,
            (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections
    """,
    "db_sizes": "SELECT datname, pg_size_pretty(pg_database_size(datname)) as size FROM pg_database ORDER BY pg_database_size(datname) DESC LIMIT 5",
    "table_sizes": "SELECT relname AS table_name, pg_size_pretty(pg_total_relation_size(relid)) AS total_size FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 15",
    "cache_hit": """
        SELECT
            ROUND(100.0 * sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as table_cache_hit_pct,
            ROUND(100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2) as index_cache_hit_pct
        FROM pg_statio_user_tables
    """,
    "cache_per_table": """
        SELECT
            relname as table_name,
            heap_blks_read as disk_reads,
            heap_blks_hit as cache_hits,
            ROUND(100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0), 2) as hit_pct
        FROM pg_statio_user_tables
        WHERE heap_blks_read + heap_blks_hit > 1000
        ORDER BY heap_blks_read DESC LIMIT 15
    """,
    "memory_settings": """
        SELECT name, setting, unit,
            CASE
                WHEN unit = '8kB' THEN (setting::bigint * 8 / 1024)::text || ' MB'
                WHEN unit = 'kB' THEN (setting::bigint / 1024)::text || ' MB'
                ELSE setting || ' ' || COALESCE(unit, '')
            END as human_readable
        FROM pg_settings
        WHERE name IN ('shared_buffers', 'effective_cache_size', 'work_mem', 'maintenance_work_mem', 'max_connections')
    """,
    "vacuum_health": """
        SELECT
            schemaname,
            relname as table_name,
            n_live_tup as live_rows,
            n_dead_tup as dead_rows,
            CASE WHEN n_live_tup > 0 THEN ROUND(100.0 * n_dead_tup / n_live_tup, 2) ELSE 0 END as dead_pct,
            last_autovacuum::date,
            last_vacuum::date
        FROM pg_stat_user_tables
        WHERE n_dead_tup > 100
        ORDER BY n_dead_tup DESC LIMIT 15
    """,
    "xid_age": """
        SELECT
            datname,
            age(datfrozenxid) as xid_age,
            ROUND(age(datfrozenxid)::numeric / 2147483647 * 100, 2) as pct_to_wraparound
        FROM pg_database
        WHERE datname = current_database()
    """,
    "top_queries": """
        SELECT
            left(query, 80) as query,
            calls,
            ROUND(total_exec_time::numeric/1000/60, 1) as total_min,
            ROUND(mean_exec_time::numeric, 1) as mean_ms,
            rows
        FROM pg_stat_statements s
        JOIN pg_database d ON s.dbid = d.oid
        WHERE d.datname = current_database()
        ORDER BY total_exec_time DESC LIMIT 12
    """,
    "long_queries": """
        SELECT
            pid,
            now() - pg_stat_activity.query_start AS duration,
            left(query, 60) as query
        FROM pg_stat_activity
        WHERE state = 'active'
            AND now() - pg_stat_activity.query_start > interval '5 seconds'
        ORDER BY duration DESC
    """,
    "locks": """
        SELECT
            l.locktype,
            l.mode,
            a.usename,
            left(a.query, 50) as query
        FROM pg_locks l
        JOIN pg_stat_activity a ON l.pid = a.pid
        WHERE a.datname = current_database() AND NOT l.granted
        LIMIT 10
    """,
    "unused_indexes": """
        SELECT
            s.relname as table_name,
            s.indexrelname as index_name,
            pg_size_pretty(pg_relation_size(s.indexrelid)) as index_size,
            s.idx_scan as scans
        FROM pg_stat_user_indexes s
        WHERE s.idx_scan = 0 AND pg_relation_size(s.indexrelid) > 8192
        ORDER BY pg_relation_size(s.indexrelid) DESC LIMIT 15
    """,
    "seq_scans": """
        SELECT
            relname as table_name,
            seq_scan,
            idx_scan,
            n_live_tup as rows
        FROM pg_stat_user_tables
        WHERE seq_scan > 100 AND n_live_tup > 1000
        ORDER BY seq_scan DESC LIMIT 10
    """,
    "replication": "SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn FROM pg_stat_replication",
}

REDIS_PRESETS: Dict[str, str] = {
    "info": "INFO",
    "memory": "INFO memory",
    "clients": "INFO clients",
    "replication": "INFO replication",
    "keyspace": "INFO keyspace",
    "slowlog": "SLOWLOG GET 10",
    "persistence": "INFO persistence",
}

MYSQL_PRESETS: Dict[str, str] = {
    "processlist": "SHOW PROCESSLIST",
    "status": "SHOW STATUS",
    "buffer_pool": "SHOW STATUS LIKE 'Innodb_buffer_pool%'",
    "connections": "SELECT user, host, count(*) as conns FROM information_schema.processlist GROUP BY user, host",
    "db_sizes": """
        SELECT table_schema AS database_name,
               ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
        FROM information_schema.tables
        GROUP BY table_schema
        ORDER BY size_mb DESC
    """,
    "table_sizes": """
        SELECT table_name,
               ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        ORDER BY size_mb DESC LIMIT 20
    """,
}

MONGODB_PRESETS: Dict[str, str] = {
    "status": "db.serverStatus()",
    "connections": "db.serverStatus().connections",
    "current_ops": "db.currentOp()",
    "stats": "db.stats()",
    "rs_status": "rs.status()",
}

# Destructive keywords to block
DESTRUCTIVE_KEYWORDS = [
    "DELETE", "DROP", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "GRANT", "REVOKE", "FLUSHALL", "FLUSHDB", "SHUTDOWN", "SLAVEOF",
    "REPLICAOF", "CONFIG SET", "VACUUM", "REINDEX",
]


def get_presets(db_type: str) -> Dict[str, str]:
    """Get preset queries for a database type."""
    presets = {
        "postgres": POSTGRES_PRESETS,
        "redis": REDIS_PRESETS,
        "mysql": MYSQL_PRESETS,
        "mongodb": MONGODB_PRESETS,
    }
    return presets.get(db_type, {})


def list_presets():
    """Print all available presets."""
    print("Available presets:\n")
    for db_type, presets in [
        ("postgres", POSTGRES_PRESETS),
        ("redis", REDIS_PRESETS),
        ("mysql", MYSQL_PRESETS),
        ("mongodb", MONGODB_PRESETS),
    ]:
        print(f"=== {db_type} ===")
        for name in sorted(presets.keys()):
            print(f"  {name}")
        print()


def normalize_query(query: str) -> str:
    """Normalize a query by collapsing whitespace."""
    return " ".join(query.split())


def validate_query(query: str) -> None:
    """Check for destructive keywords."""
    query_upper = query.upper()
    for keyword in DESTRUCTIVE_KEYWORDS:
        # Use word boundary matching to avoid false positives
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, query_upper):
            print(f"Error: Query contains destructive keyword '{keyword}'.", file=sys.stderr)
            print("Blocked for safety. Run mutations manually via SSH with explicit user confirmation.", file=sys.stderr)
            sys.exit(1)


def build_postgres_command(query: str) -> str:
    """Build psql command with proper escaping and read-only mode."""
    # Normalize whitespace
    query = normalize_query(query)

    # Escape for shell
    # We use a heredoc approach to avoid complex escaping
    cmd = f'''PAGER='' psql $DATABASE_URL -P pager=off -c "SET default_transaction_read_only = on; {query}"'''
    return cmd


def build_redis_command(query: str) -> str:
    """Build redis-cli command."""
    return f"redis-cli {query}"


def build_mysql_command(query: str) -> str:
    """Build mysql command with read-only mode."""
    query = normalize_query(query)
    return f'''mysql -e "SET SESSION TRANSACTION READ ONLY; {query}"'''


def build_mongodb_command(query: str) -> str:
    """Build mongosh command with read preference."""
    return f'''mongosh --quiet --eval 'db.getMongo().setReadPref("secondary"); {query}' '''


def execute_via_railway_ssh(service: str, command: str, timeout: int = 60) -> int:
    """Execute command via railway ssh."""
    # Build the full command
    # We wrap in single quotes and escape any internal single quotes
    escaped_command = command.replace("'", "'\"'\"'")
    full_cmd = ["railway", "ssh", "--service", service, "--", f"sh -c '{escaped_command}'"]

    try:
        result = subprocess.run(
            full_cmd,
            timeout=timeout,
            capture_output=False,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"Error: Command timed out after {timeout}s", file=sys.stderr)
        return 124
    except FileNotFoundError:
        print("Error: railway CLI not found. Install with: npm i -g @railway/cli", file=sys.stderr)
        return 127


def execute_via_direct_ssh(domain: str, command: str, timeout: int = 60) -> int:
    """Execute command via direct SSH."""
    full_cmd = [
        "ssh",
        "-o", f"ConnectTimeout={timeout}",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{domain}@ssh.railway.com",
        command
    ]

    try:
        result = subprocess.run(
            full_cmd,
            timeout=timeout,
            capture_output=False,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"Error: SSH timed out after {timeout}s", file=sys.stderr)
        return 124


def main():
    parser = argparse.ArgumentParser(
        description="Query Railway database services safely via SSH.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --service core-postgres --type postgres --preset connections
  %(prog)s --service core-postgres --type postgres --query "SELECT count(*) FROM users;"
  %(prog)s --domain mydb.up.railway.app --type postgres --preset cache_hit
  %(prog)s --service my-redis --type redis --preset memory
  %(prog)s --list-presets
        """
    )

    parser.add_argument("--service", help="Service name (requires linked project)")
    parser.add_argument("--domain", help="Service domain (e.g., myapp.up.railway.app)")
    parser.add_argument("--type", dest="db_type", choices=["postgres", "redis", "mysql", "mongodb"],
                       help="Database type")
    parser.add_argument("--query", help="Custom query to execute")
    parser.add_argument("--preset", help="Use a preset query")
    parser.add_argument("--timeout", type=int, default=60, help="SSH timeout in seconds (default: 60)")
    parser.add_argument("--list-presets", action="store_true", help="List available preset queries")

    args = parser.parse_args()

    # Handle --list-presets
    if args.list_presets:
        list_presets()
        return 0

    # Validate required arguments
    if not args.service and not args.domain:
        parser.error("Either --service or --domain is required")

    if not args.db_type:
        parser.error("--type is required")

    if not args.query and not args.preset:
        parser.error("Either --query or --preset is required")

    # Resolve preset to query
    query = args.query
    if args.preset:
        presets = get_presets(args.db_type)
        if args.preset not in presets:
            print(f"Error: Unknown preset '{args.preset}' for type '{args.db_type}'.", file=sys.stderr)
            print("Use --list-presets to see available presets.", file=sys.stderr)
            return 1
        query = presets[args.preset]

    # Validate query
    validate_query(query)

    # Build database-specific command
    if args.db_type == "postgres":
        command = build_postgres_command(query)
    elif args.db_type == "redis":
        command = build_redis_command(query)
    elif args.db_type == "mysql":
        command = build_mysql_command(query)
    elif args.db_type == "mongodb":
        command = build_mongodb_command(query)
    else:
        print(f"Error: Unsupported database type: {args.db_type}", file=sys.stderr)
        return 1

    # Execute
    if args.service:
        return execute_via_railway_ssh(args.service, command, args.timeout)
    else:
        return execute_via_direct_ssh(args.domain, command, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
