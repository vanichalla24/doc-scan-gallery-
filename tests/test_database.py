"""Unit tests for the database manager."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        import app.database.db_manager as _db_mod  # ensure module imported before patching
        self._tmp = tempfile.mkdtemp()
        self._db_path = Path(self._tmp) / "test.db"
        self._patch = patch.object(_db_mod, "DB_PATH", self._db_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_initialize_and_save_run(self):
        from app.database import db_manager
        db_manager.initialize_database()

        run_data = {
            "run_id": "test-run-001",
            "root_folder": "/tmp/test",
            "source_language": "English",
            "target_language": "Korean",
            "engines": ["Google", "Papago"],
            "status": "completed",
            "scoring_weights": {},
            "start_time": "2024-01-01T00:00:00",
            "total_images": 10,
            "processed_images": 10,
            "average_score": 82.5,
            "pass_rate": 80.0,
        }
        db_manager.save_run(run_data)
        runs = db_manager.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], "test-run-001")

    def test_save_and_get_image_result(self):
        from app.database import db_manager
        db_manager.initialize_database()

        db_manager.save_run({
            "run_id": "run-img-test",
            "root_folder": "/tmp",
            "source_language": "English",
            "target_language": "Korean",
            "engines": ["Google"],
            "status": "completed",
        })

        db_manager.save_image_result({
            "run_id": "run-img-test",
            "engine": "Google",
            "image_name": "image001.png",
            "original_path": "/tmp/orig/image001.png",
            "translated_path": "/tmp/Google/image001.png",
            "overall_score": 88.5,
            "score_band": "Good",
            "parameter_scores": {"ocr_accuracy": {"score": 90}},
            "issues": ["Minor blur detected"],
        })

        results = db_manager.get_image_results("run-img-test")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["image_name"], "image001.png")
        self.assertAlmostEqual(results[0]["overall_score"], 88.5)

    def test_save_and_load_settings(self):
        from app.database import db_manager
        db_manager.initialize_database()

        db_manager.save_setting("theme", "light")
        db_manager.save_setting("parallel_workers", 8)

        self.assertEqual(db_manager.load_setting("theme"), "light")
        self.assertEqual(db_manager.load_setting("parallel_workers"), 8)
        self.assertIsNone(db_manager.load_setting("nonexistent"))
        self.assertEqual(db_manager.load_setting("nonexistent", "default"), "default")

    def test_delete_run(self):
        from app.database import db_manager
        db_manager.initialize_database()

        db_manager.save_run({
            "run_id": "del-run",
            "root_folder": "/tmp",
            "source_language": "English",
            "target_language": "Korean",
            "engines": ["Google"],
            "status": "completed",
        })
        db_manager.delete_run("del-run")
        self.assertIsNone(db_manager.get_run("del-run"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
