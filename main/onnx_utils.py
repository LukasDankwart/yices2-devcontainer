import onnx
import onnxruntime as ort
import numpy as np
import pandas as pd
import os


def generate_csv_examples(onnx_path, iterations=1):
    concretes = []
    for it in range(iterations):
        concrete = generate_concrete_input(onnx_path)
        concretes.append(concrete)

    data_points = []
    for concrete in concretes:
        conc_input = concrete["concrete_input"].flatten()
        vals = list(conc_input)
        conc_class_prediction = concrete["class_prediction"]
        data_points.append([*vals, conc_class_prediction])

    columns = [f"inp_{i}" for i in range(len(data_points[0]) - 1)] + ["class"]
    df= pd.DataFrame(data_points, columns=columns)
    csv_path = os.path.join(onnx_path.removesuffix(".onnx"), "_examples.csv")
    csv_path = onnx_path.removesuffix(".onnx") + "_examples.csv"
    df.to_csv(csv_path, index=False)


def generate_concrete_input(onnx_path):
    concrete_input, concrete_output = perform_onnx_runtime(onnx_path)
    concrete = {
        "concrete_input": concrete_input,
        "class_prediction": np.argmax(concrete_output)
    }
    return concrete


def perform_onnx_runtime(onnx_path):
    model = onnx.load(onnx_path)
    graph = model.graph
    input_shape = get_input_dims(graph.input[0])
    dummy_input = np.random.randn(*input_shape).astype(np.float32)

    ort_session = ort.InferenceSession(onnx_path)
    onnx_output = ort_session.run(None, {'onnx::MatMul_0': dummy_input})

    return dummy_input, onnx_output[0]


def get_input_dims(node):
    dims = []
    if node.type.tensor_type.HasField("shape"):
        for d in node.type.tensor_type.shape.dim:
            if d.HasField("dim_value"):
                dims.append(d.dim_value)
            else:
                dims.append(1)
    return dims


if __name__ == "__main__":
    path = "main/networks/concrete/flow.onnx"
    generate_csv_examples(path, iterations=1)