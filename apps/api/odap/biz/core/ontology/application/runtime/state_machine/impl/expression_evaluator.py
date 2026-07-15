import ast
import operator

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}

_SAFE_NAMES = {
    "True": True,
    "False": False,
    "None": None,
    "len": len,
    "abs": abs,
    "min": min,
    "max": max,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "isinstance": isinstance,
    "hasattr": hasattr,
    "getattr": getattr,
}


class SafeExpressionEvaluator:
    def __init__(self, context: dict):
        self._context = context

    def evaluate(self, expression: str) -> bool:
        if not expression or not expression.strip():
            return True
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            return bool(self._eval_node(tree.body))
        except Exception:
            return False

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self._context:
                return self._context[node.id]
            if node.id in _SAFE_NAMES:
                return _SAFE_NAMES[node.id]
            raise NameError(f"Name '{node.id}' is not allowed")
        if isinstance(node, ast.Attribute):
            value = self._eval_node(node.value)
            if isinstance(value, dict) and node.attr in value:
                return value[node.attr]
            return getattr(value, node.attr)
        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value)
            slice_val = self._eval_node(node.slice)
            return value[slice_val]
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type in _SAFE_OPERATORS:
                return _SAFE_OPERATORS[op_type](self._eval_node(node.left), self._eval_node(node.right))
            raise TypeError(f"Operator {op_type.__name__} is not allowed")
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                op_type = type(op)
                if op_type not in _SAFE_OPERATORS:
                    raise TypeError(f"Comparison {op_type.__name__} is not allowed")
                right = self._eval_node(comparator)
                if not _SAFE_OPERATORS[op_type](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = True
                for value in node.values:
                    result = self._eval_node(value)
                    if not result:
                        return result
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for value in node.values:
                    result = self._eval_node(value)
                    if result:
                        return result
                return result
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return not self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -self._eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +self._eval_node(node.operand)
        if isinstance(node, ast.Call):
            func = self._eval_node(node.func)
            args = [self._eval_node(arg) for arg in node.args]
            return func(*args)
        if isinstance(node, ast.IfExp):
            if self._eval_node(node.test):
                return self._eval_node(node.body)
            return self._eval_node(node.orelse)
        if isinstance(node, ast.List):
            return [self._eval_node(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return dict(zip(
                [self._eval_node(k) for k in node.keys],
                [self._eval_node(v) for v in node.values],
            ))
        if isinstance(node, ast.Set):
            return {self._eval_node(e) for e in node.elts}
        raise TypeError(f"Node type {type(node).__name__} is not allowed")


def safe_eval(expression: str, context: dict) -> bool:
    return SafeExpressionEvaluator(context).evaluate(expression)
