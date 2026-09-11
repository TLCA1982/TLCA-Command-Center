from __future__ import annotations

import importlib
import os
import unittest


class DatabaseEngineConfigTests(unittest.TestCase):
    def _reload_db_module(self):
        from app import config as config_module
        from app import db as db_module

        config_module.get_settings.cache_clear()
        return importlib.reload(db_module)

    def setUp(self) -> None:
        self._original_environ = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._original_environ)
        self._reload_db_module()

    def test_postgresql_engine_uses_conservative_pool_settings(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql+psycopg://user:pass@localhost:5432/example"
        os.environ["DATABASE_BACKEND"] = "postgresql"

        db_module = self._reload_db_module()

        self.assertTrue(db_module.is_postgresql())
        self.assertTrue(db_module.engine.pool._pre_ping)
        self.assertEqual(db_module.engine.pool._recycle, 300)

    def test_sqlite_engine_is_unchanged(self) -> None:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("DATABASE_BACKEND", None)

        db_module = self._reload_db_module()

        self.assertTrue(db_module.is_sqlite())
        self.assertFalse(db_module.engine.pool._pre_ping)
        self.assertEqual(db_module.engine.pool._recycle, -1)


if __name__ == "__main__":
    unittest.main()
