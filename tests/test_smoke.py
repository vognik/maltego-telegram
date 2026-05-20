from pathlib import Path


def test_project_structure_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "project.py").is_file()
    assert (root / "transforms").is_dir()
