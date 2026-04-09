#from enncode.gurobiModelBuilder import GurobiModelBuilder
from gurobipy import GRB
import gurobipy as gp
from z3 import *

def add_gen_constraint_to_gurobi(gen_constraint, gurobi_model, gurobi_vars, eps=1e-3):
    goal = z3.Goal()
    goal.add(gen_constraint)

    # Transformation into Negation Normalform
    tactic = z3.Then(z3.Tactic('nnf'), z3.Tactic('tseitin-cnf'))
    cnf_goal = tactic(goal)[0]

    # Enforce gurobi encoding of the Z3 expression
    for expr in cnf_goal:
        enforce(expr, gurobi_model, gurobi_vars, eps)

    gurobi_model.update()
    print("Z3 Gen-Constraint successfully translated to Gurobi (E-Solver)")

def parse_arith(node, gurobi_vars):
    """ Translates every arithmetic Z3-node into Gurobi linear expression """

    # Check subexpression being a number
    if z3.is_rational_value(node):
        return float(node.numerator_as_long()) / float(node.denominator_as_long())
    elif z3.is_int_value(node):
        return int(node.as_long())
    elif z3.is_algebraic_value(node):
        # Nur für den Notfall, falls MBP irrationale Wurzeln erzeugt
        return float(node.approx(20).as_fraction())

    # Check if node is variable
    elif z3.is_const(node):
        name = str(node.decl().name())
        if name in gurobi_vars:
            return gurobi_vars[name]
        else:
            raise KeyError(f"Unknown variable '{name}' found, missing in var. mapping.")

    # Translate each operation case
    elif z3.is_add(node):
        # Sum over all children (summands)
        return gp.quicksum(parse_arith(c, gurobi_vars) for c in node.children())
    elif z3.is_mul(node):
        res = 1.0
        # Product of all children
        for c in node.children():
            res *= parse_arith(c, gurobi_vars)
        return res
    elif z3.is_sub(node):
        children = node.children()
        res = parse_arith(children[0], gurobi_vars)
        # Subtract each child
        for c in children[1:]:
            res -= parse_arith(c, gurobi_vars)
        return res

    else:
        raise ValueError(f"Unknown math-type of node: {node} (Z3-Declaration: {node.decl()})")


def get_gurobi_ineq(is_not, ineq_node, gurobi_vars, eps=1e-3):
    """ Translates strict inequalities to Gurobi-inequalities with epsilon deviation """
    lhs = parse_arith(ineq_node.children()[0], gurobi_vars)
    rhs = parse_arith(ineq_node.children()[1], gurobi_vars)

    # Fetch operator of expression
    is_le = z3.is_le(ineq_node)
    is_ge = z3.is_ge(ineq_node)
    is_lt = z3.is_lt(ineq_node)
    is_gt = z3.is_gt(ineq_node)
    is_eq = z3.is_eq(ineq_node)

    if is_not:  # If negated, switch the operator accordingly
        if is_le:
            is_gt = True; is_le = False
        elif is_ge:
            is_lt = True; is_ge = False
        elif is_lt:
            is_ge = True; is_lt = False
        elif is_gt:
            is_le = True; is_gt = False
        elif is_eq:
            raise NotImplementedError("Expression 'Not(==)' needs to binary variables")

    if is_le:
        return lhs <= rhs
    elif is_ge:
        return lhs >= rhs
    elif is_lt:
        return lhs <= rhs - eps
    elif is_gt:
        return lhs >= rhs + eps
    elif is_eq:
        return lhs == rhs


def enforce(node, gurobi_model, gurobi_vars, eps):
    """ Traverse through the AST and piecewise encode each subformula as Gurobi constraint"""
    if z3.is_and(node):
        for child in node.children():
            enforce(child, gurobi_model, gurobi_vars, eps)

    elif z3.is_or(node):
        # If node is a disjunction, create binary vars. for each subformula
        bin_vars = []
        for child in node.children():
            b = gurobi_model.addVar(vtype=GRB.BINARY)
            bin_vars.append(b)

            # Check if child is negated
            is_not = z3.is_not(child)
            ineq_node = child.children()[0] if is_not else child

            # Indikator Constraint: b == 1 -> Ungleichung gilt
            gurobi_ineq = get_gurobi_ineq(is_not, ineq_node, gurobi_vars, eps)
            gurobi_model.addGenConstrIndicator(b, True, gurobi_ineq)

        # At least one binary var has to be true (1)
        gurobi_model.addConstr(gp.quicksum(bin_vars) >= 1)
        gurobi_model.update()

    else:
        # Single unequality (leaf) of the tree
        is_not = z3.is_not(node)
        ineq_node = node.children()[0] if is_not else node
        gurobi_ineq = get_gurobi_ineq(is_not, ineq_node, gurobi_vars, eps)
        gurobi_model.addConstr(gurobi_ineq)
        gurobi_model.update()