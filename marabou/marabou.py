import sys
import os

sys.path.append("/opt/Marabou")

from maraboupy import Marabou

if __name__ == "__main__":


    if os.path.exists("/opt/Marabou"):
        print("Marabou Verzeichnis existiert")
    print(f"Python Version: {sys.version}")
    #marabou_version = version("maraboupy")
    #print(f"maraboupy ist installiert! Version: {marabou_version}")
    print("marabou erfolgreich geladen!")


    network = Marabou.read_onnx("yices/networks/concrete/classifier_medium.onnx")
    network.getInputQuery().saveQueryAsSmtLib("test_output.smt2")
    print(f"worked")
