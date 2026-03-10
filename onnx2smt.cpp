#include "InputQuery.h"
#include "ONNXParser.h"
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 3) {
            std::cerr << "Usage: onnx2smt <in.onnx> <out.smt2>\n";
            return 1;
    }
    try {
        InputQuery query;
        ONNXParser::parse(query, String(argv[1]));
        query.saveQueryAsSmtLib(String(argv[2]));
        std::cout << "SMT data successfully generated: " << argv[2] << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error while converting: " << e.what() << std::endl;
        return 1;
    }
}