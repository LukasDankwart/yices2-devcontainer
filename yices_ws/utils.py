import subprocess
import re
import numpy as np
import onnxruntime as ort
import onnx
from z3 import *


def run_yices_on_smt(smt_path):
    try:
        results = subprocess.run(
            ['yices-smt2', smt_path],
            text=True,
            capture_output=True
        )
        return results
    except FileNotFoundError:
        print(f"{smt_path} not found or not valid.")

def run_z3_on_smt(smt_path, target_vars=None):
    s = Solver()
    s.from_file(smt_path)

    result = s.check()
    print(f"Status: {result}")

    if result != sat:
        return {"status": "unsat"}

    m = s.model()
    extracted_values = {"status": "sat"}

    for d in m.decls():
        name = d.name()

        if name in target_vars:
            val = m[d]

            if is_rational_value(val):
                num = val.numerator_as_long()
                den = val.denominator_as_long()
                extracted_values[name] = num / den
            elif is_int_value(val):
                extracted_values[name] = val.as_long()
            else:
                extracted_values[name] = str(val)

    return extracted_values

def parse_yices_results(results, input_vars, output_vars):
    if results.returncode != 0:
        print(f"Error while running Yices: \n{results.stderr}")
        return None
    output = results.stdout.strip()
    if output.startswith("unsat"):
        print(f"Formula is UNSAT.")
        return {"status": "unsat", "model": None}
    elif output.startswith("sat"):
        print(f"Formula is SAT.")
        target_vars = set(input_vars + output_vars)
        model_data = {}
        pattern = re.compile(r"\(define-fun\s+(?P<name>\S+)\s+\(\)\s+\S+\s+(?P<val>.+?)\)$", re.MULTILINE)
        for match in pattern.finditer(output):
            name = match.group("name")
            raw_val = match.group("val")

            # The assignment for each target var is parsed into the model data
            if name in target_vars:
                parsed_val = parse_smt_value(raw_val)
                model_data[name] = parsed_val

        return {"status": "sat", "model": model_data}
    else:
        print(f"Unknown Yices output: \n{output}")
        return {"status": "unknown", "model": None}


def compare_yices_to_onnx(yices_results, input_vars, output_vars, onnx_input, onnx_output, atol=1e-3, rtol=1e-3):
    if yices_results["status"] == "sat":
        input_assignment = []
        output_assignment = []
        for var in input_vars:
            input_assignment.append(yices_results.get("model").get(var))
        for var in output_vars:
            output_assignment.append(yices_results.get("model").get(var))

        input_assignment = np.array(input_assignment)
        output_assignment = np.array(output_assignment)

        equal_inputs = np.allclose(input_assignment, onnx_input, atol=atol, rtol=rtol)
        equal_outputs = np.allclose(output_assignment, onnx_output, atol=atol, rtol=rtol)

        print(f"YICES INPUT: {input_assignment}")
        print(f"ONNX INPUT: {onnx_input} \n")
        print(f"YICES OUTPUT: {output_assignment}")
        print(f"ONNX OUTPUT: {onnx_output} \n")
        if equal_inputs and equal_outputs:
            print(f"Same assignment for Input and Output variables.")
            return True
        elif equal_inputs:
            print(f"Same assignment for Input; but deviation for Output values.")
            return False
        elif equal_outputs:
            print(f"Same assignment for Output; but deviation for Input values.")
            return False
        else:
            print(f"Neither Input or Output values are equal between Yices model and ONNX runtime.")
            return False
    else:
        print(f"Yices status: {yices_results['status']} \n")
        print(f"No comparison to ONNX runtime is performed.")

def parse_smt_value(value_str):
    """
      "true" -> True
      "42" -> 42.0
      "(- 42)" -> -42.0
      "(/ 1 2)" -> 0.5
      "(/ (- 1) 2)" -> -0.5
    """
    clean_str = value_str.replace("(", " ").replace(")", " ").strip()

    # 2. In Tokens zerlegen (trennt an beliebigen Leerzeichen)
    tokens = clean_str.split()

    if not tokens:
        return None

    if tokens[0] == "/":
        def get_next_number(token_list, start_index):
            if token_list[start_index] == "-":
                return -float(token_list[start_index + 1]), start_index + 2
            else:
                return float(token_list[start_index]), start_index + 1

        numerator, idx = get_next_number(tokens, 1)
        denominator, _ = get_next_number(tokens, idx)

        return numerator / denominator

    elif tokens[0] == "-":
        return -float(tokens[1])

    # Fall 3: Boolesche Werte
    elif tokens[0] == "true":
        return True
    elif tokens[0] == "false":
        return False

    else:
        return float(tokens[0])

def clean_name(name):
    if not name:
        return "unknown"
    if name[0].isdigit():
        return "v_" + name.replace(":", "_").replace(".", "_").replace("/", "_")
    return name.replace(":", "_").replace(".", "_").replace("/", "_")

def format_smt_number(val):
    if val < 0:
        return f"(- {abs(val):.6f})"
    return f"{val:.6f}"

def get_input_dims(node):
    dims = []
    if node.type.tensor_type.HasField("shape"):
        for d in node.type.tensor_type.shape.dim:
            if d.HasField("dim_value"):
                dims.append(d.dim_value)
            else:
                dims.append(1)
    return dims

def perform_onnx_runtime(onnx_file_path):
    model = onnx.load(onnx_file_path)
    graph = model.graph
    input_shape = get_input_dims(graph.input[0])
    dummy_input = np.random.randn(*input_shape).astype(np.float32)

    ort_session = ort.InferenceSession(onnx_file_path)
    onnx_output = ort_session.run(None, {'onnx::MatMul_0': dummy_input})

    return dummy_input, onnx_output[0]

def add_distance_condition(path, distance, iteration):
    new_path = path.removesuffix(".smt2") + f"_{iteration}.smt2"
    try:
        with open(path, 'r') as src, open(new_path, 'w') as dst:
            dist_added = False
            for line in src:
                dst.write(line)

                if "; --- Define distance condition" in line:
                    dst.write(f"(assert (<= total_distance {distance})) \n")
                    dist_added = True
            if not dist_added:
                ValueError(f"Given SMT file does not contain area for distance expression.")
            return new_path
    except FileNotFoundError:
        raise RuntimeError(f"File at '{new_path}' not found.")




