import sys
from importlib.metadata import version, PackageNotFoundError
from maraboupy import Marabou

if __name__ == "__main__":
    print(f"Python Version: {sys.version}")
    marabou_version = version("maraboupy")
    print(f"maraboupy ist installiert! Version: {marabou_version}")
    print("marabou erfolgreich geladen!")


    network = Marabou.read_onnx("subprocesses/networks/concrete/classifier_medium.onnx")
    network.getInputQuery().saveQueryAsSmtLib("test_output.smt2")
    print(f"worked")
