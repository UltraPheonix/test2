"""Execution engine: executes plan nodes, streams results, handles errors."""
from __future__ import annotations
import functools
from typing import Any, Dict, Generator, List, Optional, Tuple

from .parser import (
    Literal, Identifier, Star, BinaryOp, UnaryOp, OrderByItem, Assignment,
    ColumnDef
)
from .optimizer import (
    SeqScanNode, IndexScanNode, FilterNode, ProjectNode, SortNode, LimitNode,
    NestedLoopJoinNode, InsertPlanNode, UpdatePlanNode, DeletePlanNode, CreateTablePlanNode
)
from .storage import (
    Table, Schema, Column, ColumnType, HashIndex, BTreeIndex, TransactionLog
)


class ExecutionError(Exception):
    pass


@functools.total_ordering
class SortKey:
    """Comparator for sort with NULLs last."""
    def __init__(self, val, ascending=True):
        self.val = val
        self.ascending = ascending

    def __eq__(self, other):
        return self.val == other.val

    def __lt__(self, other):
        if self.val is None and other.val is None:
            return False
        if self.val is None:
            return False  # nulls last: null > everything
        if other.val is None:
            return True   # non-null < null
        if self.ascending:
            return self.val < other.val
        else:
            return self.val > other.val


Row = Dict[str, Any]


class Executor:
    def __init__(self, catalog: Dict[str, Table], txlog: TransactionLog):
        self.catalog = catalog
        self.txlog = txlog

    def execute(self, plan) -> Tuple[List[str], List[Row]]:
        ctx = {}
        rows = list(self._execute_node(plan, ctx))
        if rows:
            cols = [k for k in rows[0].keys() if not k.startswith('__') and '.' not in k]
        else:
            cols = []
        clean_rows = []
        for row in rows:
            clean = {k: v for k, v in row.items() if not k.startswith('__') and '.' not in k}
            clean_rows.append(clean)
        return cols, clean_rows

    def _execute_node(self, node, ctx) -> Generator[Row, None, None]:
        if isinstance(node, SeqScanNode):
            yield from self._exec_seq_scan(node, ctx)
        elif isinstance(node, IndexScanNode):
            yield from self._exec_index_scan(node, ctx)
        elif isinstance(node, FilterNode):
            yield from self._exec_filter(node, ctx)
        elif isinstance(node, ProjectNode):
            yield from self._exec_project(node, ctx)
        elif isinstance(node, SortNode):
            yield from self._exec_sort(node, ctx)
        elif isinstance(node, LimitNode):
            yield from self._exec_limit(node, ctx)
        elif isinstance(node, NestedLoopJoinNode):
            yield from self._exec_nested_loop_join(node, ctx)
        elif isinstance(node, InsertPlanNode):
            yield from self._exec_insert(node, ctx)
        elif isinstance(node, UpdatePlanNode):
            yield from self._exec_update(node, ctx)
        elif isinstance(node, DeletePlanNode):
            yield from self._exec_delete(node, ctx)
        elif isinstance(node, CreateTablePlanNode):
            yield from self._exec_create_table(node, ctx)
        else:
            raise ExecutionError(f"Unknown plan node: {type(node)}")

    def _make_row(self, table_name: str, alias: Optional[str], row_id: int, data: Dict) -> Row:
        prefix = alias or table_name
        result = {'__row_id': row_id, '__table': table_name}
        for k, v in data.items():
            result[k] = v
            result[f"{prefix}.{k}"] = v
        return result

    def _exec_seq_scan(self, node: SeqScanNode, ctx) -> Generator[Row, None, None]:
        tbl = self.catalog.get(node.table)
        if tbl is None:
            raise ExecutionError(f"Table not found: {node.table}")
        for row_id, data in tbl.scan():
            row = self._make_row(node.table, node.alias, row_id, data)
            if node.predicate is None or self._eval_bool(node.predicate, row):
                yield row

    def _exec_index_scan(self, node: IndexScanNode, ctx) -> Generator[Row, None, None]:
        tbl = self.catalog.get(node.table)
        if tbl is None:
            raise ExecutionError(f"Table not found: {node.table}")
        idx = tbl.get_index(node.column)
        if idx is None:
            raise ExecutionError(f"No index on {node.table}.{node.column}")
        col, op, val = node.predicate
        row_ids = self._lookup_index(idx, (col, op, val), node.column)
        post_filter = node.residual
        for row_id in row_ids:
            data = tbl.get(row_id)
            if data is None:
                continue
            row = self._make_row(node.table, node.alias, row_id, data)
            if post_filter is None or self._eval_bool(post_filter, row):
                yield row

    def _exec_filter(self, node: FilterNode, ctx) -> Generator[Row, None, None]:
        for row in self._execute_node(node.child, ctx):
            if self._eval_bool(node.predicate, row):
                yield row

    def _exec_project(self, node: ProjectNode, ctx) -> Generator[Row, None, None]:
        for row in self._execute_node(node.child, ctx):
            out = {}
            for k, v in row.items():
                if k.startswith('__'):
                    out[k] = v
            for col_expr in node.columns:
                if isinstance(col_expr, Star):
                    if col_expr.table:
                        prefix = col_expr.table + '.'
                        for k, v in row.items():
                            if k.startswith(prefix) and not k.startswith('__'):
                                bare = k[len(prefix):]
                                out[bare] = v
                    else:
                        for k, v in row.items():
                            if not k.startswith('__') and '.' not in k:
                                out[k] = v
                elif isinstance(col_expr, Identifier):
                    if col_expr.table:
                        key = f"{col_expr.table}.{col_expr.column}"
                        val = row.get(key, row.get(col_expr.column))
                        out[col_expr.column] = val
                    else:
                        col = col_expr.column or col_expr.name
                        if col in row:
                            out[col] = row[col]
                        else:
                            # Try qualified form
                            found = None
                            for k, v in row.items():
                                if '.' in k and k.split('.', 1)[1] == col:
                                    found = v
                                    break
                            out[col] = found
                else:
                    val = self._eval(col_expr, row)
                    out[str(col_expr)] = val
            yield out

    def _exec_sort(self, node: SortNode, ctx) -> Generator[Row, None, None]:
        rows = list(self._execute_node(node.child, ctx))
        order_by = node.order_by

        def sort_key(row):
            return [SortKey(self._eval(item.expr, row), item.ascending) for item in order_by]

        rows.sort(key=sort_key)
        yield from rows

    def _exec_limit(self, node: LimitNode, ctx) -> Generator[Row, None, None]:
        count = 0
        for row in self._execute_node(node.child, ctx):
            if count >= node.limit:
                break
            yield row
            count += 1

    def _exec_nested_loop_join(self, node: NestedLoopJoinNode, ctx) -> Generator[Row, None, None]:
        outer_rows = list(self._execute_node(node.outer, ctx))
        inner_rows = list(self._execute_node(node.inner, ctx))

        inner_cols = set()
        for ir in inner_rows:
            for k in ir:
                if not k.startswith('__'):
                    inner_cols.add(k)

        for outer_row in outer_rows:
            matched = False
            for inner_row in inner_rows:
                combined = {**outer_row, **inner_row}
                if self._eval_bool(node.condition, combined):
                    matched = True
                    yield combined
            if not matched and node.join_type == "LEFT":
                null_inner = {k: None for k in inner_cols}
                yield {**outer_row, **null_inner}

    def _exec_insert(self, node: InsertPlanNode, ctx) -> Generator[Row, None, None]:
        tbl = self.catalog.get(node.table)
        if tbl is None:
            raise ExecutionError(f"Table not found: {node.table}")
        for value_row in node.values:
            row_dict = {}
            for i, col in enumerate(node.columns):
                val = self._eval(value_row[i], {}) if i < len(value_row) else None
                row_dict[col] = val
            row_id = tbl.insert(row_dict)
            self.txlog.append('INSERT', node.table, {'row_id': row_id, 'data': row_dict})
        yield from ()

    def _exec_update(self, node: UpdatePlanNode, ctx) -> Generator[Row, None, None]:
        tbl = self.catalog.get(node.table)
        if tbl is None:
            raise ExecutionError(f"Table not found: {node.table}")
        rows = list(self._execute_node(node.scan, ctx))
        for row in rows:
            row_id = row.get('__row_id')
            if row_id is None:
                continue
            updates = {}
            for asgn in node.assignments:
                updates[asgn.column] = self._eval(asgn.value, row)
            tbl.update(row_id, updates)
            self.txlog.append('UPDATE', node.table, {'row_id': row_id, 'updates': updates})
        yield from ()

    def _exec_delete(self, node: DeletePlanNode, ctx) -> Generator[Row, None, None]:
        tbl = self.catalog.get(node.table)
        if tbl is None:
            raise ExecutionError(f"Table not found: {node.table}")
        rows = list(self._execute_node(node.scan, ctx))
        for row in rows:
            row_id = row.get('__row_id')
            if row_id is None:
                continue
            tbl.delete(row_id)
            self.txlog.append('DELETE', node.table, {'row_id': row_id})
        yield from ()

    def _exec_create_table(self, node: CreateTablePlanNode, ctx) -> Generator[Row, None, None]:
        if node.table in self.catalog:
            raise ExecutionError(f"Table already exists: {node.table}")
        col_type_map = {
            'INT': ColumnType.INT, 'FLOAT': ColumnType.FLOAT,
            'TEXT': ColumnType.TEXT, 'BOOL': ColumnType.BOOL
        }
        columns = []
        for cd in node.column_defs:
            ct = col_type_map.get(cd.col_type.upper())
            if ct is None:
                raise ExecutionError(f"Unknown type: {cd.col_type}")
            columns.append(Column(name=cd.name, col_type=ct, nullable=cd.nullable, primary_key=cd.primary_key))
        schema = Schema(columns)
        tbl = Table(node.table, schema)
        self.catalog[node.table] = tbl
        self.txlog.append('CREATE_TABLE', node.table, {'columns': [c.name for c in columns]})
        yield from ()

    def _eval(self, expr, row: Row) -> Any:
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, Identifier):
            if expr.table:
                key = f"{expr.table}.{expr.column}"
                if key in row:
                    return row[key]
                return row.get(expr.column)
            col = expr.column or expr.name
            if col in row:
                return row[col]
            for k, v in row.items():
                if '.' in k and k.split('.', 1)[1] == col:
                    return v
            return None
        if isinstance(expr, BinaryOp):
            return self._eval_binop(expr, row)
        if isinstance(expr, UnaryOp):
            return self._eval_unop(expr, row)
        return None

    def _eval_bool(self, expr, row: Row) -> bool:
        val = self._eval(expr, row)
        if val is None:
            return False
        return bool(val)

    def _eval_binop(self, expr: BinaryOp, row: Row) -> Any:
        if expr.op == 'AND':
            return self._eval_bool(expr.left, row) and self._eval_bool(expr.right, row)
        if expr.op == 'OR':
            return self._eval_bool(expr.left, row) or self._eval_bool(expr.right, row)
        left = self._eval(expr.left, row)
        right = self._eval(expr.right, row)
        if expr.op == '=':
            return left == right
        if expr.op == '!=':
            return left != right
        if left is None or right is None:
            return None
        if expr.op == '<':
            return left < right
        if expr.op == '>':
            return left > right
        if expr.op == '<=':
            return left <= right
        if expr.op == '>=':
            return left >= right
        return None

    def _eval_unop(self, expr: UnaryOp, row: Row) -> Any:
        if expr.op == 'NOT':
            return not self._eval_bool(expr.operand, row)
        if expr.op == 'IS NULL':
            return self._eval(expr.operand, row) is None
        if expr.op == 'IS NOT NULL':
            return self._eval(expr.operand, row) is not None
        return None

    def _lookup_index(self, idx, predicate, column) -> List[int]:
        col, op, val = predicate
        if col != column:
            return self._all_index_ids(idx)
        if isinstance(idx, HashIndex):
            if op == '=':
                return idx.lookup(val)
            return self._all_index_ids(idx)
        if isinstance(idx, BTreeIndex):
            if op == '=':
                return idx.lookup_eq(val)
            if op == '<':
                return idx.lookup_range(hi_key=val, hi_inc=False)
            if op == '<=':
                return idx.lookup_range(hi_key=val, hi_inc=True)
            if op == '>':
                return idx.lookup_range(lo_key=val, lo_inc=False)
            if op == '>=':
                return idx.lookup_range(lo_key=val, lo_inc=True)
            return self._all_index_ids(idx)
        return []

    def _all_index_ids(self, idx) -> List[int]:
        if isinstance(idx, (HashIndex, BTreeIndex)):
            return idx.all_ids()
        return []
