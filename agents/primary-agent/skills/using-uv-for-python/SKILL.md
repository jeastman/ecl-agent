---
name: using-uv-for-python
description: Use when creating Python scripts or executing Python code—default to uv run for execution and PEP 723 for script dependencies
---

# Using uv for Python

## Overview

**`uv` is the default tool for all Python execution.** Use `uv run` for script execution and PEP 723 inline dependencies for new scripts. This replaces traditional `pip` + `python` workflows.

**Why uv?**
- Single tool for dependencies, execution, and virtual environments
- PEP 723 inline dependency declarations mean no separate `requirements.txt`
- Faster than pip
- Scripts are self-contained and portable
- Shebang support for direct execution: `./script.py`

## When to Use

Any time you:
- Execute Python code or scripts
- Create a Python script for use as a tool
- Need to run Python with dependencies
- Would normally use `pip install` + `python script.py`

**NOT when:**
- Working with existing projects that use `pip`/`poetry`/`pipenv` (respect their tooling)
- Writing code for Python packages (use the project's package manager)

## Creating uv Scripts

All new Python scripts should use PEP 723 inline dependencies.

### Minimal Example
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///

import requests

response = requests.get("https://api.example.com/data")
data = response.json()
print(data)
```

**Key parts:**
- Shebang: `#!/usr/bin/env python3`
- Script metadata block between `# ///` lines (PEP 723 format)
- `requires-python`: minimum Python version
- `dependencies`: list of required packages with version specs

### Execution

```bash
# Recommended: Let uv manage everything
uv run script.py

# After making executable (chmod +x)
./script.py

# Traditional (not recommended, but works)
python script.py
```

On first run, `uv run` automatically creates a virtual environment, installs dependencies, and executes the script.

## Common Patterns

### With Click CLI Library
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "click>=8.1.0",
# ]
# ///

import click

@click.command()
@click.option('--name', default='World', help='Name to greet.')
def hello(name):
    click.echo(f'Hello {name}!')

if __name__ == '__main__':
    hello()
```

### With Multiple Dependencies
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pandas>=2.0.0",
#     "numpy>=1.24.0",
#     "requests>=2.28.0",
# ]
# ///
```

### With Optional Dependencies
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests>=2.28.0",
#     "lxml>=4.9.0 ; extra == 'parsing'",
# ]
# ///
```

## Quick Reference

| Task | Command |
|------|---------|
| Execute script | `uv run script.py` |
| Execute with args | `uv run script.py --flag value` |
| Make executable | `chmod +x script.py` then `./script.py` |
| Check uv installed | `uv --version` |
| Install uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

## Common Mistakes

### ❌ Using pip
```python
# Wrong: Creates separate requirements.txt
# $ pip install requests
# $ python script.py
```

**Fix:** Use PEP 723 inline dependencies with `uv run`

### ❌ Missing shebang
```python
# Wrong: No shebang line
import requests
```

**Fix:** Always start with `#!/usr/bin/env python3`

### ❌ Wrong PEP 723 syntax
```python
# Wrong: Comments outside block
# dependencies = ["requests"]

# /// script
# requires-python = ">=3.9"
# ///
```

**Fix:** Dependencies must be inside `# ///` block with proper indentation

### ❌ Version specs too loose
```python
# Risky: "requests" with no version
dependencies = [
    "requests",  # Could break with major version bump
]
```

**Fix:** Always pin minimum version: `"requests>=2.28.0"`

## Red Flags — STOP if You're Doing This

These patterns mean you should use `uv`:
- Creating new Python scripts → Use PEP 723 + `uv run`
- Writing "pip install requests" → Use PEP 723 instead
- Managing script dependencies with `requirements.txt` → Use PEP 723
- Defaulting to `python script.py` → Use `uv run script.py`

**All of these should trigger: Use uv for this Python work.**

## Real-World Reference

**PEP 723 Official Spec:**
https://peps.python.org/pep-0723/

**uv Documentation:**
https://docs.astral.sh/uv/

**uv Scripts Guide:**
https://docs.astral.sh/uv/guides/scripts/
