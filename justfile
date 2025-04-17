# run coverage checks and output html
coverage:
    uv run coverage run -m pytest && uv run coverage html && open htmlcov/index.html