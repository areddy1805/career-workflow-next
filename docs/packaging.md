# Packaging & Installation Guide

This document outlines the packaging architecture and installation procedures for the Career Workflow project.

## 1. Project Layout

The project uses an "application layout", placing multiple independent service directories at the root:

```
career-workflow-next/
├── api/             # FastAPI Control Plane
├── control_center/  # Core Backend Services & Runner
├── src/             # Main Pipeline Logic & CLI
├── tools/           # Developer Utilities
├── pyproject.toml
└── ...
```

Unlike traditional PyPI libraries that bundle everything under a single namespace (e.g., `career_workflow/`), this project treats `api`, `control_center`, `src`, and `tools` as top-level Python packages. This is common in microservices and web application repositories.

## 2. Package Discovery (setuptools)

Because of the application layout, Python's standard package discovery (which expects a `src/<project_name>` structure) will fail. 

To resolve this, our `pyproject.toml` is configured using **PEP 517/518 (`setuptools.build_meta`)** and explicitly discovers our top-level packages:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
```

This configuration ensures that when the project is installed, all these directories are successfully discovered and linked into the Python virtual environment's `site-packages` automatically (provided they contain `__init__.py` or are valid packages).

## 3. Entry Point Generation

We declare the Unified Operations CLI (`cw`) as a console script in `pyproject.toml`:

```toml
[project.scripts]
cw = "src.cli.main:app"
```

When you run `pip install -e .`, `setuptools` automatically generates a highly reliable `cw` executable wrapper in your virtual environment's `bin/` directory (`.venv/bin/cw`).

This generated executable automatically binds the virtual environment and manages `sys.path` correctly, eliminating the need for `sys.path.insert()` hacks or bash wrappers.

## 4. Installation Procedure

To install the project in an editable ("develop") mode:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install the project in editable mode
pip install -e .
```

After installation, the `cw` command will be available globally on your system (as long as the virtual environment is activated), regardless of your Current Working Directory (CWD).

## 5. Troubleshooting

**Error: `ModuleNotFoundError: No module named 'src'` when running `cw`**

- **Cause**: The project was likely installed without a proper `[build-system]` or before package discovery was configured. Thus, `pip` created a dummy package and did not map the `src/` directory.
- **Fix**: Completely uninstall the broken package and reinstall:
  ```bash
  pip uninstall -y career-workflow
  pip install -e .
  ```

**Error: `command not found: cw`**

- **Cause**: The virtual environment is either not activated, or the installation failed.
- **Fix**: Ensure your virtual environment is active (`source .venv/bin/activate`) and run `pip install -e .` again. You can verify the executable exists at `.venv/bin/cw`.
