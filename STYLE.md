# Python Style Guide

**Status:** Preferred conventions for Python code authored, reviewed, or generated for this repository.  
**Priority:** Readability, explicit contracts, modularity, testability, and predictable execution over cleverness or brevity.

This guide is intentionally more explicit than PEP 8. Follow PEP 8 and PEP 257 where they do not conflict with the rules below. Match existing project conventions when integration demands it, and document material exceptions instead of silently inventing a second style.

## 1. Non-negotiable conventions

1. **Document every function and method parameter, and every return value.** This applies to public and internal functions, constructors, classmethods, staticmethods, test helpers, and nested helpers when they are substantial enough to exist. Include what an argument *means*, relevant units, constraints, defaults, mutation, and what is returned. Do not merely repeat the type annotation. Document exceptions when callers need to understand them.
2. **Type every function parameter and return value.** Also **annotate local variables when they are declared**, even when inference would be trivial. Explicit is preferred over compact. Include test code in this policy.
3. **Use `argparse` for CLIs, and materialize parsed arguments into typed `@dataclass` instances.** `argparse.Namespace` must not leak into application logic. Use separate argument dataclasses for meaningfully different subcommands.
4. **Separate entry points, CLI parsing, orchestration, business logic, and I/O.** `__main__.py` and executable wrappers must be thin. A `main()` function should parse, call a separately testable `run(arguments)`, and turn its result into an exit code.
5. **Keep modules short and cohesive.** Separate unrelated functions and classes into logical files and packages; do not let a script grow into a thousand-line junk drawer. Do not fragment one coherent component into dozens of useless one-function files either.
6. **Prefer readable, unsurprising standard-library solutions** before adding dependencies or elaborate abstraction layers. Dataclasses, `pathlib`, `argparse`, `logging`, `typing`, and ordinary functions cover an enormous amount of ground.
7. **Use structured logging for operational output.** Reserve `print()` for intentional CLI output to the user or structured stdout contracts. Keep libraries silent by default.
8. **Make errors explicit and actionable.** Raise meaningful exceptions; preserve causes with `raise ... from exc`; do not silently swallow failures or substitute fabricated defaults.
9. **Write tests for behavior, failure paths, boundaries, and regressions**, not just the happy path or incidental implementation details.

## 2. Project and package organization

Organize by responsibility, not arbitrary file count. A typical CLI package looks like this:

```text
project/
├── pyproject.toml
├── src/
│   └── hydro_tool/
│       ├── __init__.py
│       ├── __main__.py       # python -m hydro_tool; dispatch only
│       ├── cli.py            # ArgumentParser and typed argument conversion
│       ├── config.py         # Validated dataclasses and configuration
│       ├── application.py    # run(args): orchestration and exit result
│       ├── domain/           # Domain models and pure business rules
│       │   ├── __init__.py
│       │   └── calculations.py
│       └── io/               # External systems, readers, writers, adapters
│           ├── __init__.py
│           └── records.py
└── tests/
    ├── test_cli.py
    ├── test_application.py
    └── test_calculations.py
```

- **One responsibility per module** and a clear public API. If unrelated features accumulate or navigation becomes painful, split the module.
- Keep complex classes and their helpers together only while they remain cohesive; move independent classes, parsing, validation, or I/O into separate modules.
- Avoid circular imports by keeping dependencies pointed inward: entry point → CLI/application → domain interfaces; infrastructure implements the I/O edges.
- Use absolute imports between package modules unless local relative imports are distinctly clearer.
- Separate data models from serialization, parsing, storage, and transport. Avoid objects that represent the configuration, parse the CLI, perform the work, and write the results all at once.
- Do not introduce a premature plugin framework, service locator, generic base class, or design-pattern ceremony to solve a small local problem.

**Size heuristic, not a hard rule:** review any module approaching roughly 300–500 lines, especially if it mixes multiple responsibilities. A single well-defined cohesive component may legitimately be larger. The goal is maintainability, not gaming a line-count metric.

## 3. Type annotations everywhere

Use `from __future__ import annotations` in contemporary Python modules, subject to supported Python versions and libraries that inspect annotations at runtime.

```python
from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator, Mapping

DEFAULT_LIMIT: int = 100


def find_records(directory: Path, minimum_size: int) -> list[Path]:
    """Locate qualifying files under a directory.

    :param directory: Root directory to search recursively.
    :param minimum_size: Minimum accepted file size, in bytes; must be nonnegative.
    :return: Paths to qualifying files, sorted lexicographically.
    :raises ValueError: If `minimum_size` is negative.

    TODO(AI-GENERATED): Review and rewrite this generated example before reuse.
    """
    if minimum_size < 0:
        raise ValueError("minimum_size must be nonnegative")

    candidates: Iterator[Path] = directory.rglob("*")
    accepted: list[Path] = [
        path for path in candidates if path.is_file() and path.stat().st_size >= minimum_size
    ]
    result: list[Path] = sorted(accepted)
    return result
```

- Annotate **variables at declaration**, even for seemingly obvious literals: `count: int = 0`, `names: list[str] = []`, `mapping: dict[str, int] = {}`, `path: Path = Path(value)`.
- Do not annotate the same variable repeatedly on reassignment; annotate it when introduced.
- Favor precise collection and protocol types: `Mapping[str, float]` for read-only mapping requirements, `Sequence[T]` when indexing is needed, `Iterable[T]` for single-pass consumption, `Iterator[T]` for generators.
- Prefer modern built-in generics (`list[str]`, `dict[str, int]`) and `T | None` where supported. Use `Any` only when the actual contract cannot reasonably be expressed, not as a shortcut.
- Define type aliases for genuinely complex signatures; avoid aliases that hide simple types.
- Explicitly annotate exceptions, loops' important intermediate values, NumPy/Polars expressions, and test fixtures when it improves visibility. For loop-bound variables, `for item in items` is sufficient when typing a loop target separately would produce awkward code; the strict declaration rule applies to explicit assignments and initialized locals.
- Do not replace type hints with pervasive runtime `isinstance()` checks. Validate at external boundaries, then work with trusted typed domain objects internally.
- Prefer `Enum`/`Literal` for constrained values when they meaningfully improve clarity; avoid magic strings sprinkled across modules.

## 4. Docstrings: complete contracts, not decoration

Use PEP 257-style triple-quoted docstrings. **Prefer Sphinx/reStructuredText fields** (`:param:`, `:return:`, `:raises:`) consistently throughout a repository. An existing codebase's established NumPy/Google convention can take precedence, but its content requirements cannot be dropped.

Every function or method must document:

- **Purpose:** What it does and why a caller would use it.
- **Every explicit input argument:** Each argument by name, semantics, constraints, relevant units, accepted special values, and mutation/ownership behavior. For instance methods, omit boilerplate `self` and `cls` where these are implicit receivers, not user-supplied inputs.
- **Every return:** Meaning, shape, units, order, ownership, and meaningful special cases. For a `None`-returning procedure, explicitly say `:return: None; the operation performs ...`.
- **Important errors:** Document meaningful exceptions and when they occur, including parser/validation errors at an external boundary.
- **Side effects:** Filesystem changes, remote calls, logging, database writes, or mutations that are not obvious from the signature.

```python
def normalize_flow(flow: float, basin_area_km2: float) -> float:
    """Convert streamflow into discharge per unit drainage area.

    :param flow: Streamflow in cubic meters per second.
    :param basin_area_km2: Upstream drainage area in square kilometers; must be positive.
    :return: Specific discharge in cubic meters per second per square kilometer.
    :raises ValueError: If `basin_area_km2` is zero or negative.

    TODO(AI-GENERATED): Verify units and behavior before adopting this code.
    """
    if basin_area_km2 <= 0.0:
        raise ValueError("basin_area_km2 must be positive")
    result: float = flow / basin_area_km2
    return result
```

- Write module docstrings describing responsibility; class docstrings describing invariant, purpose, and salient fields; dataclass fields should use descriptive names and use field metadata/docs or class docstrings when field meaning is not obvious.
- Avoid useless tautologies (`:param name: The name`) and mechanically generated walls of prose. Documentation must explain the contract beyond restating annotations.
- Keep docstrings synchronized with code changes. A stale docstring is worse than an obviously missing one.
- Prefer comments that explain *why*, tradeoffs, numerical assumptions, and non-obvious interactions; avoid line-by-line narration of self-evident code.

### AI-generated code review marker

When AI authors or significantly rewrites code for this user, **include a `TODO(AI-GENERATED)` note in each generated module, class, and function docstring** so copied code is visibly awaiting human review/reimplementation. This marker is for generated code, not a demand to stigmatize human-authored code or retroactively add markers to existing code. Remove or replace it only as part of an actual human review. Examples throughout this guide deliberately carry these markers.

## 5. CLI architecture: argparse + dataclasses

Use standard-library `argparse` for command-line grammar, defaults, `--help`, argument validation, and subcommands. Translate it immediately into a strongly typed dataclass; never hand `Namespace` to domain logic. `argparse` handles presentation/parsing, the dataclass handles typed values and application-level invariant checks.

```python
# cli.py
"""Parse command-line input into typed application arguments.

TODO(AI-GENERATED): Review and rewrite this generated module before reuse.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Arguments:
    """Validated options for one execution of the application.

    :ivar input_path: Source file to process.
    :ivar output_path: Destination file to write.
    :ivar verbose: Whether to enable verbose diagnostics.

    TODO(AI-GENERATED): Review and rewrite this generated class before reuse.
    """

    input_path: Path
    output_path: Path
    verbose: bool = False


def parse_args(argv: Sequence[str] | None = None) -> Arguments:
    """Parse supplied CLI tokens into immutable, typed arguments.

    :param argv: Tokens excluding the executable name; `None` reads `sys.argv[1:]`.
    :return: Validated application arguments.
    :raises SystemExit: When argparse handles help or rejects malformed CLI input.

    TODO(AI-GENERATED): Review and rewrite this generated function before reuse.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Process a source file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_path", type=Path, help="Source file")
    parser.add_argument("output_path", type=Path, help="Destination file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    namespace: argparse.Namespace = parser.parse_args(argv)
    result: Arguments = Arguments(
        input_path=namespace.input_path,
        output_path=namespace.output_path,
        verbose=namespace.verbose,
    )
    return result
```

```python
# application.py
"""Run application operations without coupling to command-line parsing.

TODO(AI-GENERATED): Review and rewrite this generated module before reuse.
"""
from __future__ import annotations

from .cli import Arguments


def run(arguments: Arguments) -> int:
    """Execute one configured application invocation.

    :param arguments: Validated settings for this invocation.
    :return: Process exit status, with zero denoting success.

    TODO(AI-GENERATED): Replace the stub and review generated code before reuse.
    """
    # TODO(AI-GENERATED): Delegate to independently testable application services.
    return 0
```

```python
# __main__.py
"""Expose the package's minimal command-line entry point.

TODO(AI-GENERATED): Review and rewrite this generated module before reuse.
"""
from __future__ import annotations

from collections.abc import Sequence

from .application import run
from .cli import Arguments, parse_args


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments and dispatch the application.

    :param argv: CLI tokens excluding the program name; `None` reads the process CLI.
    :return: Exit code produced by the application.

    TODO(AI-GENERATED): Review and rewrite this generated function before reuse.
    """
    arguments: Arguments = parse_args(argv)
    result: int = run(arguments)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
```

**CLI-specific requirements:**

- For subcommands, give each command its own frozen/slotted dataclass and use a discriminated union or explicit dispatch. Avoid an enormous dataclass full of optional fields unrelated to the selected command.
- Use `pathlib.Path` for paths. Resolve or verify paths **only when necessary** and at the correct boundary; don't silently turn relative paths into absolute paths without reason.
- Use `argparse.ArgumentTypeError` for custom `type=` conversion failures and display valid choices in `--help` where appropriate. Prefer `nargs` for space-separated lists.
- `argparse` normally calls `SystemExit` on parser errors and help. If an embedded library or asynchronous context requires catchable parser errors, subclass/configure the parser to raise a dedicated exception rather than letting parsing terminate a host process. This is a deliberate exception to the ordinary CLI behavior.
- Validate settings after parsing with dataclass `__post_init__` or a dedicated validator where semantic constraints span fields. Keep validation reusable without invoking CLI parsing.
- Support `main(argv=...)` and direct `run(Arguments(...))` in tests without patching `sys.argv` or starting subprocesses.
- Prefer constructor keyword arguments for tests and programmatic invocations; do not force callers to manufacture fake CLI strings.
- Avoid parsing CLI options at module import time.

## 6. Functions, classes, and configuration

- Prefer **small composable functions** with explicit inputs and outputs; keep pure calculations separate from file/network/database operations.
- Use `@dataclass` for cohesive configuration and record-like data. Prefer `frozen=True, slots=True` for immutable value/configuration objects when compatibility allows.
- Do not turn a plain function into a class without state, lifecycle, or invariants to justify it.
- Avoid arbitrary dynamic attributes, global mutable state, monkey-patching, magic reflection, and abstraction just for abstraction's sake.
- Inject dependencies (filesystem abstraction, network client, logger, clock) where doing so improves deterministic tests; don't build an injection framework for a couple of arguments.
- Keep APIs explicit: distinguish transformation from mutation; document when iterables are exhausted or resources are owned/closed.
- Use `pathlib.Path` for filesystem paths and context managers for resources.
- Keep long-running processing memory-aware: stream/iterate/chunk large data when full materialization is unnecessary; document where a generator is consumed.

## 7. Naming, imports, and formatting

- Use `snake_case` for functions, modules, and variables; `PascalCase` for classes; `UPPER_SNAKE_CASE` for constants.
- Prefer descriptive, domain-relevant names to terse abbreviations; don't hide units (`area_km2`, `flow_m3_s`) or important semantics.
- Group imports as standard library, third-party, local. Avoid wildcard imports and unexplained import-time side effects.
- Use a consistent formatter and linter (e.g., Ruff with formatter) and a static type checker (mypy or pyright). Establish repository configuration rather than inventing editor-specific rules.
- Prefer explicit control flow over dense comprehensions, clever one-liners, nested ternaries, or walrus expressions when readability suffers.
- Follow the repository's chosen Python version and toolchain. Do not introduce a dependency solely to replace a tiny, reliable standard-library feature.

## 8. Logging, exceptions, and reproducibility

- Use module-level loggers (`logging.getLogger(__name__)`) and let entry points configure handlers and verbosity. Never configure global logging when merely importing a library.
- Distinguish expected invalid input, environmental failures, and bugs. Fail visibly with enough context to diagnose what went wrong.
- Handle anticipated exceptions narrowly; no unqualified `except:` and no broad `except Exception: pass`.
- Favor deterministic processing, explicit ordering where order matters, and clear units/conversions in scientific/data workflows.
- Make file writes and state changes intentional, with attention to partial output and restartability when workloads are large or unattended.

## 9. Testing policy

- Test domain behavior directly via typed arguments, dataclasses, and functions. Test CLI token parsing separately from actual application execution.
- Include boundary and invalid inputs, empty collections, `None` where allowed, duplicate values, malformed data, resource failure, and regression cases relevant to the behavior.
- Test important mutation semantics and error behavior. Don't write brittle tests that simply mirror implementation steps.
- Use temporary directories, in-memory fakes, and dependency injection rather than hardcoded environment paths or live services for normal unit tests.
- A pragmatic ~80–85% line coverage can be a useful target, **not a substitute for thoughtful coverage**. Prioritize complex logic and failure paths over trivial getters, constants, logging passthrough, and standard-library behavior.
- Type test helpers and fixtures; write contract-oriented docstrings for reusable helpers.

## 10. Review checklist

Before approving or copying Python code, verify:

- [ ] Each function parameter is annotated **and documented** with meaning, constraints, and units when relevant.
- [ ] Every return value is annotated **and documented**, including explicit `None` returns.
- [ ] Meaningful raised exceptions, mutations, and side effects are documented.
- [ ] Local variables have declaration-time type annotations, including obvious initial values.
- [ ] `argparse` parsing creates typed dataclass argument objects; domain functions never receive `Namespace`.
- [ ] Entry point contains only parsing, dispatch, and exit-status handling; application logic is separately callable.
- [ ] Functions/classes reside in cohesive modules/packages; no unrelated kitchen-sink files.
- [ ] Domain logic is separable from I/O; dependencies and failure cases are testable.
- [ ] Logging is used appropriately; no surprising import-time work or hidden global state.
- [ ] Edge cases and failure paths have meaningful tests.
- [ ] Any AI-authored module, class, or function docstrings contain the required `TODO(AI-GENERATED)` marker until genuinely reviewed.

**Guiding principle:** Make it easy for the next developer to understand what values exist, what every function expects, what it returns, where behavior lives, and how to test it, without reverse-engineering a monolithic script or relying on implicit conventions.
