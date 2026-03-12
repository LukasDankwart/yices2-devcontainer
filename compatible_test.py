from yices_ws.utils import *
from yices_ws.binary_search import binary_search
from z3_examples.smt_parser import onnx2smt
import os
import onnx
import onnxruntime as ort

NetworkPaths = {
    1 : "yices_ws/networks/concrete",
    2 : "yices_ws/networks/diabetes",
    3 : "yices_ws/networks/power",
    4 : "yices_ws/networks/wine"
}

def parse_networks_to_smt():
    try:
        # Parse SMT representation that encodes each network computation
        for network_path in NetworkPaths.values():
            onnx_path = os.path.join(network_path, "classifier_medium.onnx")
            smt_dest_path = os.path.join(network_path, "smt", "classifier_medium.smt2")
            # Call parser for each network and store at destination smt path
            onnx2smt(onnx_path, smt_dest_path)
    except Exception as e:
        print(f"Networks couldn't be parsed \n")
        print(e)

def compute_onnx_inference(path):
    try:
        ort_input, ort_output = perform_onnx_runtime(path)
        return ort_input, ort_output
    except FileNotFoundError:
        print(f"Given path {path} doesn't exist")
    except Exception:
        print(f"Error occured while running ORT on {path}")


def main():
    # Parse SMT representation that encodes each network computation
    parse_networks_to_smt()
    network_type = "classifier_medium.onnx"

    # Compute Onnx outputs for each network and compare with encoding
    ort_runs = {}
    for path in NetworkPaths.values():
        onnx_path = os.path.join(path, network_type)
        ort_input, ort_output = compute_onnx_inference(onnx_path)
        ort_runs[path] = {"input": ort_input, "output": ort_output}

    # Ensure equivalence of encoding
    # TODO: Not finished



if __name__ == "__main__":
    main()