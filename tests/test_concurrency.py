"""Concurrency tests using asyncio."""
import asyncio
import pytest
from memdb import Database


class AsyncDatabase:
    """Thread-safe async wrapper around Database."""
    def __init__(self):
        self._db = Database()
        self._lock = asyncio.Lock()

    async def execute(self, sql):
        async with self._lock:
            return self._db.execute(sql)

    async def create_index(self, table, column, index_type="hash"):
        async with self._lock:
            return self._db.create_index(table, column, index_type)


@pytest.mark.asyncio
async def test_concurrent_inserts():
    db = AsyncDatabase()
    await db.execute("CREATE TABLE users (id INT, name TEXT)")

    async def insert_row(i):
        await db.execute(f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}')")

    await asyncio.gather(*[insert_row(i) for i in range(20)])
    _, rows = await db.execute("SELECT * FROM users")
    assert len(rows) == 20


@pytest.mark.asyncio
async def test_concurrent_reads():
    db = AsyncDatabase()
    await db.execute("CREATE TABLE data (id INT, value INT)")
    for i in range(5):
        await db.execute(f"INSERT INTO data (id, value) VALUES ({i}, {i*10})")

    async def read():
        _, rows = await db.execute("SELECT * FROM data")
        return rows

    results = await asyncio.gather(*[read() for _ in range(10)])
    for rows in results:
        assert len(rows) == 5


@pytest.mark.asyncio
async def test_read_write_interleaving():
    db = AsyncDatabase()
    await db.execute("CREATE TABLE events (id INT, name TEXT)")

    results = []

    async def writer(i):
        await db.execute(f"INSERT INTO events (id, name) VALUES ({i}, 'Event{i}')")

    async def reader():
        _, rows = await db.execute("SELECT * FROM events")
        results.append(len(rows))

    # Interleave writes and reads
    tasks = []
    for i in range(5):
        tasks.append(writer(i))
        tasks.append(reader())
    await asyncio.gather(*tasks)

    # Final read should have all 5 rows
    _, final_rows = await db.execute("SELECT * FROM events")
    assert len(final_rows) == 5
