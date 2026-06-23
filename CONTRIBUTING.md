# Contributing to Swiss Auditor IAC

## Development Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd swiss_auditor_iac
    ```

2.  **Set up a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run tests**:
    ```bash
    ./venv/bin/python -m unittest discover tests
    ```

## Coding Standards

*   We use **Ruff** for linting and formatting.
*   Run linter:
    ```bash
    ruff check .
    ```
*   Follow **Test-Driven Development (TDD)** principles when adding new features.
*   Ensure unit tests cover public interfaces and are not coupled to implementation details.

## Data Handling

*   Do NOT commit large data files to the repository.
*   Place large test fixtures in `tests/fixtures/` which is ignored by Git.
*   Ensure `data_grafo_structured.md` is available in `agents/resources/` as required by the pipeline.
