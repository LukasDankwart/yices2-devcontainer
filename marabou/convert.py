import os
import subprocess


if __name__ == "__main__":
    onnx_path = "yices_ws/networks/concrete/classifier_medium.onnx"
    smt_path = "test_output.smt2"

    print(f"Start converting....")

    try:
        result = subprocess.run(
            ["onnx2smt", onnx_path, smt_path],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"C++ tool didn't work.")
        print(f"Error code: {e.returncode}")
    except FileNotFoundError as e:
        print(f"Command 'onnx2smt' not found.")
        print(f"Error code: {e}")
