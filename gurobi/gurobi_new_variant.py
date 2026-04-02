from z3 import *
from enncode.gurobiModelBuilder import GurobiModelBuilder
from gurobipy import GRB
import gurobipy as gp
from z3_examples.z3_gen_example import extract_mbp_core


import z3

concrete_input = [
        -0.021025,
        -1.043187,
        0.300265,
        0.570702,
        -1.124416,
        -1.794718,
        0.569139,
        -0.361468
]