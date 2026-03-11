import numpy as np
import onnxruntime as ort
from yices_ws.utils import compare_yices_to_onnx, run_yices_on_smt, parse_yices_results

# Try to ensure semantic equivalence of onnx2smt parser and z3convert-parser,
# since performance and results on binary search are very different

def main():
    inp_vars = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
    out_vars = ["o0", "o1"]
    path = "z3_examples/z3_inference.smt2"
    results = run_yices_on_smt(path)
    results = parse_yices_results(results, inp_vars, out_vars)

    onnx_input = np.array([
        -0.021025,
        -1.043187,
        0.300265,
        0.570702,
        -1.124416,
        -1.794718,
        0.569139,
        -0.361468
    ]).astype(np.float32)
    ort_session = ort.InferenceSession("yices_ws/networks/concrete/classifier_medium.onnx")
    onnx_output = ort_session.run(None, {'onnx::MatMul_0': onnx_input})

    compare_yices_to_onnx(results, inp_vars, out_vars, onnx_input, onnx_output[0])

if __name__ == "__main__":
    main()