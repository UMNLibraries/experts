# Session Context

Purpose: Quick bootstrap context for future coding sessions in this repository.

## Snapshot

- Last updated: 2026-07-10
- Repository name: experts
- Repository path: /Users/barne102/devprojects/experts
- Default working directory: /Users/barne102/devprojects/experts
- Active branch at capture time: feature/documentation
- Head commit at capture time: 756af69
- Remote: origin https://github.com/UMNLibraries/experts.git

## Worktree State At Capture Time

- Modified file: poetry.lock
- Untracked file: assorter_out.txt
- Untracked file: scopus_results_assorter.py

## Top-Level Layout

- experts: main package code
- tests: test suite mirroring package structure
- scopus_etl: ETL and loading scripts
- experiments: scratch experiments and prototypes
- practical_experiments: applied one-off scripts
- pyproject.toml: Poetry project config
- env.dist: environment variable template
- README.md: project overview and testing notes

## Core Code Map

- experts/api/scopus.py: Scopus client, parsers, bulk request helpers
- experts/api/pure/ws.py: Pure Web Services client and parsers
- experts/api/common.py: shared request/retry logic and protocol types
- experts/db/oracledb.py: Oracle connection helpers via oracledb
- experts/db/sqlalchemy.py: SQLAlchemy and cx_Oracle session helpers
- experts/helpers/jsonpath.py: JSONPath helper utilities

## Test Map

- tests/conftest.py: global pytest setup and --integration marker behavior
- tests/api/scopus: Scopus API tests
- tests/api/pure/ws: Pure WS API tests
- tests/db: database adapter tests
- tests/pure.old and tests/pureapi.old: legacy module test suites

## Environment Baseline

Expected variables are defined in env.dist, including:

- PURE_WS_DOMAIN
- PURE_WS_KEY
- PURE_WS_VERSION
- SCOPUS_API_DOMAIN
- SCOPUS_API_KEY
- SCOPUS_API_AFFILIATION_ID

## Known Local Constraint

At capture time, pytest collection failed under local pyenv 3.9.10 due to missing OpenSSL 1.1 dynamic library for Python ssl module (_ssl import error).

## Quick Start Commands

Run these at the beginning of a new session:

```bash
cd /Users/barne102/devprojects/experts
git branch --show-current
git status --short
```

Optional fast orientation:

```bash
find experts tests scopus_etl -maxdepth 2 -type d | sort
```

## Maintenance

Update this file whenever one of these changes:

- Default branch or active branch workflow
- Core module locations
- Test locations or test execution approach
- Environment requirements
- Known local constraints affecting development
