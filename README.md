# MemDB - In-Memory Database Engine

A fully-functional in-memory relational database engine implemented in Python.

## Features

- **SQL Support**: SELECT, INSERT, UPDATE, DELETE, CREATE TABLE
- **WHERE clauses**: Equality, range comparisons, AND/OR/NOT, IS NULL/IS NOT NULL
- **JOINs**: INNER JOIN and LEFT JOIN with nested loop execution
- **ORDER BY** with ASC/DESC and NULL handling (NULLs last)
- **LIMIT** for result pagination
- **Indexes**: Hash index (O(1) equality lookup) and B-tree index (range queries)
- **Type system**: INT, FLOAT, TEXT, BOOL with automatic coercion
- **Transaction log**: Append-only log of all mutations
- **Query optimizer**: Predicate pushdown, index selection

## File Structure

```
memdb/
  __init__.py      - Package exports
  storage.py       - Storage layer (columns, tables, indexes, transaction log)
  parser.py        - SQL tokenizer and recursive-descent parser
  optimizer.py     - Query planner with predicate pushdown and index selection
  executor.py      - Execution engine
  database.py      - High-level Database interface
tests/
  test_parser.py
  test_storage.py
  test_optimizer.py
  test_executor.py
  test_concurrency.py
benchmarks/
  benchmark.py     - Performance benchmarks
main.py            - Interactive REPL
```

## Quick Start

```python
from memdb import Database

db = Database()
db.execute("CREATE TABLE users (id INT, name TEXT, age INT)")
db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")

cols, rows = db.execute("SELECT * FROM users WHERE age > 20 ORDER BY age DESC")
for row in rows:
    print(row)
```

## Running Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Running Benchmarks

```bash
python benchmarks/benchmark.py
```

## Interactive REPL

```bash
python main.py
```

## Architecture

1. **Parser** (`parser.py`): Tokenizes SQL and builds an AST using recursive descent
2. **Optimizer** (`optimizer.py`): Converts AST to a physical plan with index selection and predicate pushdown
3. **Executor** (`executor.py`): Executes the plan, streaming rows through the plan tree
4. **Storage** (`storage.py`): In-memory row storage with hash and B-tree indexes