"""Tests for the execution engine."""
import pytest
from memdb import Database, ExecutionError


@pytest.fixture
def db():
    d = Database()
    d.execute("CREATE TABLE users (id INT, name TEXT, age INT, active BOOL)")
    d.execute("CREATE TABLE orders (id INT, user_id INT, amount FLOAT)")
    return d


def test_create_and_insert_select(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    cols, rows = db.execute("SELECT * FROM users")
    assert len(rows) == 1
    assert rows[0]['name'] == 'Alice'
    assert rows[0]['age'] == 30


def test_select_where_equality(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    cols, rows = db.execute("SELECT * FROM users WHERE id = 1")
    assert len(rows) == 1
    assert rows[0]['name'] == 'Alice'


def test_select_where_range(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("INSERT INTO users (id, name, age) VALUES (3, 'Charlie', 20)")
    cols, rows = db.execute("SELECT * FROM users WHERE age > 22")
    assert len(rows) == 2
    names = {r['name'] for r in rows}
    assert 'Alice' in names
    assert 'Bob' in names


def test_select_and_or(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("INSERT INTO users (id, name, age) VALUES (3, 'Charlie', 20)")
    # AND
    cols, rows = db.execute("SELECT * FROM users WHERE age > 20 AND age < 30")
    assert len(rows) == 1
    assert rows[0]['name'] == 'Bob'
    # OR
    cols, rows = db.execute("SELECT * FROM users WHERE age = 20 OR age = 30")
    assert len(rows) == 2


def test_select_order_by(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("INSERT INTO users (id, name, age) VALUES (3, 'Charlie', 20)")
    cols, rows = db.execute("SELECT * FROM users ORDER BY age ASC")
    ages = [r['age'] for r in rows]
    assert ages == [20, 25, 30]
    cols, rows = db.execute("SELECT * FROM users ORDER BY age DESC")
    ages = [r['age'] for r in rows]
    assert ages == [30, 25, 20]


def test_select_limit(db):
    for i in range(10):
        db.execute(f"INSERT INTO users (id, name, age) VALUES ({i}, 'User{i}', {20+i})")
    cols, rows = db.execute("SELECT * FROM users LIMIT 3")
    assert len(rows) == 3


def test_update_where(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("UPDATE users SET age = 31 WHERE id = 1")
    cols, rows = db.execute("SELECT * FROM users WHERE id = 1")
    assert rows[0]['age'] == 31
    cols, rows = db.execute("SELECT * FROM users WHERE id = 2")
    assert rows[0]['age'] == 25


def test_delete_where(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("DELETE FROM users WHERE id = 1")
    cols, rows = db.execute("SELECT * FROM users")
    assert len(rows) == 1
    assert rows[0]['name'] == 'Bob'


def test_insert_multiple_select_limit(db):
    for i in range(5):
        db.execute(f"INSERT INTO users (id, name, age) VALUES ({i}, 'User{i}', {20+i})")
    cols, rows = db.execute("SELECT * FROM users LIMIT 2")
    assert len(rows) == 2


def test_inner_join(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("INSERT INTO orders (id, user_id, amount) VALUES (1, 1, 99.99)")
    db.execute("INSERT INTO orders (id, user_id, amount) VALUES (2, 1, 49.99)")
    db.execute("INSERT INTO orders (id, user_id, amount) VALUES (3, 2, 29.99)")
    cols, rows = db.execute("SELECT * FROM users u JOIN orders o ON u.id = o.user_id")
    assert len(rows) == 3
    # Every joined row must contain both user fields (name) and order fields (amount)
    for row in rows:
        assert 'name' in row and 'amount' in row, f"Expected both 'name' and 'amount' in {row}"


def test_left_join(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
    db.execute("INSERT INTO orders (id, user_id, amount) VALUES (1, 1, 99.99)")
    cols, rows = db.execute("SELECT * FROM users u LEFT JOIN orders o ON u.id = o.user_id")
    assert len(rows) == 2
    bob_row = next(r for r in rows if r.get('name') == 'Bob')
    # Bob has no orders, so order fields should be None
    assert bob_row.get('amount') is None


def test_is_null_is_not_null(db):
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
    cols, rows = db.execute("SELECT * FROM users WHERE age IS NULL")
    assert len(rows) == 1
    assert rows[0]['name'] == 'Bob'
    cols, rows = db.execute("SELECT * FROM users WHERE age IS NOT NULL")
    assert len(rows) == 1
    assert rows[0]['name'] == 'Alice'


def test_select_nonexistent_table():
    db = Database()
    with pytest.raises(ExecutionError):
        db.execute("SELECT * FROM nonexistent")


def test_index_scan_correct_results(db):
    for i in range(10):
        db.execute(f"INSERT INTO users (id, name, age) VALUES ({i}, 'User{i}', {20+i})")
    db.create_index('users', 'id', 'hash')
    cols, rows = db.execute("SELECT * FROM users WHERE id = 5")
    assert len(rows) == 1
    assert rows[0]['id'] == 5


def test_create_table_twice_raises_error(db):
    with pytest.raises(ExecutionError):
        db.execute("CREATE TABLE users (id INT)")
