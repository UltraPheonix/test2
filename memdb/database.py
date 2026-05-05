"""High-level Database interface."""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from .parser import parse
from .optimizer import Planner
from .executor import Executor, ExecutionError
from .storage import Table, TransactionLog


class Database:
    def __init__(self, name: str = "memdb"):
        self.name = name
        self.catalog: Dict[str, Table] = {}
        self.txlog = TransactionLog()

    def execute(self, sql: str) -> Tuple[List[str], List[Dict]]:
        stmt = parse(sql)
        planner = Planner(self.catalog)
        plan = planner.plan(stmt)
        executor = Executor(self.catalog, self.txlog)
        cols, rows = executor.execute(plan)
        return cols, rows

    def create_index(self, table: str, column: str, index_type: str = "hash") -> None:
        tbl = self.catalog.get(table)
        if tbl is None:
            raise ExecutionError(f"Table not found: {table}")
        tbl.add_index(column, index_type)

    def get_table(self, name: str) -> Optional[Table]:
        return self.catalog.get(name)

    def list_tables(self) -> List[str]:
        return list(self.catalog.keys())

    def transaction_log(self) -> List[Dict]:
        return self.txlog.entries()
