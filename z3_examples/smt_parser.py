import onnx
from onnx import numpy_helper
from z3 import *
import numpy as np
from yices_ws.utils import clean_name

def onnx2smt(onnx_path, smt_path):
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
        else:
            raise ValueError(f"Current node-optype is not supported!")

        intermediate_tensors[clean_name(node.output[0])] = out

    print(f"Building z3 instance was successful ")
    # 4. Generate SMT Lib file
    print(f"Start generating SMT-Lib file")
    with open(smt_path, "w") as f:
        out_names = [clean_name(out.name) for out in graph.output]
        f.write("(set-logic LRA)\n \n")

        # Build a input string holding all input vars (z3 real inputs of the network)
        input_args_str = " ".join([f"({var.sexpr()} Real)" for var in input_vars])

        for out_idx, out_name in enumerate(out_names):
            final_tensor = intermediate_tensors[out_name].flatten()

            for i, neuron_expr in enumerate(final_tensor):
                simplified_expr = z3.simplify(neuron_expr)
                math_string = simplified_expr.sexpr()
                func_name = f"OutputNeuron_{out_idx}_idx{i}"
                f.write(f"(define-fun {func_name} ({input_args_str}) Real\n")
                f.write(f"  {math_string}\n")
                f.write(f")\n\n")

    print(f"SMT file stored at {smt_path}")

def main():
    onnx2smt("yices_ws/networks/concrete/classifier_medium.onnx", "z3_examples/z3.smt2")


if __name__ == "__main__":
    main()