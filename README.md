# Native Python JIT
The following repository serves no purpose. It is a proof on concept for a bigger
idea. The following repo shows it is possible without external libraries to,

1. Compile a subset of python to C.
2. Invoke GCC at runtime with optimizations
3. Instruct the CPython interpreter to execute arbitrary mmaped code produced via gcc.

### Big Picture

1. Introduce `CALL_NATIVE` op code to CPython interpreter.
2. Package JIT compiled code into `.pyc`.
