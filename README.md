# Native Python JIT
The following repository serves no purpose. It is a proof on concept for a bigger
idea. The following repo shows it is possible without external libraries to,

1. CPython C extensions are difficult to write correctly.
2. CPython, PyO3, MyPy .... require compiled `.so` objects, which introduce pain in building
3. PyPy and pypy like projects require a different python interpreter, making compatability with sufficiently large projects difficult.


Proof of concept shows that
1. Compile a subset of python to C.
2. Invoke GCC at runtime with optimizations
3. Instruct the CPython interpreter to execute arbitrary mmaped code produced via gcc.

### Big Picture

1. Define strict subset of python like mypy.
2. JitCompile subsets of code marked as jitable
