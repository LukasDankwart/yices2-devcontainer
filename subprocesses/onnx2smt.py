import onnx
from onnx import numpy_helper, shape_inference
from utils import run_yices_on_smt, clean_name, format_smt_number


def get_input_dims(node):
    dims = []
    print(node)
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

def main():
    input_path = "subprocesses/networks/concrete/classifier_medium.onnx"
    output_path = "subprocesses/formulas/classifier_medium.smt2"
    input_vars, output_vars = onnx_to_smt2(input_path, output_path)
    # Define Dummy input and output bounds
    input_bounds = {}
    for input_var in input_vars:
        input_bounds[input_var] = {"lb": 0.0, "ub": 1.0}

    # Output bounds
    output_bounds = {}
    for output_var in output_vars:
        output_bounds[output_var] = {"lb": 1.0, "ub": 1.0}

    add_bounds_to_smt(output_path, input_vars, output_vars, input_bounds=input_bounds, output_bounds=output_bounds)

if __name__ == "__main__":
    # TODO: VALIDIERUNGSSKRIPT das ONNXRUNTIME EINGABE/AUSGABE auf dem Netz mit dem von YICES AUF SMT ENCODING vergleicht
    main()