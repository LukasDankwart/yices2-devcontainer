from z3 import *
import subprocess
from yices_ws.utils import run_z3_on_smt

def dummy_example():
    Type = DeclareSort('Type')
    subtype = Function('subtype', Type, Type, BoolSort())
    array_of = Function('array_of', Type, Type)
    root = Const('root', Type)

    x, y, z = Consts('x y z', Type)

    axioms = [ForAll(x, subtype(x, x)),
              ForAll([x, y, z], Implies(And(subtype(x, y), subtype(y, z)),
                                        subtype(x, z))),
              ForAll([x, y], Implies(And(subtype(x, y), subtype(y, x)),
                                     x == y)),
              ForAll([x, y, z], Implies(And(subtype(x, y), subtype(x, z)),
                                        Or(subtype(y, z), subtype(z, y)))),
              ForAll([x, y], Implies(subtype(x, y),
                                     subtype(array_of(x), array_of(y)))),

              ForAll(x, subtype(root, x))
              ]
    s = Solver()
    s.add(axioms)
    print(s)
    print(s.check())
    print("Interpretation for Type:")
    print(s.model()[Type])
    print("Model:")
    print(s.model())

def main():
    results = run_z3_on_smt("z3_examples/z3_binarysearch/z3_ef.smt2", ["r0", "r1", "r2", "r3", "r4", "r5", "r6"])
    for (key, val) in results.items():
        print(f"{key}: {val}")



if __name__ == "__main__":
    main()