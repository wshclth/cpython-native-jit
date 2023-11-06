from typing import Type
from pycompiler import compileme
from typing import TypeAlias
from ctypes import c_float, c_int

import numpy as np

@compileme
def jitted_bench() -> c_float:
    accumulator: c_float = 0
    for x in range(0, 100):
        for y in range(0, 100):
            accumulator += y
        accumulator += x
    return accumulator

def bench() -> c_float:
    accumulator: c_float = 0
    for x in range(0, 100):
        for y in range(0, 100):
            accumulator += y
        accumulator += x
    return accumulator


# mul(10, 10)
import time

a_mean = []
for _ in range(100):
    start = time.monotonic_ns()
    bench()
    end = time.monotonic_ns()
    a_mean.append((end - start))

b_mean = []
for _ in range(100):
    start = time.monotonic_ns()
    jitted_bench()
    end = time.monotonic_ns()
    b_mean.append((end - start))

from matplotlib import pyplot as plt
fig, ax = plt.subplots()
plt.plot(np.array(a_mean[1:]), label="native python")
plt.plot(np.array(b_mean[1:]), label="jit compiled -O2")

ax.grid(True)
ax.set_xlabel("sample #")
ax.set_ylabel("ns")
plt.legend()
plt.show()
