import numpy as np

from yices_ws.utils import run_yices_on_smt, parse_yices_results, compare_yices_to_onnx, run_z3_on_smt, add_distance_condition
from yices_ws.binary_search import binary_search
import os
import onnxruntime as ort


import time

def yices_on_z3_parsed_smt():
    path = "z3_examples/z3_binarysearch/z3_ef.smt2"
    if os.path.isfile(path):
        print("FILE EXISTS")
    results = run_yices_on_smt(path)
    results = parse_yices_results(results, ["r0", "r1", "r2", "r3", "r4", "r5", "r6"], [])

    bs_start = time.perf_counter()
    minimal_r = binary_search(path, initial_ub=100.0)
    bs_end = time.perf_counter()

    print(f"Binary search time on 'Z3-Parser' Variant: {(bs_end - bs_start):.5f}")

    print("Binary search finished! CX with minimal distance: \n")
    print(minimal_r)
    print(f"Distance: {np.sum(np.abs(np.array(minimal_r)))} \n")

    minimal_r = np.append(minimal_r, 0.0)
    minimal_r = np.array(minimal_r, dtype=np.float32)
    x_input = [
        -0.021025,
        -1.043187,
        0.300265,
        0.570702,
        -1.124416,
        -1.794718,
        0.569139,
        -0.361468
    ]
    x_input = np.array(x_input, dtype=np.float32)
    ort_session = ort.InferenceSession("yices_ws/networks/concrete/classifier_medium.onnx")
    onnx_output = ort_session.run(None, {'onnx::MatMul_0': x_input})
    onnx_class_pred = np.argmax(onnx_output[0])
    print(f"ONNX run on original input 'x' is classified: {onnx_class_pred} \n")
    print(f"Sampling different missing inputs between '[-1.0, 1.0]'")
    y_values = [x / 10 for x in range(-10, 11)]
    for idx in range(len(y_values)):
        y = y_values[idx]
        x_input[-1] = y
        cx = x_input + minimal_r
        onnx_output = ort_session.run(None, {'onnx::MatMul_0': cx})
        print(f"CX with y '{y}' is classified as: {np.argmax(onnx_output[0])}")
        print(f"{onnx_output[0]} \n")

def z3_binary_search_on_smt():

    target_vars = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]
    path = "z3_examples/z3_binarysearch/z3_ef.smt2"
    if os.path.isfile(path):
        print("FILE EXISTS")
    results = run_z3_on_smt(path, target_vars)
    #results = parse_yices_results(results, ["r0", "r1", "r2", "r3", "r4", "r5", "r6"], [])

    bs_start = time.perf_counter()
    minimal_r = binary_search_z3(path, initial_ub=100.0)
    bs_end = time.perf_counter()

    print(f"Binary search time on 'Z3-Parser' Variant: {(bs_end - bs_start):.5f}")

    print("Binary search finished! CX with minimal distance: \n")
    print(minimal_r)
    print(f"Distance: {np.sum(np.abs(np.array(minimal_r)))} \n")

    minimal_r = np.append(minimal_r, 0.0)
    minimal_r = np.array(minimal_r, dtype=np.float32)
    x_input = [
        -0.021025,
        -1.043187,
        0.300265,
        0.570702,
        -1.124416,
        -1.794718,
        0.569139,
        -0.361468
    ]
    x_input = np.array(x_input, dtype=np.float32)
    ort_session = ort.InferenceSession("yices_ws/networks/concrete/classifier_medium.onnx")
    onnx_output = ort_session.run(None, {'onnx::MatMul_0': x_input})
    onnx_class_pred = np.argmax(onnx_output[0])
    print(f"ONNX run on original input 'x' is classified: {onnx_class_pred} \n")
    print(f"Sampling different missing inputs between '[-1.0, 1.0]'")
    y_values = [x / 10 for x in range(-10, 11)]
    for idx in range(len(y_values)):
        y = y_values[idx]
        x_input[-1] = y
        cx = x_input + minimal_r
        onnx_output = ort_session.run(None, {'onnx::MatMul_0': cx})
        print(f"CX with y '{y}' is classified as: {np.argmax(onnx_output[0])}")
        print(f"{onnx_output[0]} \n")


def binary_search_z3(path, initial_ub=100.0):
    target_vars = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]

    lb = 0.0
    ub = initial_ub

    minimal_res = None
    iter = 0
    while (ub - lb) > 0.001:
    #for iter in range(10):
        mb = (ub + lb) / 2.0
        run_path = add_distance_condition(path, mb, iter)
        results = run_z3_on_smt(run_path, target_vars=target_vars)
        #results = parse_yices_results(results, input_vars=target_vars, output_vars=[])
        iter += 1
        if results["status"] == "sat":
            # Fetch assignment and compute distance
            new_res = [results.get(target) for target in target_vars]
            new_distance = np.sum(np.abs(np.array(new_res)))
            # Store new assignment and set upper bound to found minimal distance
            ub = min(mb, new_distance)
            minimal_res = new_res
        elif results["status"] == "unsat":
            # No new better cx was found, just lift up the lower bound to the mid value
            lb = mb

    return minimal_res

if __name__ == "__main__":
    z3_binary_search_on_smt()