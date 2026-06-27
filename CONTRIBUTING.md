# Contributing to NextGen Energy Suite ⚡

Thank you for considering contributing! Every pull request, bug report, and feature idea helps make this project better.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

---

## Code of Conduct

Be respectful, constructive, and professional. We welcome contributors of all backgrounds and skill levels.

---

## How to Contribute

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/nextgen-energy-suite.git
   ```
3. **Create** a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make** your changes
5. **Test** that all three modules run without errors:
   ```bash
   python b2b_energy_optimizer.py
   python microgrid_p2p_trader.py
   python ev_fleet_smart_charger.py
   ```
6. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add PVGIS solar forecast integration to Module 1"
   ```
7. **Push** and open a Pull Request

---

## Development Setup

```bash
# Python 3.10+ required
python --version

# Install Module 1 dependencies
pip install pandas numpy

# Modules 2 & 3 need no external packages
```

---

## Code Style

- **PEP 8** with 4-space indentation
- **Type hints** on all function signatures (Python 3.10+ syntax)
- **Docstrings** on all classes and public functions
- **Constants** in `UPPER_SNAKE_CASE` at file top
- **No magic numbers** — name every threshold/rate as a constant
- Line width: **88 characters** (Black formatter default)
- Module docstring at top with Problem / Solution / Algorithm / Dependencies / Run

---

## Submitting a Pull Request

- Keep PRs focused on a single feature or fix
- Update `CHANGELOG.md` under `[Unreleased]`
- Update `README.md` if you add/change user-facing behaviour
- All three modules must still run successfully after your changes

---

## Reporting Bugs

Open a GitHub Issue with:
- Python version (`python --version`)
- OS and terminal encoding
- The full error traceback
- Steps to reproduce

---

## Suggesting Features

Open a GitHub Issue labelled `enhancement` with:
- The energy domain problem you want to solve
- Which module it belongs to (or is it a new module?)
- Any relevant academic papers or industry standards

---

We look forward to your contribution! ⚡
