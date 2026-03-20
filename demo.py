import os
import time
import shutil
import importlib
import cache_file  # Import the module object itself

# Force Python to re-read cache_file.py from disk
importlib.reload(cache_file)

# Re-import the specific functions you need into your namespace
from cache_file import cache_file, track_file, cache_tree_nodes

# --- Setup Directories ---
CACHE_DIR = "./demo_cache"
DATA_FILE = "data.txt"

# Clean up previous runs for a fresh demo
if os.path.exists(CACHE_DIR):
    shutil.rmtree(CACHE_DIR)
if os.path.exists(DATA_FILE):
    os.remove(DATA_FILE)

# --- Define the Cached Function ---
@cache_file(cache_dir=CACHE_DIR)
def count_words(filepath):
    """
    Simulates a heavy process. 
    We use track_file() to explicitly tell the system: 
    'If this specific file changes, invalidate my cache.'
    """
    print("  [BUSY] Reading file and computing...")
    time.sleep(1.5)  # Simulate work
    
    # Register the file dependency
    real_path = track_file(filepath)
    
    with open(real_path, 'r') as f:
        content = f.read()
        return len(content.split())

# --- helper to print section headers ---
def print_header(msg):
    print(f"\n{'-'*10} {msg} {'-'*10}")

# =======================================================
# EXECUTION
# =======================================================

# 1. Create initial data
print_header("Step 1: Creating Data")
with open(DATA_FILE, "w") as f:
    f.write("Hello world, this is a test.")
print(f"Created {DATA_FILE}")

# 2. First Run (Cold Cache)
print_header("Step 2: First Run (Cold Cache)")
start = time.time()
res1 = count_words(DATA_FILE)
print(f"Result: {res1} words")
print(f"Time:   {time.time() - start:.2f}s (Expected ~1.5s)")

# 3. Second Run (Warm Cache)
print_header("Step 3: Second Run (Warm Cache)")
start = time.time()
res2 = count_words(DATA_FILE)
print(f"Result: {res2} words")
print(f"Time:   {time.time() - start:.2f}s (Expected ~0.0s)")

# 4. Modify Data
print_header("Step 4: Modifying Data File")
with open(DATA_FILE, "a") as f:
    f.write(" We are adding more words now.")
print("File updated.")

# 5. Third Run (Cache Invalidation)
print_header("Step 5: Third Run (Detects Change)")
start = time.time()
res3 = count_words(DATA_FILE)
print(f"Result: {res3} words")
print(f"Time:   {time.time() - start:.2f}s (Expected ~1.5s)")

# 6. Inspect the Graph
print_header("Step 6: Cache Tree Info")
nodes = cache_tree_nodes()
print(f"Total Nodes tracked in session: {len(nodes)}")
for node_id, data in nodes.items():
    print(f"- Node: {data['fname']}")
    print(f"  Files tracked: {data['files']}")