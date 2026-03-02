from yices import *

def main():

    # Set up block
    cfg = Config()
    ctx = Context(cfg)
    int_t = Types.int_type()
    zero = Terms.integer(0)

    print(f"Context has status: {ctx.status}")

    x_var = Terms.new_variable(int_t, 'x')
    y_var = Terms.new_variable(int_t, 'y')

    y_gt_0 = Terms.arith_eq0_atom(y_var)
    y_sub_x = Terms.sub(y_var, x_var)
    sub_eq_zero = Terms.arith_eq0_atom(y_sub_x)

    inner_formula = Terms.yand([y_gt_0, sub_eq_zero])

    exists_formula = Terms.exists([x_var, y_var], inner_formula)

    ctx.assert_formula(exists_formula)

    status = ctx.check_context()

    if status == Status.SAT:
        print(f"Formula is satisfiable.")
        model = Model.from_context(ctx, 1)
        model_string = model.to_string(80, 100, 0)
        print(model_string)
    else:
        print("Formula is not satisfiable.")

    ctx.dispose()
    cfg.dispose()

if __name__ == "__main__":
    main()