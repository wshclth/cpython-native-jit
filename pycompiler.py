from typing import get_type_hints
from inspect import signature, getfullargspec
import ast
import inspect
import mmap
import subprocess
import ctypes
import os
import pycompiler

save_mmaped = {}
jitted_dispatch = {}

def compileme(func):
    """compileme decorator performs native python jit compilation"""
    global jitted_dispatch

    def patched_func(*args):
        sig = signature(func)
        if not func in pycompiler.jitted_dispatch:
            parameters = [v.annotation for _, v in sig.parameters.items()]
            compilable = ast.parse(inspect.getsource(func))
            compiler = Compiler()
            src = compiler.visit(compilable)

            with open("_jit.c", "w") as fd:
                fd.write(src)

            subprocess.call(["gcc", "-O2", "-c", "_jit.c"])
            subprocess.call(["objcopy", "-O", "binary", "-j", ".text", "_jit.o"])

            jitted_fp = os.open("./_jit.o", os.O_RDWR)
            mm_buf = mmap.mmap(
                    jitted_fp,
                    0,
                    mmap.MAP_PRIVATE,
                    mmap.PROT_READ | mmap.PROT_EXEC)
            pycompiler.save_mmaped = mm_buf

            obj = ctypes.py_object(mm_buf)
            address = ctypes.c_void_p()
            length = ctypes.c_ssize_t()
            ctypes.pythonapi.PyObject_AsReadBuffer(obj, ctypes.byref(address), ctypes.byref(length))
            int_pointer = address.value

            prototype = ctypes.CFUNCTYPE(sig.return_annotation, *parameters)
            jitted_function = prototype(int_pointer)
            pycompiler.jitted_dispatch[func] = jitted_function

        
        cargs = [v.annotation(args[idx]) for idx, (_, v) in enumerate(sig.parameters.items())]
        val = pycompiler.jitted_dispatch[func](*cargs)
        return val

    return patched_func

class Compiler(ast.NodeVisitor):
    def __init__(self):
        super().__init__()

        self.used_variables = {}

        self.dispatch = {
            ast.Module: self.on_Module,
            ast.FunctionDef: self.on_FunctionDef,
            ast.BinOp: self.on_BinOp,
            ast.Mult: self.on_Mult,
            ast.Add: self.on_Add,
            ast.Div: self.on_Div,
            ast.operator: self.on_Operator,
            ast.Name: self.on_Name,
            ast.Return: self.on_Return,
            ast.AnnAssign: self.on_AnnAssign,
            ast.Constant: self.on_Constant,
            ast.For: self.on_For,
            ast.AugAssign: self.on_AugAssign,
            list: self.on_list,
        }

    def visit(self, node):
        return self.dispatch[type(node)](node)

    def on_list(self, nodes):
        return '\n'.join([self.dispatch[type(x)](x) for x in nodes])

    def on_Constant(self, node: ast.Constant):
        return node.s

    def on_arg(self, node: ast.arg):
        arg_CType = self.to_CType(node.annotation)
        return f"{arg_CType} {node.arg}"

    def on_Return(self, node: ast.Return):
        return_CBody = self.dispatch[type(node.value)](node.value)
        return f"return {return_CBody};"

    def on_Add(self, node: ast.Add):
        return "+"

    def on_Mult(self, node: ast.Mult):
        return "*"

    def on_Div(self, node: ast.Div):
        return "/"

    def on_AugAssign(self, node: ast.AugAssign):
        store_name = node.target.id
        operation = self.dispatch[type(node.op)](node.op)
        value = node.value.id
        return f"{store_name} {operation}= {value};"

    def on_For(self, node: ast.For):
        # AST Match this for only if iter call is to "range"
        if type(node.iter) != ast.Call:
            raise Exception("error: only `for <var> in range(A, B)` is supported")

        iter_call: ast.Call = node.iter
        if type(iter_call.func) != ast.Name:
            raise Exception("error: only `for <var> in range(A, B)` is supported")

        iter_call_func: ast.Name = iter_call.func
        if iter_call_func.id != "range":
            raise Exception("error: only `for <var> in range(A, B)` is supported")

        if type(node.target) != ast.Name:
            raise Exception("error: only `for <var> in range(A, B)` is supported")

        lower_bound = iter_call.args[0].s
        upper_bound = iter_call.args[1].s
        loop_var = node.target.id

        for_template = f"for (int {loop_var} = {lower_bound}; {loop_var} < {upper_bound}; ++{loop_var}) {{" + "\n"
        for_template += '\n'.join(["\t\t" + self.dispatch[type(x)](x) for x in node.body])
        for_template += "\n"
        for_template += "\t}\n"
        return for_template

    def on_AnnAssign(self, node: ast.AnnAssign):
        type_CType = self.to_CType(node.annotation)
        name = node.target.id
        assignment = self.dispatch[type(node.value)](node.value)

        if not name in self.used_variables:
            return f"{type_CType} {name} = {assignment};"
        else:
            return f"{name} = {assignment};"

    def on_Name(self, node: ast.Name):
        if type(node.ctx) == ast.Load:
            return node.id
        elif type(node.ctx) == ast.Store:
            return f"{node.id} = "

    def on_Operator(self, node: ast.operator):
        return self.dispatch[type(node.op)](node.op)

    def on_BinOp(self, node: ast.BinOp):
        operator = self.dispatch[type(node.op)](node.op)

        left_CCode = self.dispatch[type(node.left)](node.left)
        right_CCode = self.dispatch[type(node.right)](node.right)
        return f"{left_CCode} {operator} {right_CCode}"

    def on_Module(self, node: ast.Module):
        return self.dispatch[type(node.body)](node.body)

    def on_FunctionDef(self, node: ast.FunctionDef):
        name: ast.Name = node.returns
        return_CType = self.to_CType(name)
        function_name = node.name

        arglist = [self.on_arg(x) for x in node.args.args]
        arglist_CArgs = ', '.join(arglist)

        function_CFunction = f"{return_CType} {function_name}({arglist_CArgs}) {{" + "\n"
        body_CBody = '\n'.join(['\t' + self.dispatch[type(x)](x) for x in node.body])
        body_CBody += "\n"
        return f"{function_CFunction}{body_CBody}}}" + "\n"

    def to_CType(self, name: ast.Name):
        match name.id:
            case "c_float":
                return "float"
            case _:
                raise Exception(f"unknown translation of type {name.id}")

