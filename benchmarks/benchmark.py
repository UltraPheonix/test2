"""Benchmarking suite: query latency, insert throughput, memory usage, index performance."""
import time
import tracemalloc
from memdb import Database


def bench_insert_throughput(n=10000):
    db = Database()
    db.execute("CREATE TABLE bench (id INT, name TEXT, value INT)")
    start = time.perf_counter()
    for i in range(n):
        db.execute(f"INSERT INTO bench (id, name, value) VALUES ({i}, 'item{i}', {i*2})")
    elapsed = time.perf_counter() - start
    rows_per_sec = n / elapsed
    return {'rows': n, 'elapsed_s': elapsed, 'rows_per_sec': rows_per_sec}


def bench_select_latency(n=1000):
    db = Database()
    db.execute("CREATE TABLE bench (id INT, value INT)")
    for i in range(100):
        db.execute(f"INSERT INTO bench (id, value) VALUES ({i}, {i})")
    latencies = []
    for _ in range(n):
        start = time.perf_counter()
        db.execute("SELECT * FROM bench WHERE value > 50")
        latencies.append(time.perf_counter() - start)
    return {
        'queries': n,
        'avg_ms': sum(latencies) / len(latencies) * 1000,
        'min_ms': min(latencies) * 1000,
        'max_ms': max(latencies) * 1000,
    }


def bench_index_vs_seq_scan(n=10000):
    # Seq scan
    db_seq = Database()
    db_seq.execute("CREATE TABLE bench (id INT, value INT)")
    for i in range(n):
        db_seq.execute(f"INSERT INTO bench (id, value) VALUES ({i}, {i})")
    start = time.perf_counter()
    db_seq.execute(f"SELECT * FROM bench WHERE id = {n // 2}")
    seq_time = time.perf_counter() - start

    # Index scan
    db_idx = Database()
    db_idx.execute("CREATE TABLE bench (id INT, value INT)")
    for i in range(n):
        db_idx.execute(f"INSERT INTO bench (id, value) VALUES ({i}, {i})")
    db_idx.create_index('bench', 'id', 'hash')
    start = time.perf_counter()
    db_idx.execute(f"SELECT * FROM bench WHERE id = {n // 2}")
    idx_time = time.perf_counter() - start

    return {
        'n': n,
        'seq_scan_ms': seq_time * 1000,
        'index_scan_ms': idx_time * 1000,
        'speedup': seq_time / idx_time if idx_time > 0 else float('inf'),
    }


def bench_memory_usage(n=10000):
    tracemalloc.start()
    db = Database()
    db.execute("CREATE TABLE bench (id INT, name TEXT, value INT)")
    for i in range(n):
        db.execute(f"INSERT INTO bench (id, name, value) VALUES ({i}, 'item{i}', {i})")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        'rows': n,
        'current_mb': current / 1024 / 1024,
        'peak_mb': peak / 1024 / 1024,
    }


def bench_order_by(n=10000):
    db = Database()
    db.execute("CREATE TABLE bench (id INT, value INT)")
    for i in range(n):
        db.execute(f"INSERT INTO bench (id, value) VALUES ({i}, {n - i})")
    start = time.perf_counter()
    db.execute("SELECT * FROM bench ORDER BY value ASC")
    elapsed = time.perf_counter() - start
    return {'rows': n, 'elapsed_ms': elapsed * 1000}


def bench_join(n=1000):
    db = Database()
    db.execute("CREATE TABLE users (id INT, name TEXT)")
    db.execute("CREATE TABLE orders (id INT, user_id INT, amount FLOAT)")
    for i in range(n):
        db.execute(f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}')")
    for i in range(n):
        db.execute(f"INSERT INTO orders (id, user_id, amount) VALUES ({i}, {i % n}, {i * 1.5})")
    start = time.perf_counter()
    db.execute("SELECT * FROM users u JOIN orders o ON u.id = o.user_id")
    elapsed = time.perf_counter() - start
    return {'users': n, 'orders': n, 'elapsed_ms': elapsed * 1000}


def print_table(title, data):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    for k, v in data.items():
        if isinstance(v, float):
            print(f"  {k:25s}: {v:.4f}")
        else:
            print(f"  {k:25s}: {v}")


def main():
    print("MemDB Benchmark Suite")
    print("=" * 50)

    print("\n[1/6] Insert Throughput (n=10000)...")
    result = bench_insert_throughput(10000)
    print_table("Insert Throughput", result)

    print("\n[2/6] Select Latency (n=1000)...")
    result = bench_select_latency(1000)
    print_table("Select Latency", result)

    print("\n[3/6] Index vs Seq Scan (n=10000)...")
    result = bench_index_vs_seq_scan(10000)
    print_table("Index vs Seq Scan", result)

    print("\n[4/6] Memory Usage (n=10000)...")
    result = bench_memory_usage(10000)
    print_table("Memory Usage", result)

    print("\n[5/6] Order By (n=10000)...")
    result = bench_order_by(10000)
    print_table("Order By", result)

    print("\n[6/6] Join (n=1000)...")
    result = bench_join(1000)
    print_table("Join", result)

    print("\n" + "=" * 50)
    print("Benchmarks complete.")


if __name__ == '__main__':
    main()
