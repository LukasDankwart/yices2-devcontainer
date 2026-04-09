### Idea:

The idea was to use YICES2 E/F-Solver for computing Counterfactual Explanations on incomplete inputs.
Let y be the missing input value of an input vector x and r the recourse.
This could be represented as: 
- Exists r: Forall Y: f(x+r) = t

where t is the target class, x is the input with a missing value (y) and f is the NN-classifier.

### Takeaways:
- YICES2 python bindings currently do not support non quantifier free logics
- To maintain the Python workflow, you can call yices via subprocesses and model the formulation in an SMT file
- Initial attempts have been made to parse at least ReLu + Gemm nets into suitable SMT files.
- This approach was pursued to the point where a binary search was implemented and, accordingly, valid CX values 
 could be found for a defined deviation threshold. But y has to be bounded and was only tested for [-1, +1]

To perform actual optimization without binary search, an attempt was made to build a kind of CEGAR loop using a combination of E-Solver (optimizer) and F-Solver (solver).
- E-Optimizer predicts a candidate for the recourse vector r (initial 0 vector)
- F-Solver then checks if there exists a y (between given bounds) through which the candidate is not a valid recourse.
- - if UNSAT: recourse r is valid for every possible y between defined bounds
- - if SAT: compute generalized constraint that excludes more than current candidate
- - - project a linear core by "freezing" the network with current valus for r and y
- - - this core should represent the atoms that caused the cx to break
- - - computing generealized constraints can be done by substitution of current r vals and a kind of QE for the remaining y
- - - this expression negated represent "a bad space" for r, where at least one y betweend defined bounds would break it

This was done using z3 since it offers tactics for QE etc. and has an optimizer engine.
It worked for a small example where the optimal cx was known from binary search. However, trying to use bigger neural networks with more 
classes would cause more inequalities for the "target-class" condition. But this is where the "QE" tactic of z3 doesn't terminate anymore (or at least in a reasonable time).

The variablen elimination represented in the yices2 paper (Virtual term substitution) might be a solution, but 
implementing it yourself would require transforming all inequalities so that the missing input is on one side and an arithmetic expression is on the other.
Since neither z3 or gurobi do support help for this; the effort was perceived as too great.
Especially considering that even then, the question remains as to when the EF loop would terminate. And what network sizes would even be possible.

An additional motivation was to integrate such a loop into our enncode library. However, to our current knowledge, 
Gurobi also does not support any kind of QE or similar methods, which means that the previous approach could not yet be successfully converted to a Gurobi+z3 / Gurobi+Gurobi EF loop.




