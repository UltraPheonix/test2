"""MemDB interactive REPL."""
import sys
from memdb import Database


def main():
    db = Database()
    db.execute("CREATE TABLE users (id INT, name TEXT, age INT, active BOOL)")
    db.execute("CREATE TABLE orders (id INT, user_id INT, amount FLOAT)")
    db.create_index("users", "id", "hash")
    db.create_index("users", "age", "btree")

    print("MemDB v1.0 - In-Memory Database Engine")
    print("Type 'exit' to quit, 'tables' to list tables, 'log' to show transaction log")
    print()

    while True:
        try:
            sql = input("memdb> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not sql:
            continue
        if sql.lower() == 'exit':
            break
        if sql.lower() == 'tables':
            print("Tables:", ", ".join(db.list_tables()))
            continue
        if sql.lower() == 'log':
            for entry in db.transaction_log()[-10:]:
                print(f"  [{entry['seq']}] {entry['op']} {entry['table']}")
            continue

        try:
            cols, rows = db.execute(sql)
            if rows:
                widths = {c: len(c) for c in cols}
                for row in rows:
                    for c in cols:
                        widths[c] = max(widths[c], len(str(row.get(c, ''))))
                header = " | ".join(c.ljust(widths[c]) for c in cols)
                print(header)
                print("-" * len(header))
                for row in rows:
                    print(" | ".join(str(row.get(c, '')).ljust(widths[c]) for c in cols))
                print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
            elif cols is not None:
                print("OK")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == '__main__':
    main()
