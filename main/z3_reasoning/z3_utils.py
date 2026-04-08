from onnx import numpy_helper
from z3 import *
import onnx
import numpy as np


def onnx2z3(onnx_path):
    """
    Parses onnx model and converts it to z3 format. For every output neuron, a symbolic expression is parsed, representing
    its computation.

    :param onnx_path: path to the desired onnx model
    :return:
        output_keys (list): list of keys, defining the names of the output neurons
        output_formulas (dict) dictionary, holding for every output neuron the sym-expr ["expr"] and variables ["vars"]
    """
    # Load onnx model
    onnx_model = onnx.load(onnx_path)
    graph = onnx_model.graph

    # Storing all tensors in a dictionary
    intermediate_tensors = {}

    # 1. Loading weights and biases
    for init in graph.initializer:
        arr = numpy_helper.to_array(init)
        flat_arr = arr.flatten()
        z3_list = [z3.RealVal(str(round(float(x), 6))) for x in flat_arr]
        z3_arr = np.array(z3_list, dtype=object).reshape(arr.shape)
        intermediate_tensors[clean_name(init.name)] = z3_arr

    # 2. Declaring input vars
    input_vars = []
    for inp in graph.input:
        shape = [d.dim_value for d in inp.type.tensor_type.shape.dim]
        shape = [d if d > 0 else 1 for d in shape]

        flat_size = np.prod(shape)
        vars_flat = [z3.Real(f"{clean_name(inp.name)}_{i}") for i in range(flat_size)]
        input_vars.extend(vars_flat)
        intermediate_tensors[clean_name(inp.name)] = np.array(vars_flat, dtype=object).reshape(shape)

    # 3. Iterating through the network graph layers
    for node in graph.node:
        node_inputs = [intermediate_tensors[clean_name(name)] for name in node.input if clean_name(name) in intermediate_tensors]

        if node.op_type == "MatMul":
            # Performing matmul with np arrays, but z3 objects as entries
            out = np.matmul(node_inputs[0], node_inputs[1])

        elif node.op_type == "Add":
            out = np.add(node_inputs[0], node_inputs[1])

        elif node.op_type == "Relu":
            relu_func = np.vectorize(lambda x: z3.If(x > 0, x, z3.RealVal(0)))
            out = relu_func(node_inputs[0])

        elif node.op_type == "Gemm":
            # Assuming Bias is stored at inputs[3]
            inp = node_inputs[0]
            weights = node_inputs[1]
            biases = node_inputs[2] if len(node_inputs) > 2 else 0

            # Fetching attributes
            alpha = 1.0
            beta = 1.0
            transA = 0
            transB = 0
            for attr in node.attribute:
                if attr.name == 'alpha':
                    alpha = attr.f
                elif attr.name == 'beta':
                    beta = attr.f
                elif attr.name == 'transA':
                    transA = attr.i
                elif attr.name == 'transB':
                    transB = attr.i

            if transA: A = A.T
            if transB: B = B.T
            out = alpha * np.matmul(inp, weights) + beta * biases

        elif node.op_type == "Constant":
            for attr in node.attribute:
                if attr.name == 'value':
                    arr = numpy_helper.to_array(attr.t)
                    if arr.ndim == 0:
                        out = np.array(z3.RealVal(str(round(float(arr), 6))), dtype=object)
                    else:
                        flat_arr = arr.flatten()
                        z3_list = [z3.RealVal(str(round(float(x), 6))) for x in flat_arr]
                        out = np.array(z3_list, dtype=object).reshape(arr.shape)
                    break

        elif node.op_type == "Mul":
            out = np.multiply(node_inputs[0], node_inputs[1])

        else:
            raise ValueError(f"Current node-optype '{node.op_type}' is not supported!")

        intermediate_tensors[clean_name(node.output[0])] = out

    print(f"Building z3 formulas was successful.")

    # Build output dictionary with corresponding z3 expression
    output_formulas = {}
    out_names = [clean_name(out.name) for out in graph.output]
    output_keys = []
    for out_idx, out_name in enumerate(out_names):
        final_tensor = intermediate_tensors[out_name].flatten()

        for i, neuron_expr in enumerate(final_tensor):
            simplified_expr = z3.simplify(neuron_expr)
            expressions_input_vars = get_input_vars(simplified_expr)
            neuron_key = f"{out_name}_{i}"
            output_formulas[neuron_key] = {
                "expr": simplified_expr,
                "vars": expressions_input_vars,
            }
            output_keys.append(neuron_key)

    return output_keys, output_formulas


def extract_mbp_core(expr, f_model, r_substitution):
    """
    Traverses through the AST tree and extracts path that is 'TRUE' by given model

    :param expr: original formular (expression)
    :param f_model: model with assignment for y variable
    :param r_substitution: current values for r to substitute

    :return: linear expression of the AST with only active paths included for given r
    """
    path_conditions = []

    # Recursively traverse through the AST
    def traverse(e):
        # In this case current node is a leaf
        if not z3.is_app(e):
            return e

        decl = e.decl()
        # In this case, we are at a ITE node
        if decl.kind() == z3.Z3_OP_ITE:
            # If, then, else expressions
            cond, then_expr, else_expr = e.children()

            # Check 'If' condition to be true for current r
            cond_with_r = z3.substitute(cond, *r_substitution)
            cond_val = f_model.eval(cond_with_r, model_completion=True)

            # 'If' condition is true, so THEN is 'executed'
            if z3.is_true(cond_val):
                # Path to 'THEN' branch is stored
                path_conditions.append(traverse(cond))
                # We traverse into 'THEN' branch
                return traverse(then_expr)
            # 'If' condition is false, so ELSE branch is 'executed'
            else:
                # Path to 'ELSE' branch is stored (ensure that 'IF' is not true for next F-solver iteration)
                path_conditions.append(z3.Not(traverse(cond)))
                # We traverse into the 'ELSE' branch
                return traverse(else_expr)
        else:
            # Otherwise dive into all children nodes
            children = [traverse(c) for c in e.children()]
            return decl(*children)

    # Linear expression of the AST, where ReLU branches have been replaced by their branch which is active for current r
    linear_expr = traverse(expr)

    return z3.And(linear_expr, *path_conditions)


def z3_setup_e_solver():
    pass


def get_input_vars(expr):
    vars_set = set()
    walk(expr, vars_set)
    sorted_list = sorted(vars_set, key=lambda var: str(var))
    return sorted_list


def walk(expr, vars_set):
    if z3.is_const(expr) and expr.decl().kind() == z3.Z3_OP_UNINTERPRETED:
        vars_set.add(expr)
    else:
        for child in expr.children():
            walk(child, vars_set)


def gen_constraint_validation(gen_constraints, substitution):
    gen_search_space = z3.And(*gen_constraints)
    test_eval = z3.simplify(z3.substitute(gen_search_space, *substitution))
    if z3.is_true(test_eval):
        print(f"Current r is NOT excluded from generalized search space.")
        exit()
    else:
        print(f"Current r is excluded from generalized search space.")


def clean_name(name):
    if not name:
        return "unknown"
    if name[0].isdigit():
        return "v_" + name.replace(":", "_").replace(".", "_").replace("/", "_")
    return name.replace(":", "_").replace(".", "_").replace("/", "_")


if __name__ == "__main__":
    # test cases
    path = "main/networks/concrete/flow.onnx"
    output_keys, output_formulas = onnx2z3(path)
    for key in output_keys:
        print(f"Output key: {key}")
        output_formula = output_formulas[key]["vars"]
        print(f"Output formulas vars: {output_formula}")
        expr = output_formulas[key]["expr"]