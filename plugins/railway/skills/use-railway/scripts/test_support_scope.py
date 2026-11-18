#!/usr/bin/env python3
"""Support-scope rules the analysis scripts share (run: python3 scripts/test_support_scope.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dal import (  # noqa: E402
    SUPPORT_SCOPE_DOCS,
    apply_support_scope,
    is_in_scope_command,
    is_official_database_image,
)

MANAGED = {"managed": True, "image": "ghcr.io/railwayapp-templates/postgres-ssl:17", "docs": SUPPORT_SCOPE_DOCS}
CUSTOM = {"managed": False, "image": "pgvector/pgvector:pg17", "docs": SUPPORT_SCOPE_DOCS}


class OfficialImage(unittest.TestCase):
    def test_railway_built_and_template_docker_hub_images_are_official(self):
        for image in [
            "ghcr.io/railwayapp-templates/postgres-ssl:17",
            "ghcr.io/railwayapp-templates/postgres-ha/postgres-patroni:17",
            "ghcr.io/railwayapp-templates/mysql-ha/mysql:8.4",
            "ghcr.io/railway/postgres:16",
            "mysql:9.4", "docker.io/library/mysql:8.4",
            "redis:8.2.1", "bitnami/redis:7.2.5", "railwayapp/redis:8.2.1",
            "mongo:8", "docker.io/library/mongo:7",
        ]:
            self.assertTrue(is_official_database_image(image), image)

    def test_custom_images_and_unknowns_are_not(self):
        for image in [
            "pgvector/pgvector:pg17", "timescale/timescaledb:latest-pg16",
            "postgres:16", "mariadb:11", "valkey/valkey:8",
            "ghcr.io/other-org/mysql:9", "quay.io/railwayapp-templates/postgres-ssl:17",
            "", None,
        ]:
            self.assertFalse(is_official_database_image(image), image)


class CommandAllowlist(unittest.TestCase):
    def test_the_users_domain_stays(self):
        for cmd in [
            "VACUUM ANALYZE \"users\";", "CREATE INDEX CONCURRENTLY ix ON t (a);",
            "DROP INDEX CONCURRENTLY IF EXISTS ix;", "SELECT pg_cancel_backend(42);",
            "SELECT pg_terminate_backend(42);", "ALTER TABLE t SET (autovacuum_vacuum_scale_factor = 0.05);",
            "EXPLAIN (ANALYZE) SELECT 1;", "-- a comment", "OPTIMIZE TABLE t;", "KILL 42;",
            "SCAN 0 COUNT 100", "CONFIG GET maxmemory",
            "db.orders.createIndex({ customerId: 1 })", "db.killOp(42)",
        ]:
            self.assertTrue(is_in_scope_command(cmd), cmd)

    def test_configuration_is_out(self):
        for cmd in [
            "ALTER SYSTEM SET shared_buffers = '1GB';", "SELECT pg_reload_conf();  -- after ALTER SYSTEM" if False else "ALTER ROLE app SUPERUSER;",
            "CREATE EXTENSION pg_stat_statements;", "CREATE ROLE reporter;", "SET GLOBAL max_connections = 500;",
            "SET PERSIST innodb_buffer_pool_size = 1073741824;", "CONFIG SET activedefrag yes",
            "db.adminCommand({ setParameter: 1, maxIncomingConnections: 2000 })",
            "railway variable set POSTGRES_SHARED_BUFFERS=1GB", "railway restart --service db --yes",
        ]:
            self.assertFalse(is_in_scope_command(cmd), cmd)


class ApplyScope(unittest.TestCase):
    def test_custom_image_keeps_everything(self):
        recs = [{"priority": "immediate", "issue": "x", "action": "ALTER", "scope": "config",
                 "commands": ["ALTER SYSTEM SET work_mem = '32MB';"]}]
        self.assertEqual(apply_support_scope(recs, CUSTOM), recs)
        self.assertEqual(apply_support_scope(recs, None), recs)

    def test_config_finding_on_a_managed_database_loses_its_remedy(self):
        recs = [{"priority": "immediate", "issue": "work_mem is 4MB", "action": "Increase work_mem to 32MB",
                 "scope": "config", "setting": "work_mem", "in_scope": "Index the ORDER BY columns.",
                 "commands": ["ALTER SYSTEM SET work_mem = '32MB';", "SELECT pg_reload_conf();"],
                 "restart_required": False}]
        [rec] = apply_support_scope(recs, MANAGED)
        self.assertEqual(rec["support_scope"], "outside")
        self.assertEqual(rec["priority"], "info")
        self.assertNotIn("commands", rec)
        self.assertNotIn("restart_required", rec)
        self.assertIn("changing work_mem", rec["action"])
        self.assertIn(SUPPORT_SCOPE_DOCS, rec["action"])
        self.assertIn("Index the ORDER BY columns.", rec["action"])
        self.assertEqual(rec["issue"], "work_mem is 4MB")

    def test_message_style_finding_is_rewritten_from_its_observation(self):
        recs = [{"severity": "critical", "observation": "Buffer pool hit ratio at 90%.",
                 "remedy": "Increase innodb_buffer_pool_size.", "scope": "config",
                 "setting": "innodb_buffer_pool_size", "in_scope": "Add indexes.",
                 "message": "Buffer pool hit ratio at 90%. Increase innodb_buffer_pool_size."}]
        [rec] = apply_support_scope(recs, MANAGED)
        self.assertTrue(rec["message"].startswith("Buffer pool hit ratio at 90%. Outside Railway support scope"))
        self.assertNotIn("Increase innodb_buffer_pool_size", rec["message"])
        self.assertEqual(rec["severity"], "info")

    def test_mixed_commands_keep_only_the_in_scope_ones(self):
        recs = [{"priority": "immediate", "issue": "idle txn", "action": "Terminate it",
                 "commands": ["SELECT pg_terminate_backend(7);  -- Kill this connection",
                              "-- Prevent it next time:",
                              "ALTER SYSTEM SET idle_in_transaction_session_timeout = '5min';"]}]
        [rec] = apply_support_scope(recs, MANAGED)
        self.assertEqual(rec["commands"], ["SELECT pg_terminate_backend(7);  -- Kill this connection"])
        self.assertEqual(rec["commands_outside_scope"], 1)
        self.assertEqual(rec["support_scope"], "partial")
        self.assertEqual(rec["priority"], "immediate")

    def test_keep_priority_is_honoured(self):
        recs = [{"priority": "immediate", "issue": "autovacuum off", "action": "turn on",
                 "scope": "config", "setting": "autovacuum", "keep_priority": True,
                 "commands": ["ALTER SYSTEM SET autovacuum = on;"]}]
        [rec] = apply_support_scope(recs, MANAGED)
        self.assertEqual(rec["priority"], "immediate")
        self.assertNotIn("commands", rec)


if __name__ == "__main__":
    unittest.main()
