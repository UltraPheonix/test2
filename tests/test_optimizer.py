"""Tests for the optimizer/planner module."""
import pytest
from memdb.storage import Table, Schema, Column, ColumnType, HashIndex, BTreeIndex
from memdb.parser import parse
from memdb.optimizer import (
    Planner, SeqScanNode, IndexScanNode, FilterNode, ProjectNode,
    SortNode, LimitNode, NestedLoopJoinNode, UpdatePlanNode, DeletePlanNode
)


def make_catalog():
    schema = Schema([
        Column('id', ColumnType.INT),
        Column('name', ColumnType.TEXT),
        Column('age', ColumnType.INT),
    ])
    tbl = Table('users', schema)
    return {'users': tbl}


def test_seq_scan_no_index():
    catalog = make_catalog()
    stmt = parse("SELECT * FROM users WHERE age > 18")
    plan = Planner(catalog).plan(stmt)
    # ProjectNode wrapping SeqScan
    assert isinstance(plan, ProjectNode)
    assert isinstance(plan.child, SeqScanNode)
    assert plan.child.predicate is not None


def test_index_scan_hash_equality():
    catalog = make_catalog()
    catalog['users'].add_index('id', 'hash')
    stmt = parse("SELECT * FROM users WHERE id = 1")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, ProjectNode)
    assert isinstance(plan.child, IndexScanNode)
    assert plan.child.index_type == 'hash'
    assert plan.child.column == 'id'


def test_index_scan_btree():
    catalog = make_catalog()
    catalog['users'].add_index('age', 'btree')
    stmt = parse("SELECT * FROM users WHERE age > 18")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, ProjectNode)
    assert isinstance(plan.child, IndexScanNode)
    assert plan.child.index_type == 'btree'
    assert plan.child.column == 'age'


def test_predicate_pushdown_and():
    catalog = make_catalog()
    catalog['users'].add_index('id', 'hash')
    stmt = parse("SELECT * FROM users WHERE id = 1 AND age > 18")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, ProjectNode)
    assert isinstance(plan.child, IndexScanNode)
    # residual should be the non-index part
    assert plan.child.residual is not None


def test_order_by_limit_plan():
    catalog = make_catalog()
    stmt = parse("SELECT * FROM users ORDER BY age DESC LIMIT 5")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, LimitNode)
    assert plan.limit == 5
    assert isinstance(plan.child, SortNode)
    assert isinstance(plan.child.child, ProjectNode)


def test_join_plan():
    catalog = make_catalog()
    orders_schema = Schema([Column('id', ColumnType.INT), Column('user_id', ColumnType.INT)])
    catalog['orders'] = Table('orders', orders_schema)
    stmt = parse("SELECT * FROM users u JOIN orders o ON u.id = o.user_id")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, ProjectNode)
    assert isinstance(plan.child, NestedLoopJoinNode)
    assert plan.child.join_type == "INNER"


def test_update_plan():
    catalog = make_catalog()
    stmt = parse("UPDATE users SET age = 31 WHERE id = 1")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, UpdatePlanNode)
    assert plan.table == 'users'
    assert len(plan.assignments) == 1
    assert isinstance(plan.scan, SeqScanNode)


def test_delete_plan():
    catalog = make_catalog()
    stmt = parse("DELETE FROM users WHERE id = 1")
    plan = Planner(catalog).plan(stmt)
    assert isinstance(plan, DeletePlanNode)
    assert plan.table == 'users'
    assert isinstance(plan.scan, SeqScanNode)
