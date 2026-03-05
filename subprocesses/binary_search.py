from utils import *
import numpy as np
import onnxruntime as ort

def binary_search(path, initial_ub=100.0):
    target_vars = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]

    lb = 0.0
    ub = initial_ub

    minimal_res = None
    iter = 0
    while (ub - lb) > 0.001:
    #for iter in range(10):
        mb = (ub + lb) / 2.0

        run_path = add_distance_condition(path, mb, iter)

        results = run_yices_on_smt(run_path)
        results = parse_yices_results(results, input_vars=target_vars, output_vars=[])
        iter += 1
        if results is None:
            raise RuntimeError(f"Failed to interpret YICES results")
        if results["status"] == "unknown":
            print(f"Unknown Yices output: \n{results}")
            print(f"Last valid cx was: {minimal_res}")
        elif results["status"] == "sat":
            # Fetch assignment and compute distance
            new_res = [results["model"].get(target) for target in target_vars]
            new_distance = sum(abs(np.array(new_res)))
            # Store new assignment and set upper bound to found minimal distance
            ub = new_distance
            minimal_res = new_res
        elif results["status"] == "unsat":
            # No new better cx was found, just lift up the lower bound to the mid value
            lb = mb

    return minimal_res

def main():
    path = "subprocesses/binary_search/classifier_medium_binarysearch.smt2"
    minimal_r = binary_search(path, initial_ub=100.0)
    print("Binary search finished! CX with minimal distance: \n")
    print(minimal_r)
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
    ort_session = ort.InferenceSession("subprocesses/networks/concrete/classifier_medium.onnx")
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


if __name__ == '__main__':
    main()
