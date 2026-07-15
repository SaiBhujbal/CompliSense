"""Reproduce server.py's agent_runner subprocess spawn."""
import os
import subprocess
import sys
import time

env = dict(
    os.environ,
    KMP_DUPLICATE_LIB_OK="TRUE",
    OMP_NUM_THREADS="1",
    MKL_NUM_THREADS="1",
    SHOWCASE_ALL_AGENTS="false",
)
q = "GlowLeaf vs Himalaya competitor opening customer lens short"
proc = subprocess.Popen(
    [sys.executable, "-u", "agent_runner.py", "--json", q],
    cwd="/app",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    encoding="utf-8",
    errors="replace",
    env=env,
)
t0 = time.time()
lines = 0
while True:
    line = proc.stdout.readline()
    if not line:
        if proc.poll() is not None:
            break
        if time.time() - t0 > 150:
            print("TIMEOUT")
            proc.kill()
            break
        continue
    lines += 1
    print("OUT", line[:240].rstrip())
    sys.stdout.flush()
    if '"done"' in line:
        break
err = ""
try:
    err = (proc.stderr.read() or "")[-2500:]
except Exception as e:
    err = str(e)
print("RETURN", proc.poll(), "lines", lines, "elapsed", round(time.time() - t0, 1))
print("ERR", err)
