import numpy as np
import onnx
from onnx import numpy_helper, shape_inference
from utils import *


def get_input_dims(node):
    dims = []
    if node.type.tensor_type.HasField("shape"):
        for d in node.type.tensor_type.shape.dim:
            if d.HasField("dim_value"):
                dims.append(d.dim_value)
            else:
                dims.append(1)
    return dims

def get_output_dims(node, graph):
    out_name = node.output[0]

    for info in graph.value_info:
        if info.name == out_name:
            dims = []
            for d in info.type.tensor_type.shape.dim:
                if d.HasField("dim_value"):
                    dims.append(d.dim_value)
                else:
                    dims.append(1)
            return dims

    for out in graph.output:
        if out.name == out_name:
            dims = []
            for d in out.type.tensor_type.shape.dim:
                if d.HasField("dim_value"):
                    dims.append(d.dim_value)
                else:
                    dims.append(1)
            return dims
    return None

def compute_tensor_shapes(graph):
    tensors = {}
    for inp in graph.input:
        input_dims = get_input_dims(inp)
        tensors.update({clean_name(inp.name): {"input_dims": input_dims, "output_dims": input_dims}})
    for val in graph.value_info:
        input_dims = get_input_dims(val)
        output_dims = get_output_dims(val, graph)
        tensors.update({clean_name(val.name): {"input_dims": input_dims, "output_dims": input_dims}})
    for out in graph.output:
        input_dims = get_input_dims(out)
        output_dims = get_output_dims(out, graph)
        tensors.update({clean_name(out.name): {"input_dims": input_dims, "output_dims": output_dims}})
    return tensors


def get_dims(tensor_proto):
    """Hilfsfunktion: Extrahiert Dimensionen aus einem Tensor/ValueInfo Proto."""
    if not tensor_proto.type.tensor_type.HasField("shape"):
        return []  # Skalar oder unbekannt

    dims = []
    for d in tensor_proto.type.tensor_type.shape.dim:
        if d.HasField("dim_value"):
            dims.append(d.dim_value)
        elif d.HasField("dim_param"):
            # Platzhalter für variable Dimension (z.B. 'batch') -> wir setzen 1
            dims.append(1)
        else:
            dims.append(1)
    return dims


def compute_node_shapes(model):
    graph = model.graph

    # Fetch the shape for every tensor
    shape_map = {}
    for i in graph.input:
        shape_map[i.name] = get_dims(i)
    for o in graph.output:
        shape_map[o.name] = get_dims(o)
    for v in graph.value_info:
        shape_map[v.name] = get_dims(v)
    for init in graph.initializer:
        dims = list(init.dims)
        shape_map[init.name] = dims

    # Dictionary will store {"nodeName": {"optype": ..., "input_shapes": ..., "output_shapes": ...}
    node_data = {}

    for node in graph.node:
        key_name = node.name if node.name else node.output[0]

        input_shapes = []
        for input_name in node.input:
            shape = shape_map.get(input_name, [])
            input_shapes.append(shape)
        output_shapes = []
        for output_name in node.output:
            shape = shape_map.get(output_name, [])
            output_shapes.append(shape)
        node_data[clean_name(key_name)] = {
            "op_type": node.op_type,
            "input_shapes": input_shapes,
            "output_shapes": output_shapes
        }

    return node_data

def get_network_input_shapes(graph):
    initializer_names = set(init.name for init in graph.initializer)
    input_shapes = {}
    for inp in graph.input:
        name = clean_name(inp.name)
        if name in initializer_names:
            continue
        dims = []
        tensor_type = inp.type.tensor_type
        if tensor_type.HasField("shape"):
            for d in tensor_type.shape.dim:
                if d.HasField("dim_value"):
                    dims.append(d.dim_value)
                elif d.HasField("dim_param"):
                    dims.append(1)
                else:
                    dims.append(1)
        input_shapes[name] = dims
    return input_shapes

def get_operand(name, index, initializers):
    clean_n = clean_name(name)
    if name in initializers:
        arr = initializers[name]
        if arr.ndim == 1:
            val = arr[index] if index < len(arr) else arr[0]
        elif arr.ndim == 0:
            val = arr.item()
        else:
            val = arr.flatten()[index]
        return format_smt_number(val)
    return f"{clean_n}_{index}"

def onnx_to_smt2(onnx_path, smt2_path, logic="LRA"):
    model = onnx.load(onnx_path)
    model = shape_inference.infer_shapes(model)  # Perform shape inference for parsing
    graph = model.graph

    # Graph data
    network_input_shapes = get_network_input_shapes(graph)
    node_data = compute_node_shapes(model)
    with open(smt2_path, 'w') as f:
        f.write(f"(set-logic {logic})\n")

        initializers = {}
        for init in graph.initializer:
            initializers[clean_name(init.name)] = numpy_helper.to_array(init)

        previous_vars = []
        for node in graph.input:
            f.write("; --- Defining input variables ---\n")
            name = clean_name(node.name)
            dim = network_input_shapes.get(name, [1])[0]
            for i in range(dim):
                f.write(f"(declare-fun {name}_{i} () Real) \n")
                previous_vars.append(f"{name}_{i}")
        graph_input_var_names = previous_vars
        f.write("; --- INPUT BOUNDS --- \n")

        # Network computation
        f.write("; --- Translating networks computation --- \n")
        for node in graph.node:
            op_type = node.op_type
            inputs = [clean_name(i) for i in node.input]
            outputs = [clean_name(o) for o in node.output]
            out_name = outputs[0]
            f.write(f"; --- Node: {node.name} (Op-Type: {op_type}) ---\n")
            input_shape = node_data.get(clean_name(node.name), None)["input_shapes"][0][0]
            output_shape = node_data.get(clean_name(node.name), None)["output_shapes"][0][0]
            #assert len(previous_vars) == input_shape, "Intermediate amount of variables does not match input shapes."

            tmp_intermediates = []
            # --- Add parsing ---
            if op_type.lower() == "add":
                #assert input_shape == output_shape, "AddOperator should have same input and output shapes."
                for i in range(output_shape):
                    val_a = get_operand(inputs[0], i, initializers)
                    val_b = get_operand(inputs[1], i, initializers)
                    f.write(f"(declare-fun {out_name}_{i} () Real)\n")
                    f.write(f"(assert (= {out_name}_{i} (+ {val_a} {val_b})))\n")
                    tmp_intermediates.append(f"{out_name}_{i}")
                previous_vars = tmp_intermediates

            # --- MatMul parsing ---
            elif op_type.lower() == "matmul":
                if inputs[1] in initializers:
                    W = initializers[inputs[1]]
                else:
                    f.write(f"; SKIP Gemm: Gewichte für {inputs[1]} nicht gefunden\n")
                    continue

                B = None
                if len(inputs) > 2 and inputs[2] in initializers:
                    B = initializers[inputs[2]]

                rows, cols = W.shape

                for j in range(cols):
                    f.write(f"(declare-fun {out_name}_{j} () Real)\n")
                    terms = []
                    for i in range(rows):
                        w_str = format_smt_number(W[i][j])
                        in_var = f"{inputs[0]}_{i}"
                        terms.append(f"(* {w_str} {in_var})")

                    sum_expr = " ".join(terms)
                    bias_val = 0.0
                    if B is not None:
                        bias_val = B[j] if j < len(B) else 0.0
                    b_str = format_smt_number(bias_val)

                    if terms:
                        f.write(f"(assert (= {out_name}_{j} (+ (+ {sum_expr}) {b_str})))\n")
                        tmp_intermediates.append(f"{out_name}_{j}")
                    else:
                        f.write(f"(assert (= {out_name}_{j} {b_str}))\n")
                        tmp_intermediates.append(f"{out_name}_{j}")

                previous_vars = tmp_intermediates

            # --- ReLU parsing ---
            elif op_type.lower() == "relu":
                in_name = inputs[0]
                for i in range(output_shape):
                    f.write(f"(declare-fun {out_name}_{i} () Real)\n")
                    f.write(f"(assert (= {out_name}_{i} (ite (> {in_name}_{i} 0.0) {in_name}_{i} 0.0)))\n")
                    tmp_intermediates.append(f"{out_name}_{i}")
                previous_vars = tmp_intermediates
            else:
                raise ValueError(f"Given op_type '{op_type}' is not supported.")

        f.write("; --- OUTPUT BOUNDS --- \n")
        # Call for sat-check and model
        f.write(f"; --- ENCODING is done --- \n")
        f.write("(check-sat)\n")
        f.write("(get-model)\n")

        print(f"Exported to {smt2_path}")

        return graph_input_var_names, previous_vars


def add_bounds_to_smt(smt_path, input_vars, output_vars, input_bounds=None, output_bounds=None):
    new_path = smt_path.removesuffix(".smt2") + "_bounded.smt2"
    try:
        with open(smt_path, 'r') as src, open(new_path, 'w') as dst:
            for line in src:
                dst.write(line)
                # Space for input bounds found
                if "; --- INPUT BOUNDS --- " in line:
                    # If input bounds are given, they are mapped to each input var name
                    if input_bounds is not None:
                        assert len(input_vars) == len(
                            input_bounds), "Given input bounds do not match to given input vars."
                        for var_name in input_vars:
                            bounds = input_bounds.get(var_name, None)
                            if bounds is None:
                                raise ValueError(f"Input var {var_name} does not have bounds.")
                            lb = format_smt_number(bounds["lb"])
                            ub = format_smt_number(bounds["ub"])
                            dst.write(f"(assert (>= {var_name} {lb}))\n")
                            dst.write(f"(assert (>= {var_name} {ub}))\n")
                # Space four output bounds found
                elif "; --- OUTPUT BOUNDS --- " in line:
                    # If output bounds are given, they are mapped to each output var name
                    if output_bounds is not None:
                        assert len(output_vars) == len(
                            output_bounds), "Given output bounds do not match to given output vars."
                        for var_name in output_vars:
                            bounds = output_bounds.get(var_name, None)
                            if bounds is None:
                                raise ValueError(f"Output var {var_name} does not have bounds.")
                            lb = format_smt_number(bounds["lb"])
                            ub = format_smt_number(bounds["ub"])
                            dst.write(f"(assert (>= {var_name} {lb}))\n")
                            dst.write(f"(assert (>= {var_name} {ub}))\n")
            print(f"Bounds successfully added and exported to {new_path}")
            return True
    except FileNotFoundError:
        print(f"File {smt_path} not found.")
        return False

def onnx_to_smt_function(onnx_path, smt2_path):
    model = onnx.load(onnx_path)
    model = shape_inference.infer_shapes(model)
    graph = model.graph

    # Graph data
    network_input_shapes = get_network_input_shapes(graph)
    node_data = compute_node_shapes(model)

    function_params = []
    input_var_names = []

    for node in graph.input:
        name = clean_name(node.name)
        dim = network_input_shapes.get(name, [1])[0]
        for i in range(dim):
            var_name = f"{name}_{i}"
            input_var_names.append(var_name)
            function_params.append(f"({var_name} Real)")

    initializers = {}
    for init in graph.initializer:
        initializers[clean_name(init.name)] = numpy_helper.to_array(init)

    computation_steps = []

    previous_vars = input_var_names[:]

    for node in graph.node:
        op_type = node.op_type
        inputs = [clean_name(i) for i in node.input]
        outputs = [clean_name(o) for o in node.output]
        out_name = outputs[0]

        input_shape = node_data.get(clean_name(node.name), None)["input_shapes"][0][0]
        output_shape = node_data.get(clean_name(node.name), None)["output_shapes"][0][0]

        tmp_intermediates = []

        # --- Add parsing ---
        if op_type.lower() == "add":
            for i in range(output_shape):
                val_a = get_operand(inputs[0], i, initializers)
                val_b = get_operand(inputs[1], i, initializers)

                var_id = f"{out_name}_{i}"
                expr = f"(+ {val_a} {val_b})"
                computation_steps.append((var_id, expr))
                tmp_intermediates.append(var_id)
            previous_vars = tmp_intermediates

        # --- MatMul parsing ---
        elif op_type.lower() == "matmul":
            if inputs[1] in initializers:
                W = initializers[inputs[1]]
            else:
                print(f"SKIP Gemm: Gewichte für {inputs[1]} nicht gefunden")
                continue

            B = None
            if len(inputs) > 2 and inputs[2] in initializers:
                B = initializers[inputs[2]]

            rows, cols = W.shape

            for j in range(cols):
                var_id = f"{out_name}_{j}"
                terms = []
                for i in range(rows):
                    w_str = format_smt_number(W[i][j])
                    in_var = f"{inputs[0]}_{i}"
                    terms.append(f"(* {w_str} {in_var})")

                sum_expr = " ".join(terms) if terms else "0.0"

                bias_val = 0.0
                if B is not None:
                    bias_val = B[j] if j < len(B) else 0.0
                b_str = format_smt_number(bias_val)

                if terms:
                    expr = f"(+ (+ {sum_expr}) {b_str})"
                else:
                    expr = b_str

                computation_steps.append((var_id, expr))
                tmp_intermediates.append(var_id)

            previous_vars = tmp_intermediates

        # --- ReLU parsing ---
        elif op_type.lower() == "relu":
            in_name = inputs[0]
            for i in range(output_shape):
                var_id = f"{out_name}_{i}"
                # Referenz auf vorherigen Wert
                prev_val = f"{in_name}_{i}"
                expr = f"(ite (> {prev_val} 0.0) {prev_val} 0.0)"

                computation_steps.append((var_id, expr))
                tmp_intermediates.append(var_id)
            previous_vars = tmp_intermediates

        else:
            print(f"Warning: OpType {op_type} not supported/implemented yet.")

    with open(smt2_path, 'w') as f:
        f.write("(set-logic LRA)\n")


        final_layer_vars = previous_vars

        for out_idx, out_var_name in enumerate(final_layer_vars):
            func_name = f"run_network_out_{out_idx}"
            params_str = " ".join(function_params)

            f.write(f"; --- Function for Output {out_idx} ---\n")
            f.write(f"(define-fun {func_name} ({params_str}) Real\n")


            indent = "  "
            for var_name, expr in computation_steps:
                f.write(f"{indent}(let (({var_name} {expr}))\n")
                indent += " "

            f.write(f"{indent}{out_var_name}\n")

            for _ in computation_steps:
                f.write(")")
            f.write(")\n")
            f.write("\n")

        f.write("; --- Network Functions Defined ---\n")
        f.write("; Jetzt kannst du manuell deine ExistsForAll Constraints hinzufügen.\n")
        f.write("; Beispiel: (assert (forall ((y Real)) ... (run_network_out_0 ... y ...)))\n")


def main():
    input_path = "subprocesses/networks/concrete/classifier_medium.onnx"
    output_path = "subprocesses/formulas/classifier_medium.smt2"

    onnx_to_smt_function(input_path, "subprocesses/ef/classifier_medium_function.smt2")

    """
    input_vars, output_vars = onnx_to_smt2(input_path, output_path)

    onnx_input, onnx_output = perform_onnx_runtime(input_path)

    # Define Dummy input and output bounds
    input_bounds = {}
    for idx in range(len(input_vars)):
        input_bounds[input_vars[idx]] = {"lb": onnx_input[idx], "ub": onnx_input[idx]}

    # Output bounds
    #output_bounds = {}
    #for idx in range(len(output_vars)):
    #   output_bounds[output_vars[idx]] = {"lb": onnx_output[idx], "ub": onnx_output[idx]}

    add_bounds_to_smt(output_path, input_vars, output_vars, input_bounds=input_bounds, output_bounds=None)

    results = run_yices_on_smt("subprocesses/formulas/classifier_medium_bounded.smt2")
    results = parse_yices_results(results, input_vars, output_vars)
    equal = compare_yices_to_onnx(results, input_vars, output_vars, onnx_input, onnx_output)

    if results["status"] == "sat":
        input_assignment = []
        output_assignment = []
        for var in input_vars:
            input_assignment.append(results.get("model").get(var))
        for var in output_vars:
            output_assignment.append(results.get("model").get(var))

        input_assignment = np.array(input_assignment)
        output_assignment = np.array(output_assignment)

        print(f"YICES INPUT: {input_assignment}")
        print(f"ONNX INPUT: {onnx_input} \n")
        print(f"YICES OUTPUT: {output_assignment}")
        print(f"ONNX OUTPUT: {onnx_output} \n")
    """

if __name__ == "__main__":
    main()