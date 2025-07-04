import ast
import operator as op

# Supported operators
operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
}

def safe_eval(expr: str):
    """
    Safely evaluates a string containing a simple mathematical expression.
    Only numbers and basic arithmetic operations are allowed.

    Args:
        expr: The string expression to evaluate.

    Returns:
        The result of the evaluation.

    Raises:
        ValueError: If the expression is invalid or contains unsupported elements.
    """
    try:
        return _eval(ast.parse(expr, mode="eval").body)
    except (TypeError, SyntaxError, KeyError, ZeroDivisionError) as e:
        raise ValueError(f"Invalid expression: {expr}") from e

def _eval(node):
    """Recursively evaluates an AST node."""
    if isinstance(node, ast.Num):  # <number>
        return node.n
    if isinstance(node, ast.BinOp):  # <left> <operator> <right>
        if type(node.op) not in operators:
            raise TypeError(f"Unsupported operator: {type(node.op)}")
        return operators[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
        if type(node.op) not in operators:
            raise TypeError(f"Unsupported operator: {type(node.op)}")
        return operators[type(node.op)](_eval(node.operand))
    
    # Python 3.8+ uses ast.Constant for numbers
    if hasattr(ast, "Constant") and isinstance(node, ast.Constant):
        return node.n

    raise TypeError(f"Unsupported type: {node}") 