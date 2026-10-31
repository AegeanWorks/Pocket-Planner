# Pocket Planner

[![Built with AIKit](https://img.shields.io/badge/built%20with-AIKit-6f42c1)](https://github.com/AegeanWorks/AIKit)

A local-first task manager for capturing, prioritizing, and completing work from a fast terminal workflow.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10+; standard library only.
- **Canonical Regression Shield Gate**:
  ```bash
  python -m unittest discover -s tests -p "test_*.py"
  ```

### Usage

Run these commands from this directory:

```bash
python pocket_planner.py add "Write project brief" --priority 1
python pocket_planner.py add "Review pull request" --priority 2 --due 2026-11-02 --tag work --tag review
python pocket_planner.py list
python pocket_planner.py list --tag work
python pocket_planner.py list --overdue
python pocket_planner.py done 1
python pocket_planner.py list --all
```

Tasks are stored in `.pocket-planner.json` in the current directory. Use `--file path/to/tasks.json` to select another store. Tasks support priorities, ISO due dates, and repeatable tags. Writes use a temporary file, `fsync`, and atomic replacement so an interrupted write does not leave a partial database.

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status pocket-planner` |
| Phase 4: every gate | `python aikit.py check pocket-planner` |
| Repair memory and map, then check | `python aikit.py fix pocket-planner` |
| Resume an interrupted task | `python aikit.py resume pocket-planner` |

## 📦 What's Inside

```text
pocket-planner/
├── .gitignore                <- transient AIKit state excluded
├── LICENSE                   <- Aegean License 1.1 (AL-1.1): free personal use
├── COMMERCIAL.md             <- Commercial licensing terms
├── LICENSES/                 <- REUSE license texts
├── REUSE.toml                <- Machine-readable SPDX metadata
├── README.md
├── pocket_planner.py         <- task store and CLI
├── tests/
    └── test_pocket_planner.py
└── .aikit/                   <- this project's memory: record, ledger, decisions
```

## 📜 License

Free for personal use under the Aegean License 1.1 (AL-1.1); see [LICENSE](LICENSE). Any commercial use needs the Aegean Commercial License 1.0 (ACL-1.0); see [COMMERCIAL.md](COMMERCIAL.md).
