"""Tests for the parser module."""
import pytest
from memdb.parser import (
    tokenize, parse, TT, Token,
    Literal, Identifier, Star, BinaryOp, UnaryOp, OrderByItem, JoinClause,
    SelectStmt, InsertStmt, UpdateStmt, DeleteStmt, CreateTableStmt,
    LexError, ParseError
)


def test_tokenize_simple_select():
    tokens = tokenize("SELECT * FROM users")
    types = [t.type for t in tokens]
    assert TT.SELECT in types
    assert TT.STAR in types
    assert TT.FROM in types
    assert TT.IDENT in types
    assert TT.EOF in types


def test_parse_select_star():
    stmt = parse("SELECT * FROM users")
    assert isinstance(stmt, SelectStmt)
    assert stmt.from_table == "users"
    assert len(stmt.columns) == 1
    assert isinstance(stmt.columns[0], Star)


def test_parse_select_with_where():
    stmt = parse("SELECT id, name FROM users WHERE age > 18")
    assert isinstance(stmt, SelectStmt)
    assert stmt.from_table == "users"
    assert len(stmt.columns) == 2
    assert isinstance(stmt.where, BinaryOp)
    assert stmt.where.op == '>'
    assert isinstance(stmt.where.left, Identifier)
    assert stmt.where.left.name == 'age'
    assert isinstance(stmt.where.right, Literal)
    assert stmt.where.right.value == 18


def test_parse_select_with_and():
    stmt = parse("SELECT * FROM users WHERE age > 18 AND name = 'Alice'")
    assert isinstance(stmt, SelectStmt)
    assert isinstance(stmt.where, BinaryOp)
    assert stmt.where.op == 'AND'
    assert isinstance(stmt.where.left, BinaryOp)
    assert stmt.where.left.op == '>'
    assert isinstance(stmt.where.right, BinaryOp)
    assert stmt.where.right.op == '='


def test_parse_select_order_by_limit():
    stmt = parse("SELECT * FROM users ORDER BY age DESC LIMIT 10")
    assert isinstance(stmt, SelectStmt)
    assert stmt.limit == 10
    assert len(stmt.order_by) == 1
    assert stmt.order_by[0].ascending is False
    assert isinstance(stmt.order_by[0].expr, Identifier)


def test_parse_insert():
    stmt = parse("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    assert isinstance(stmt, InsertStmt)
    assert stmt.table == "users"
    assert stmt.columns == ['id', 'name', 'age']
    assert len(stmt.values) == 1
    assert len(stmt.values[0]) == 3
    assert isinstance(stmt.values[0][0], Literal)
    assert stmt.values[0][0].value == 1
    assert stmt.values[0][1].value == 'Alice'
    assert stmt.values[0][2].value == 30


def test_parse_update():
    stmt = parse("UPDATE users SET age = 31 WHERE id = 1")
    assert isinstance(stmt, UpdateStmt)
    assert stmt.table == "users"
    assert len(stmt.assignments) == 1
    assert stmt.assignments[0].column == 'age'
    assert isinstance(stmt.assignments[0].value, Literal)
    assert stmt.assignments[0].value.value == 31
    assert isinstance(stmt.where, BinaryOp)
    assert stmt.where.op == '='


def test_parse_delete():
    stmt = parse("DELETE FROM users WHERE id = 1")
    assert isinstance(stmt, DeleteStmt)
    assert stmt.table == "users"
    assert isinstance(stmt.where, BinaryOp)
    assert stmt.where.op == '='


def test_parse_create_table():
    stmt = parse("CREATE TABLE users (id INT, name TEXT, age INT)")
    assert isinstance(stmt, CreateTableStmt)
    assert stmt.table == "users"
    assert len(stmt.column_defs) == 3
    assert stmt.column_defs[0].name == 'id'
    assert stmt.column_defs[0].col_type == 'INT'
    assert stmt.column_defs[1].name == 'name'
    assert stmt.column_defs[1].col_type == 'TEXT'


def test_parse_join():
    stmt = parse("SELECT * FROM users u JOIN orders o ON u.id = o.user_id")
    assert isinstance(stmt, SelectStmt)
    assert stmt.from_table == "users"
    assert stmt.from_alias == "u"
    assert len(stmt.joins) == 1
    join = stmt.joins[0]
    assert isinstance(join, JoinClause)
    assert join.table == "orders"
    assert join.alias == "o"
    assert join.join_type == "INNER"
    assert isinstance(join.condition, BinaryOp)
    assert join.condition.op == '='


def test_parse_is_null():
    stmt = parse("SELECT * FROM users WHERE name IS NULL")
    assert isinstance(stmt, SelectStmt)
    assert isinstance(stmt.where, UnaryOp)
    assert stmt.where.op == 'IS NULL'


def test_parse_is_not_null():
    stmt = parse("SELECT * FROM users WHERE name IS NOT NULL")
    assert isinstance(stmt, SelectStmt)
    assert isinstance(stmt.where, UnaryOp)
    assert stmt.where.op == 'IS NOT NULL'


def test_parse_not_operator():
    stmt = parse("SELECT * FROM users WHERE NOT active = true")
    assert isinstance(stmt, SelectStmt)
    assert isinstance(stmt.where, UnaryOp)
    assert stmt.where.op == 'NOT'


def test_lex_error():
    with pytest.raises(LexError):
        tokenize("SELECT @ FROM users")


def test_parse_error():
    with pytest.raises(ParseError):
        parse("SELECT FROM WHERE")
