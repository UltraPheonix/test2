"""Tokenizer + recursive-descent parser producing AST nodes."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


class LexError(Exception):
    pass


class ParseError(Exception):
    pass


class TT(Enum):
    INT_LIT = auto()
    FLOAT_LIT = auto()
    STRING_LIT = auto()
    BOOL_LIT = auto()
    NULL_LIT = auto()
    IDENT = auto()
    SELECT = auto()
    FROM = auto()
    WHERE = auto()
    INSERT = auto()
    INTO = auto()
    VALUES = auto()
    UPDATE = auto()
    SET = auto()
    DELETE = auto()
    CREATE = auto()
    TABLE = auto()
    JOIN = auto()
    ON = auto()
    INNER = auto()
    LEFT = auto()
    ORDER = auto()
    BY = auto()
    ASC = auto()
    DESC = auto()
    LIMIT = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IS = auto()
    INT = auto()
    FLOAT = auto()
    TEXT = auto()
    BOOL = auto()
    AS = auto()
    STAR = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    SEMI = auto()
    DOT = auto()
    EOF = auto()


KEYWORDS = {
    'select': TT.SELECT, 'from': TT.FROM, 'where': TT.WHERE,
    'insert': TT.INSERT, 'into': TT.INTO, 'values': TT.VALUES,
    'update': TT.UPDATE, 'set': TT.SET, 'delete': TT.DELETE,
    'create': TT.CREATE, 'table': TT.TABLE, 'join': TT.JOIN,
    'on': TT.ON, 'inner': TT.INNER, 'left': TT.LEFT,
    'order': TT.ORDER, 'by': TT.BY, 'asc': TT.ASC, 'desc': TT.DESC,
    'limit': TT.LIMIT, 'and': TT.AND, 'or': TT.OR, 'not': TT.NOT,
    'is': TT.IS, 'int': TT.INT, 'float': TT.FLOAT, 'text': TT.TEXT,
    'bool': TT.BOOL, 'as': TT.AS, 'null': TT.NULL_LIT,
    'true': TT.BOOL_LIT, 'false': TT.BOOL_LIT,
}

# Keywords that can also be used as identifiers
KEYWORD_IDENT_TYPES = frozenset([
    TT.SELECT, TT.FROM, TT.WHERE, TT.INSERT, TT.INTO, TT.VALUES,
    TT.UPDATE, TT.SET, TT.DELETE, TT.CREATE, TT.TABLE, TT.JOIN,
    TT.ON, TT.INNER, TT.LEFT, TT.ORDER, TT.BY, TT.ASC, TT.DESC,
    TT.LIMIT, TT.AND, TT.OR, TT.NOT, TT.IS, TT.INT, TT.FLOAT,
    TT.TEXT, TT.BOOL, TT.AS
])


@dataclass
class Token:
    type: TT
    value: Any
    pos: int


@dataclass
class Literal:
    value: Any


@dataclass
class Identifier:
    name: str
    table: Optional[str] = None
    column: Optional[str] = None

    def __post_init__(self):
        if '.' in self.name and self.table is None:
            parts = self.name.split('.', 1)
            self.table = parts[0]
            self.column = parts[1]
        elif self.table is None:
            self.column = self.name


@dataclass
class Star:
    table: Optional[str] = None


@dataclass
class BinaryOp:
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp:
    op: str
    operand: Any


@dataclass
class OrderByItem:
    expr: Any
    ascending: bool = True


@dataclass
class JoinClause:
    table: str
    alias: Optional[str]
    condition: Any
    join_type: str = "INNER"


@dataclass
class Assignment:
    column: str
    value: Any


@dataclass
class ColumnDef:
    name: str
    col_type: str
    nullable: bool = True
    primary_key: bool = False


@dataclass
class SelectStmt:
    columns: List
    from_table: str
    from_alias: Optional[str]
    joins: List[JoinClause]
    where: Optional[Any]
    order_by: List[OrderByItem]
    limit: Optional[int]


@dataclass
class InsertStmt:
    table: str
    columns: List[str]
    values: List[List]


@dataclass
class UpdateStmt:
    table: str
    assignments: List[Assignment]
    where: Optional[Any]


@dataclass
class DeleteStmt:
    table: str
    where: Optional[Any]


@dataclass
class CreateTableStmt:
    table: str
    column_defs: List[ColumnDef]


def tokenize(sql: str) -> List[Token]:
    tokens = []
    i = 0
    n = len(sql)
    while i < n:
        if sql[i].isspace():
            i += 1
            continue
        if sql[i:i+2] == '--':
            while i < n and sql[i] != '\n':
                i += 1
            continue
        pos = i
        c = sql[i]
        if c in ('"', "'"):
            quote = c
            i += 1
            start = i
            while i < n and sql[i] != quote:
                if sql[i] == '\\':
                    i += 1
                i += 1
            if i >= n:
                raise LexError(f"Unterminated string at pos {pos}")
            value = sql[start:i]
            i += 1
            tokens.append(Token(TT.STRING_LIT, value, pos))
            continue
        if c.isdigit() or (c == '.' and i+1 < n and sql[i+1].isdigit()):
            start = i
            is_float = False
            while i < n and sql[i].isdigit():
                i += 1
            if i < n and sql[i] == '.':
                is_float = True
                i += 1
                while i < n and sql[i].isdigit():
                    i += 1
            num_str = sql[start:i]
            if is_float:
                tokens.append(Token(TT.FLOAT_LIT, float(num_str), pos))
            else:
                tokens.append(Token(TT.INT_LIT, int(num_str), pos))
            continue
        if c.isalpha() or c == '_':
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == '_'):
                i += 1
            word = sql[start:i]
            lower = word.lower()
            if lower in KEYWORDS:
                tt = KEYWORDS[lower]
                if tt == TT.BOOL_LIT:
                    value = lower == 'true'
                elif tt == TT.NULL_LIT:
                    value = None
                else:
                    value = word
                tokens.append(Token(tt, value, pos))
            else:
                tokens.append(Token(TT.IDENT, word, pos))
            continue
        two = sql[i:i+2]
        if two == '!=':
            tokens.append(Token(TT.NEQ, '!=', pos)); i += 2; continue
        if two == '<>':
            tokens.append(Token(TT.NEQ, '<>', pos)); i += 2; continue
        if two == '<=':
            tokens.append(Token(TT.LTE, '<=', pos)); i += 2; continue
        if two == '>=':
            tokens.append(Token(TT.GTE, '>=', pos)); i += 2; continue
        ops = {'=': TT.EQ, '<': TT.LT, '>': TT.GT, '(': TT.LPAREN,
               ')': TT.RPAREN, ',': TT.COMMA, ';': TT.SEMI, '.': TT.DOT, '*': TT.STAR}
        if c in ops:
            tokens.append(Token(ops[c], c, pos)); i += 1; continue
        raise LexError(f"Unexpected character {c!r} at pos {pos}")
    tokens.append(Token(TT.EOF, None, n))
    return tokens


class Parser:
    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        t = self._tokens[self._pos]
        self._pos += 1
        return t

    def _check(self, *types) -> bool:
        return self._peek().type in types

    def _match(self, *types) -> Optional[Token]:
        if self._check(*types):
            return self._advance()
        return None

    def _expect(self, tt: TT, msg: str = None) -> Token:
        if self._peek().type == tt:
            return self._advance()
        raise ParseError(msg or f"Expected {tt.name}, got {self._peek().type.name!r} at pos {self._peek().pos}")

    def _expect_ident(self, msg: str = None) -> str:
        t = self._peek()
        if t.type == TT.IDENT or t.type in KEYWORD_IDENT_TYPES:
            self._advance()
            return t.value if isinstance(t.value, str) else str(t.value)
        raise ParseError(msg or f"Expected identifier, got {t.type.name!r} at pos {t.pos}")

    def parse(self):
        t = self._peek()
        if t.type == TT.SELECT:
            return self._parse_select()
        if t.type == TT.INSERT:
            return self._parse_insert()
        if t.type == TT.UPDATE:
            return self._parse_update()
        if t.type == TT.DELETE:
            return self._parse_delete()
        if t.type == TT.CREATE:
            return self._parse_create()
        raise ParseError(f"Unknown statement type {t.type.name!r} at pos {t.pos}")

    def _parse_select(self):
        self._expect(TT.SELECT)
        columns = self._parse_select_columns()
        self._expect(TT.FROM)
        from_table = self._expect_ident("Expected table name")
        from_alias = None
        if self._check(TT.AS):
            self._advance()
            from_alias = self._expect_ident()
        elif self._peek().type == TT.IDENT:
            from_alias = self._advance().value
        joins = []
        while self._check(TT.JOIN, TT.INNER, TT.LEFT):
            joins.append(self._parse_join())
        where = None
        if self._match(TT.WHERE):
            where = self._parse_expr()
        order_by = []
        if self._check(TT.ORDER):
            self._advance()
            self._expect(TT.BY)
            order_by = self._parse_order_by()
        limit = None
        if self._match(TT.LIMIT):
            limit = self._expect(TT.INT_LIT).value
        return SelectStmt(columns=columns, from_table=from_table, from_alias=from_alias,
                          joins=joins, where=where, order_by=order_by, limit=limit)

    def _parse_select_columns(self) -> List:
        cols = []
        cols.append(self._parse_select_col())
        while self._match(TT.COMMA):
            cols.append(self._parse_select_col())
        return cols

    def _parse_select_col(self):
        if self._check(TT.STAR):
            self._advance()
            return Star()
        expr = self._parse_primary()
        if self._check(TT.AS):
            self._advance()
            self._expect_ident()  # alias (currently unused in output)
        return expr

    def _parse_join(self) -> JoinClause:
        join_type = "INNER"
        if self._match(TT.LEFT):
            join_type = "LEFT"
            self._match(TT.INNER)
        elif self._match(TT.INNER):
            pass
        self._expect(TT.JOIN)
        table = self._expect_ident("Expected table name in JOIN")
        alias = None
        if self._check(TT.AS):
            self._advance()
            alias = self._expect_ident()
        elif self._peek().type == TT.IDENT:
            alias = self._advance().value
        self._expect(TT.ON)
        condition = self._parse_expr()
        return JoinClause(table=table, alias=alias, condition=condition, join_type=join_type)

    def _parse_order_by(self) -> List[OrderByItem]:
        items = []
        expr = self._parse_primary()
        ascending = True
        if self._match(TT.DESC):
            ascending = False
        elif self._match(TT.ASC):
            ascending = True
        items.append(OrderByItem(expr=expr, ascending=ascending))
        while self._match(TT.COMMA):
            expr = self._parse_primary()
            ascending = True
            if self._match(TT.DESC):
                ascending = False
            elif self._match(TT.ASC):
                ascending = True
            items.append(OrderByItem(expr=expr, ascending=ascending))
        return items

    def _parse_insert(self):
        self._expect(TT.INSERT)
        self._expect(TT.INTO)
        table = self._expect_ident("Expected table name")
        columns = []
        if self._match(TT.LPAREN):
            columns.append(self._expect_ident())
            while self._match(TT.COMMA):
                columns.append(self._expect_ident())
            self._expect(TT.RPAREN)
        self._expect(TT.VALUES)
        values = [self._parse_value_row()]
        while self._match(TT.COMMA):
            values.append(self._parse_value_row())
        return InsertStmt(table=table, columns=columns, values=values)

    def _parse_value_row(self) -> List:
        self._expect(TT.LPAREN)
        vals = [self._parse_primary()]
        while self._match(TT.COMMA):
            vals.append(self._parse_primary())
        self._expect(TT.RPAREN)
        return vals

    def _parse_update(self):
        self._expect(TT.UPDATE)
        table = self._expect_ident("Expected table name")
        self._expect(TT.SET)
        assignments = []
        col = self._expect_ident()
        self._expect(TT.EQ)
        val = self._parse_primary()
        assignments.append(Assignment(column=col, value=val))
        while self._match(TT.COMMA):
            col = self._expect_ident()
            self._expect(TT.EQ)
            val = self._parse_primary()
            assignments.append(Assignment(column=col, value=val))
        where = None
        if self._match(TT.WHERE):
            where = self._parse_expr()
        return UpdateStmt(table=table, assignments=assignments, where=where)

    def _parse_delete(self):
        self._expect(TT.DELETE)
        self._expect(TT.FROM)
        table = self._expect_ident("Expected table name")
        where = None
        if self._match(TT.WHERE):
            where = self._parse_expr()
        return DeleteStmt(table=table, where=where)

    def _parse_create(self):
        self._expect(TT.CREATE)
        self._expect(TT.TABLE)
        table = self._expect_ident("Expected table name")
        self._expect(TT.LPAREN)
        col_defs = [self._parse_col_def()]
        while self._match(TT.COMMA):
            col_defs.append(self._parse_col_def())
        self._expect(TT.RPAREN)
        return CreateTableStmt(table=table, column_defs=col_defs)

    def _parse_col_def(self) -> ColumnDef:
        name = self._expect_ident("Expected column name")
        if self._check(TT.INT):
            col_type = "INT"; self._advance()
        elif self._check(TT.FLOAT):
            col_type = "FLOAT"; self._advance()
        elif self._check(TT.TEXT):
            col_type = "TEXT"; self._advance()
        elif self._check(TT.BOOL):
            col_type = "BOOL"; self._advance()
        else:
            raise ParseError(f"Expected column type at pos {self._peek().pos}")
        return ColumnDef(name=name, col_type=col_type)

    def _parse_expr(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._match(TT.OR):
            right = self._parse_and()
            left = BinaryOp('OR', left, right)
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self._match(TT.AND):
            right = self._parse_not()
            left = BinaryOp('AND', left, right)
        return left

    def _parse_not(self):
        if self._match(TT.NOT):
            operand = self._parse_not()
            return UnaryOp('NOT', operand)
        return self._parse_comparison()

    def _parse_comparison(self):
        left = self._parse_primary()
        if self._check(TT.IS):
            self._advance()
            if self._match(TT.NOT):
                self._expect(TT.NULL_LIT)
                return UnaryOp('IS NOT NULL', left)
            else:
                self._expect(TT.NULL_LIT)
                return UnaryOp('IS NULL', left)
        op_map = {
            TT.EQ: '=', TT.NEQ: '!=', TT.LT: '<', TT.GT: '>',
            TT.LTE: '<=', TT.GTE: '>='
        }
        for tt, op in op_map.items():
            if self._match(tt):
                right = self._parse_primary()
                return BinaryOp(op, left, right)
        return left

    def _parse_primary(self):
        t = self._peek()
        if t.type == TT.INT_LIT:
            self._advance(); return Literal(t.value)
        if t.type == TT.FLOAT_LIT:
            self._advance(); return Literal(t.value)
        if t.type == TT.STRING_LIT:
            self._advance(); return Literal(t.value)
        if t.type == TT.BOOL_LIT:
            self._advance(); return Literal(t.value)
        if t.type == TT.NULL_LIT:
            self._advance(); return Literal(None)
        if t.type == TT.STAR:
            self._advance(); return Star()
        if t.type == TT.LPAREN:
            self._advance()
            expr = self._parse_expr()
            self._expect(TT.RPAREN)
            return expr
        if t.type == TT.IDENT or t.type in KEYWORD_IDENT_TYPES:
            self._advance()
            name = t.value if isinstance(t.value, str) else str(t.value)
            if self._match(TT.DOT):
                if self._check(TT.STAR):
                    self._advance()
                    return Star(table=name)
                col = self._expect_ident()
                return Identifier(f"{name}.{col}")
            return Identifier(name)
        raise ParseError(f"Unexpected token {t.type.name!r} at pos {t.pos}")


def parse(sql: str):
    tokens = tokenize(sql)
    parser = Parser(tokens)
    return parser.parse()
