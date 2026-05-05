"""Tests for the storage module."""
import pytest
from memdb.storage import (
    ColumnType, Column, Schema, HashIndex, BTreeIndex, TransactionLog, Table
)


def make_users_schema():
    return Schema([
        Column('id', ColumnType.INT),
        Column('name', ColumnType.TEXT),
        Column('age', ColumnType.INT),
        Column('score', ColumnType.FLOAT),
        Column('active', ColumnType.BOOL),
    ])


def test_schema_coerce():
    schema = make_users_schema()
    assert schema.coerce('id', '42') == 42
    assert isinstance(schema.coerce('id', '42'), int)
    assert schema.coerce('score', '3.14') == pytest.approx(3.14)
    assert isinstance(schema.coerce('score', '3.14'), float)
    assert schema.coerce('name', 123) == '123'
    assert isinstance(schema.coerce('name', 123), str)
    assert schema.coerce('active', 'true') is True
    assert schema.coerce('active', 'false') is False
    assert schema.coerce('active', True) is True
    assert schema.coerce('id', None) is None


def test_table_insert_scan():
    schema = make_users_schema()
    table = Table('users', schema)
    rid = table.insert({'id': 1, 'name': 'Alice', 'age': 30})
    assert rid == 0
    rows = table.scan()
    assert len(rows) == 1
    row_id, data = rows[0]
    assert row_id == 0
    assert data['name'] == 'Alice'
    assert data['age'] == 30


def test_table_update_delete():
    schema = make_users_schema()
    table = Table('users', schema)
    rid = table.insert({'id': 1, 'name': 'Alice', 'age': 30})
    table.update(rid, {'age': 31})
    assert table.get(rid)['age'] == 31
    assert table.row_count() == 1
    table.delete(rid)
    assert table.row_count() == 0
    assert table.get(rid) is None


def test_hash_index_insert_lookup_delete():
    idx = HashIndex()
    idx.insert('alice', 0)
    idx.insert('bob', 1)
    idx.insert('alice', 2)
    assert sorted(idx.lookup('alice')) == [0, 2]
    assert idx.lookup('bob') == [1]
    assert idx.lookup('charlie') == []
    idx.delete('alice', 0)
    assert idx.lookup('alice') == [2]


def test_btree_index_lookup_eq():
    idx = BTreeIndex()
    idx.insert(10, 0)
    idx.insert(20, 1)
    idx.insert(10, 2)
    idx.insert(30, 3)
    result = idx.lookup_eq(10)
    assert sorted(result) == [0, 2]
    assert idx.lookup_eq(20) == [1]
    assert idx.lookup_eq(99) == []


def test_btree_index_lookup_range_inclusive():
    idx = BTreeIndex()
    for i, v in enumerate([1, 3, 5, 7, 9]):
        idx.insert(v, i)
    # inclusive range [3, 7]
    result = idx.lookup_range(lo_key=3, hi_key=7, lo_inc=True, hi_inc=True)
    assert sorted(result) == [1, 2, 3]  # row_ids for values 3,5,7


def test_btree_index_lookup_range_exclusive():
    idx = BTreeIndex()
    for i, v in enumerate([1, 3, 5, 7, 9]):
        idx.insert(v, i)
    # exclusive range (3, 7)
    result = idx.lookup_range(lo_key=3, hi_key=7, lo_inc=False, hi_inc=False)
    assert result == [2]  # only value 5


def test_btree_index_range_none_bounds():
    idx = BTreeIndex()
    for i, v in enumerate([10, 20, 30]):
        idx.insert(v, i)
    # no lower bound
    result = idx.lookup_range(hi_key=20, hi_inc=True)
    assert sorted(result) == [0, 1]
    # no upper bound
    result = idx.lookup_range(lo_key=20, lo_inc=True)
    assert sorted(result) == [1, 2]
    # both None = all
    result = idx.lookup_range()
    assert sorted(result) == [0, 1, 2]


def test_transaction_log():
    log = TransactionLog()
    log.append('INSERT', 'users', {'row_id': 0})
    log.append('INSERT', 'users', {'row_id': 1})
    log.append('DELETE', 'users', {'row_id': 0})
    entries = log.entries()
    assert len(entries) == 3
    assert entries[0]['seq'] == 0
    assert entries[0]['op'] == 'INSERT'
    replayed = log.replay(since_seq=1)
    assert len(replayed) == 2
    assert replayed[0]['seq'] == 1


def test_index_updated_on_table_update_delete():
    schema = make_users_schema()
    table = Table('users', schema)
    table.add_index('age', 'btree')
    rid = table.insert({'id': 1, 'name': 'Alice', 'age': 30})
    assert rid in table.get_index('age').lookup_eq(30)
    # Update age
    table.update(rid, {'age': 31})
    assert rid not in table.get_index('age').lookup_eq(30)
    assert rid in table.get_index('age').lookup_eq(31)
    # Delete row
    table.delete(rid)
    assert rid not in table.get_index('age').lookup_eq(31)
