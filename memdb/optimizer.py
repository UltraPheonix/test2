"""Query planner: AST → execution plan with predicate pushdown and index selection."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .parser import (
    SelectStmt, InsertStmt, UpdateStmt, DeleteStmt, CreateTableStmt,
    BinaryOp, UnaryOp, Identifier, Literal, Star, OrderByItem, JoinClause
)
from .storage import Table, HashIndex, BTreeIndex


@dataclass
class SeqScanNode:
    table: str
    alias: Optional[str] = None
    predicate: Optional[Any] = None


@dataclass
class IndexScanNode:
    table: str
    column: str
    index_type: str
    predicate: Any
    alias: Optional[str] = None
    residual: Optional[Any] = None


@dataclass
class FilterNode:
    child: Any
    predicate: Any


@dataclass
class ProjectNode:
    child: Any
    columns: List


@dataclass
class SortNode:
    child: Any
    order_by: List


@dataclass
class LimitNode:
    child: Any
    limit: int


@dataclass
class NestedLoopJoinNode:
    outer: Any
    inner: Any
    condition: Any
    join_type: str = "INNER"


@dataclass
class InsertPlanNode:
    table: str
    columns: List[str]
    values: List[List]


@dataclass
class UpdatePlanNode:
    table: str
    assignments: List
    scan: Any


@dataclass
class DeletePlanNode:
    table: str
    scan: Any


@dataclass
class CreateTablePlanNode:
    table: str
    column_defs: List


OP_FLIP = {'=': '=', '!=': '!=', '<': '>', '>': '<', '<=': '>=', '>=': '<='}


class Planner:
    def __init__(self, catalog: Dict[str, Table]):
        self.catalog = catalog

    def plan(self, stmt) -> Any:
        if isinstance(stmt, SelectStmt):
            return self._plan_select(stmt)
        if isinstance(stmt, InsertStmt):
            return InsertPlanNode(table=stmt.table, columns=stmt.columns, values=stmt.values)
        if isinstance(stmt, UpdateStmt):
            scan = self._build_scan(stmt.table, None, stmt.where)
            return UpdatePlanNode(table=stmt.table, assignments=stmt.assignments, scan=scan)
        if isinstance(stmt, DeleteStmt):
            scan = self._build_scan(stmt.table, None, stmt.where)
            return DeletePlanNode(table=stmt.table, scan=scan)
        if isinstance(stmt, CreateTableStmt):
            return CreateTablePlanNode(table=stmt.table, column_defs=stmt.column_defs)
        raise ValueError(f"Unknown statement type: {type(stmt)}")

    def _plan_select(self, stmt: SelectStmt) -> Any:
        has_joins = bool(stmt.joins)
        if not has_joins:
            node = self._build_scan(stmt.from_table, stmt.from_alias, stmt.where)
        else:
            node = SeqScanNode(table=stmt.from_table, alias=stmt.from_alias)
            for join in stmt.joins:
                inner = SeqScanNode(table=join.table, alias=join.alias)
                node = NestedLoopJoinNode(
                    outer=node, inner=inner,
                    condition=join.condition, join_type=join.join_type
                )
            if stmt.where:
                node = FilterNode(child=node, predicate=stmt.where)
        node = ProjectNode(child=node, columns=stmt.columns)
        if stmt.order_by:
            node = SortNode(child=node, order_by=stmt.order_by)
        if stmt.limit is not None:
            node = LimitNode(child=node, limit=stmt.limit)
        return node

    def _build_scan(self, table: str, alias: Optional[str], where: Optional[Any]) -> Any:
        tbl = self.catalog.get(table)
        if tbl is None or where is None:
            return SeqScanNode(table=table, alias=alias, predicate=where)
        idx_pred, residual = self._extract_index_predicate(where, tbl, alias)
        if idx_pred is not None:
            col, op, val, idx_type = idx_pred
            return IndexScanNode(
                table=table, column=col, index_type=idx_type,
                predicate=(col, op, val),
                alias=alias,
                residual=residual
            )
        return SeqScanNode(table=table, alias=alias, predicate=where)

    def _extract_index_predicate(self, expr, tbl: Table, alias) -> Tuple:
        """Returns ((col, op, val, idx_type), residual) or (None, None)."""
        if isinstance(expr, BinaryOp) and expr.op == 'AND':
            idx_pred, _ = self._extract_index_predicate(expr.left, tbl, alias)
            if idx_pred is not None:
                return idx_pred, expr.right
            idx_pred, _ = self._extract_index_predicate(expr.right, tbl, alias)
            if idx_pred is not None:
                return idx_pred, expr.left
            return None, None

        if isinstance(expr, BinaryOp) and expr.op in ('=', '!=', '<', '>', '<=', '>='):
            left, right, op = expr.left, expr.right, expr.op
            if isinstance(left, Identifier) and isinstance(right, Literal):
                col = left.column or left.name
                idx = tbl.get_index(col)
                if idx is not None:
                    idx_type = 'hash' if isinstance(idx, HashIndex) else 'btree'
                    return (col, op, right.value, idx_type), None
            if isinstance(right, Identifier) and isinstance(left, Literal):
                col = right.column or right.name
                idx = tbl.get_index(col)
                if idx is not None:
                    idx_type = 'hash' if isinstance(idx, HashIndex) else 'btree'
                    flipped_op = OP_FLIP[op]
                    return (col, flipped_op, left.value, idx_type), None
        return None, None
