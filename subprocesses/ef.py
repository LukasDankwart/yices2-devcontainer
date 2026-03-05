import numpy as np
import onnxruntime as ort
import utils
from subprocesses.utils import run_yices_on_smt, parse_yices_results

if __name__ == "__main__":
    smt_path = "subprocesses/ef/classifier_medium_ef_minimized.smt2"

    results = run_yices_on_smt(smt_path)
    res_vars = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]
    results = parse_yices_results(results, res_vars, [])

    # Das ist der original input, anhand welcher ef/classifier_medium_ef.smt2 manuell formuliert wurde
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

    residuals = []
    for res_var in res_vars:
        residuals.append(results["model"].get(res_var))
        print(results["model"].get(res_var))
    residuals.append(x_input[-1])

    x_input = np.array(x_input).astype(np.float32) + np.array(residuals).astype(np.float32)
    print(x_input)

    ort_session = ort.InferenceSession("subprocesses/networks/concrete/classifier_medium.onnx")
    y_values = [x / 10 for x in range(-10, 11)]
    for y in y_values:
        x_input[-1] = y
        onnx_output = ort_session.run(None, {'onnx::MatMul_0': x_input})
        print(f"ONNX Output for CX: {np.argmax(onnx_output[0])}")

    # TODO: Exists (not Exists) For All kann nicht ausgeführt werden
    # TODO: liese sich dann nur noch mit CEGIS (Counterexample-Guided Inductive Synthesis) oder
    # TODO: CEGAR (Counterexample-Guided Abstraction Refinement)


