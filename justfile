default: list

[private]
list:
    just --list

test:
    uv run pytest

lint:
    uv run ruff check

types:
    uv run mypy --strict splunk_downloader tests
    uv run ty check

check: lint types test

# run coverage checks and output html
coverage:
    uv run coverage run -m pytest && uv run coverage html && open htmlcov/index.html