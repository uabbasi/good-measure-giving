# Contributing

Thank you for your interest in Good Measure Giving.

## Getting Started

1. Fork and clone the repository
2. Follow setup instructions in the [README](README.md)
3. Create a branch for your work

## Development

- **Python**: Use `uv` for dependency management (`uv sync`, `uv run`)
- **Frontend**: Use `npm` in the `website/` directory
- **Testing**: Run `uv run pytest` for pipeline tests, `npm test` for frontend

## Pull Requests

- Keep changes focused. One concern per PR.
- Include a clear description of what changed and why.
- Add or update tests when changing behavior.
- Run linting before submitting: `ruff check . --fix` for Python.

## Reporting Issues

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or screenshots

## Security

Do not open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for responsible disclosure.

## License

By contributing you agree that your contributions will be licensed under the Apache-2.0 license.
