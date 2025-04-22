default: checks

test:
    uv run pytest

lint:
    uv run ruff check splunk_downloader tests

mypy :
    uv run mypy --strict splunk_downloader tests

checks: lint mypy test

# run coverage checks and output html
coverage:
    uv run coverage run -m pytest && uv run coverage html && open htmlcov/index.html