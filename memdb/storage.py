"""Storage layer: typed columns, in-memory tables, hash index, B-tree index, transaction log."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ColumnType(Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOL = "BOOL"


@dataclass
class Column:
    name: str
    col_type: ColumnType
    nullable: bool = True
    primary_key: bool = False


class Schema:
    def __init__(self, columns: List[Column]):
        self.columns = columns
        self._col_map = {c.name: c for c in columns}

    def coerce(self, col_name: str, value: Any) -> Any:
        if col_name not in self._col_map:
            return value
        col = self._col_map[col_name]
        if value is None:
            return None
        if col.col_type == ColumnType.INT:
            return int(value)
        if col.col_type == ColumnType.FLOAT:
            return float(value)
        if col.col_type == ColumnType.TEXT:
            return str(value)
        if col.col_type == ColumnType.BOOL:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes')
            return bool(value)
        return value

    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]


class HashIndex:
    def __init__(self):
        self._data: Dict[Any, List[int]] = {}
        self._id_sets: Dict[Any, set] = {}

    def insert(self, key: Any, row_id: int) -> None:
        if key not in self._data:
            self._data[key] = []
            self._id_sets[key] = set()
        if row_id not in self._id_sets[key]:
            self._data[key].append(row_id)
            self._id_sets[key].add(row_id)

    def delete(self, key: Any, row_id: int) -> None:
        if key in self._data:
            self._id_sets[key].discard(row_id)
            try:
                self._data[key].remove(row_id)
            except ValueError:
                pass
            if not self._data[key]:
                del self._data[key]
                del self._id_sets[key]

    def lookup(self, key: Any) -> List[int]:
        return list(self._data.get(key, []))

    def all_ids(self) -> List[int]:
        result = []
        for ids in self._data.values():
            result.extend(ids)
        return result


class BTreeIndex:
    def __init__(self):
        self._entries: List[Tuple[Any, int]] = []  # sorted by (key, row_id)

    def _lower_bound(self, key: Any) -> int:
        """First i where _entries[i][0] >= key"""
        lo, hi = 0, len(self._entries)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._entries[mid][0] < key:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _upper_bound(self, key: Any) -> int:
        """First i where _entries[i][0] > key"""
        lo, hi = 0, len(self._entries)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._entries[mid][0] <= key:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def insert(self, key: Any, row_id: int) -> None:
        if key is None:
            return
        hi = self._upper_bound(key)
        self._entries.insert(hi, (key, row_id))

    def delete(self, key: Any, row_id: int) -> None:
        if key is None:
            return
        lo = self._lower_bound(key)
        hi = self._upper_bound(key)
        for i in range(lo, hi):
            if self._entries[i][1] == row_id:
                self._entries.pop(i)
                return

    def lookup_eq(self, key: Any) -> List[int]:
        lo = self._lower_bound(key)
        hi = self._upper_bound(key)
        return [self._entries[i][1] for i in range(lo, hi)]

    def lookup_range(self, lo_key=None, hi_key=None, lo_inc=True, hi_inc=True) -> List[int]:
        lo = 0 if lo_key is None else (self._lower_bound(lo_key) if lo_inc else self._upper_bound(lo_key))
        hi = len(self._entries) if hi_key is None else (self._upper_bound(hi_key) if hi_inc else self._lower_bound(hi_key))
        return [self._entries[i][1] for i in range(lo, hi)]

    def all_ids(self) -> List[int]:
        return [e[1] for e in self._entries]


class TransactionLog:
    def __init__(self):
        self._log: List[Dict] = []
        self._seq = 0

    def append(self, op: str, table: str, data: Any = None) -> int:
        entry = {'seq': self._seq, 'op': op, 'table': table, 'data': data}
        self._log.append(entry)
        self._seq += 1
        return self._seq - 1

    def entries(self) -> List[Dict]:
        return list(self._log)

    def replay(self, since_seq: int = 0) -> List[Dict]:
        return [e for e in self._log if e['seq'] >= since_seq]


class Table:
    def __init__(self, name: str, schema: Schema):
        self.name = name
        self.schema = schema
        self._rows: Dict[int, Dict] = {}
        self._next_id = 0
        self._indexes: Dict[str, Any] = {}

    def add_index(self, column: str, index_type: str = "hash") -> None:
        if index_type == "hash":
            idx = HashIndex()
        elif index_type == "btree":
            idx = BTreeIndex()
        else:
            raise ValueError(f"Unknown index type: {index_type}")
        self._indexes[column] = idx
        for row_id, row in self._rows.items():
            key = row.get(column)
            idx.insert(key, row_id)

    def get_index(self, column: str):
        return self._indexes.get(column)

    def insert(self, row_dict: Dict) -> int:
        row_id = self._next_id
        self._next_id += 1
        coerced = {}
        for col_name in self.schema.column_names():
            val = row_dict.get(col_name)
            coerced[col_name] = self.schema.coerce(col_name, val)
        self._rows[row_id] = coerced
        for col_name, idx in self._indexes.items():
            key = coerced.get(col_name)
            idx.insert(key, row_id)
        return row_id

    def scan(self) -> List[Tuple[int, Dict]]:
        return list(self._rows.items())

    def get(self, row_id: int) -> Optional[Dict]:
        return self._rows.get(row_id)

    def update(self, row_id: int, updates: Dict) -> None:
        if row_id not in self._rows:
            return
        old_row = self._rows[row_id]
        for col_name, idx in self._indexes.items():
            old_key = old_row.get(col_name)
            idx.delete(old_key, row_id)
        new_row = dict(old_row)
        for col_name, val in updates.items():
            new_row[col_name] = self.schema.coerce(col_name, val)
        self._rows[row_id] = new_row
        for col_name, idx in self._indexes.items():
            new_key = new_row.get(col_name)
            idx.insert(new_key, row_id)

    def delete(self, row_id: int) -> None:
        if row_id not in self._rows:
            return
        row = self._rows[row_id]
        for col_name, idx in self._indexes.items():
            key = row.get(col_name)
            idx.delete(key, row_id)
        del self._rows[row_id]

    def row_count(self) -> int:
        return len(self._rows)
