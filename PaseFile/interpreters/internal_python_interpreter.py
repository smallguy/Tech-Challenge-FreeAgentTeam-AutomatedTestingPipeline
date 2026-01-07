import ast
import difflib
import importlib
import typing
from typing import Any, ClassVar, Dict, List, Optional

from .base import BaseInterpreter
from .interpreter_error import InterpreterError


class InternalPythonInterpreter(BaseInterpreter):
    r"""
    一种定制化的 Python 解释器，用于控制大语言模型（LLM）生成代码的执行过程。
    该解释器确保代码仅能执行动作空间（action space）中指定的函数，且仅能导入白名单（white list）内的模块/函数。
    同时，它还支持模糊变量匹配功能，以检索名称不确定的输入变量。
    .. highlight:: none
    本类改编自 Hugging Face 的实现代码python_interpreter.py <https://github.com/huggingface/transformers/blob/8f093fb799246f7dd9104ff44728da0c53a9f67a/src/transformers/tools/python_interpreter.py>_。
    原许可协议适用：版权所有 2023 The HuggingFace Inc. 团队。保留所有权利。
    依据 Apache 许可证 2.0 版（以下简称“许可证”）授权；除非遵守许可证规定，否则您不得使用本文件。您可在以下地址获取许可证副本：
    http://www.apache.org/licenses/LICENSE-2.0
    除非适用法律要求或书面同意，否则按“原样”分发的软件不附带任何明示或暗示的担保或条件。详见许可证中关于权限和限制的特定语言规定。
    我们已对原始代码进行修改以适配自身需求：将原函数封装为类，并在执行后保存解释器状态；新增对import语句、for语句以及若干二元/一元运算符的支持；添加导入白名单机制以保障import语句的安全性；
    此外，我们修改了变量匹配逻辑，并引入:obj:fuzz_state`实现模糊匹配。
    修改部分的版权所有（C）2023 CAMEL-AI.org
    参数说明：action_space (Dict [str, Any], 可选)：将动作名称映射至对应函数/对象的字典。
    解释器仅能执行两类函数——直接列于该字典中的函数，或字典内对象的成员函数。
    action_space的概念源自 EmbodiedAgent（具身智能体），代表智能体可执行的动作集合。
    若为None，则默认设为空字典。（默认值：:obj:None）import_white_list (List [str], 可选)：存储代码中允许导入的 Python 模块/函数的列表。
    列表中所列模块的所有子模块和函数均可导入，其余导入语句均会被拒绝。模块与其子模块/函数名之间用句点（:obj:.）分隔。
    （默认值：:obj:None）unsafe_mode (bool, 可选)：若设为True，解释器将通过eval()/exec()执行代码，且不进行任何安全检查。
    （默认值：:obj:False）raise_error (bool, 可选)：若解释器执行失败，是否抛出异常。（默认值：:obj:False）
    """

    _CODE_TYPES: ClassVar[List[str]] = ["python", "py", "python3", "python2"]


    _DEFAULT_BUILTINS = {
        "range": range,
        "len": len,
        "print": print,
    }

    # ➋ default允许 import 的module（按需增删）
    _DEFAULT_IMPORTS = [
        "math",
        "sympy",            # 整个 sympy
        "astor",
        "sympy.core",       # ——如果想更细粒度可拆分
        "sympy.symbols",
    ]

    def __init__(
        self,
        action_space: Optional[Dict[str, Any]] = None,
        import_white_list: Optional[List[str]] = None,
        unsafe_mode: bool = False,
        raise_error: bool = False,
    ) -> None:
        # self.action_space = action_space or dict()
        self.action_space = {**self._DEFAULT_BUILTINS,** (action_space or {})}
        self.state = self.action_space.copy()
        self.fuzz_state: Dict[str, Any] = dict()
        # self.import_white_list = import_white_list or list()
        self.import_white_list = list(
            {*(import_white_list or []), *self._DEFAULT_IMPORTS}
        )
        self.raise_error = raise_error
        self.unsafe_mode = unsafe_mode

    def run(self, code: str, code_type: str) -> str:
        r"""在解释器中执行给定的代码及指定的代码类型。

        该方法接收一段代码字符串及其类型，检查代码类型是否受支持，然后执行代码。如果`unsafe_mode`
        设置为`False`，代码将在受控环境中通过`execute`方法执行。如果`unsafe_mode`为`True`，代码将
        使用`eval()`或`exec()`在动作空间作为全局上下文的环境中执行。
        如果代码类型不受支持或执行过程中发生任何运行时错误，将抛出`InterpreterError`。

        参数：
            code (str)：要执行的python代码。
            code_type (str)：代码的类型，必须是受支持的代码类型之一（`python`、`py`、`python3`、`python2`）。


        返回：
            str：执行代码输出的字符串表示。

        抛出：
            InterpreterError：如果`code_type`不受支持或代码执行过程中发生任何运行时错误。
        """
        if code_type not in self._CODE_TYPES:
            raise InterpreterError(
                f"不支持的代码类型 {code_type}。"
                f"`{self.__class__.__name__}` 仅支持 "
                f"{', '.join(self._CODE_TYPES)}。"
            )
        if self.unsafe_mode:
            import contextlib
            import io

            # 首先尝试执行并捕获标准输出
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                exec(code, self.action_space)
            result = output_buffer.getvalue()

            # 如果没有捕获到输出，尝试计算代码
            if not result:
                try:
                    result = str(eval(code, self.action_space))
                except (SyntaxError, NameError):
                    result = ""  # 如果eval失败，返回空字符串

            return result
        else:
            return str(self.execute(code))

    def update_action_space(self, action_space: Dict[str, Any]) -> None:
        r"""更新*python*解释器的动作空间。"""
        self.action_space.update(action_space)

    def supported_code_types(self) -> List[str]:
        r"""提供解释器支持的代码类型。"""
        return self._CODE_TYPES

    def execute(
        self,
        code: str,
        state: Optional[Dict[str, Any]] = None,
        fuzz_state: Optional[Dict[str, Any]] = None,
        keep_state: bool = True,
    ) -> Any:
        r"""在安全环境中执行输入的python代码。

        参数：
            code (str)：要执行的生成的python代码。
            state (Optional[Dict[str, Any]], 可选)：生成的代码中可能使用的外部变量。（默认值：:obj:`None`）
            fuzz_state (Optional[Dict[str, Any]], 可选)：变量名不确定的外部变量。解释器将使用模糊匹配来访问这些变量。
                例如，如果:obj:`fuzz_state`包含变量:obj:`image`，生成的代码可以使用:obj:`input_image`来访问它。
                （默认值：:obj:`None`）
            keep_state (bool, 可选)：如果为:obj:`True`，:obj:`state`和:obj:`fuzz_state`将为后续执行保留。
                否则，它们将被清除。（默认值：:obj:`True`）

        返回：
            Any：代码中最后一条语句（不包括"import"）的值。对于此解释器，表达式的值是其本身的值，
                "assign"语句的值是被赋值的值，"if"和"for"块语句的值是块中最后一条语句的值。
        """

        if state is not None:
            self.state.update(state)
        if fuzz_state is not None:
            self.fuzz_state.update(fuzz_state)

        try:
            expression = ast.parse(code)
        except SyntaxError as e:
            if self.raise_error:
                raise InterpreterError(f"代码中的语法错误：{e}")
            else:
                import traceback

                return traceback.format_exc()

        result = None
        for idx, node in enumerate(expression.body):
            try:
                line_result = self._execute_ast(node)
            except InterpreterError as e:
                if not keep_state:
                    self.clear_state()
                msg = (
                    f"代码的执行在节点 {idx} 处停止。"
                    f"详见：\n{e}"
                )
                # `ast.unparse()`可以提供更多信息，这是python 3.9中的新功能。
                if self.raise_error:
                    raise InterpreterError(msg)
                else:
                    import traceback

                    return traceback.format_exc()
            if line_result is not None:
                result = line_result

        if not keep_state:
            self.clear_state()

        return result

    def clear_state(self) -> None:
        r"""初始化:obj:`state`和:obj:`fuzz_state`。"""
        self.state = self.action_space.copy()
        self.fuzz_state = {}

    # ast.Index在python 3.9之后已弃用，无法通过类型检查，但对于旧版本仍然必要。
    @typing.no_type_check
    def _execute_ast(self, expression: ast.AST) -> Any:
        if isinstance(expression, ast.Assign):
            # 赋值 -> 计算赋值，这应该会更新状态。我们返回被赋值的变量，因为它可能用于确定最终结果。
            return self._execute_assign(expression)
        elif isinstance(expression, ast.Attribute):
            value = self._execute_ast(expression.value)
            return getattr(value, expression.attr)
        elif isinstance(expression, ast.BinOp):
            # 二元运算符 -> 返回结果值
            return self._execute_binop(expression)
        elif isinstance(expression, ast.Call):
            # 函数调用 -> 返回函数调用的值
            return self._execute_call(expression)
        elif isinstance(expression, ast.Compare):
            # 比较 -> 返回True或False
            return self._execute_condition(expression)
        elif isinstance(expression, ast.Constant):
            # 常量 -> 只需返回值
            return expression.value
        elif isinstance(expression, ast.Dict):
            # 字典 -> 计算所有键和值
            result: Dict = {}
            for k, v in zip(expression.keys, expression.values):
                if k is not None:
                    result[self._execute_ast(k)] = self._execute_ast(v)
                else:
                    result.update(self._execute_ast(v))
            return result
        elif isinstance(expression, ast.Expr):
            # 表达式 -> 计算内容
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.For):
            return self._execute_for(expression)
        elif isinstance(expression, ast.FormattedValue):
            # 格式化值（f-string的一部分）-> 计算内容并返回
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.If):
            # If -> 执行正确的分支
            return self._execute_if(expression)
        elif isinstance(expression, ast.Import):
            # Import -> 在self.state中添加导入的名称并返回None。
            self._execute_import(expression)
            return None
        elif isinstance(expression, ast.ImportFrom):
            self._execute_import_from(expression)
            return None
        elif hasattr(ast, "Index") and isinstance(expression, ast.Index):
            # 无法通过类型检查
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.JoinedStr):
            return "".join(
                [str(self._execute_ast(v)) for v in expression.values]
            )
        elif isinstance(expression, ast.List):
            # 列表 -> 计算所有元素
            return [self._execute_ast(elt) for elt in expression.elts]
        elif isinstance(expression, ast.Name):
            # 名称 -> 从状态中获取值
            return self._execute_name(expression)
        elif isinstance(expression, ast.Subscript):
            # 下标 -> 返回索引的值
            return self._execute_subscript(expression)
        elif isinstance(expression, ast.Tuple):
            return tuple([self._execute_ast(elt) for elt in expression.elts])
        elif isinstance(expression, ast.UnaryOp):
            # 一元运算符 -> 返回结果值
            return self._execute_unaryop(expression)
        else:
            # 目前我们拒绝其他任何类型。我们会根据需要添加内容。
            raise InterpreterError(
                f"{expression.__class__.__name__} 不受支持。"
            )

    def _execute_assign(self, assign: ast.Assign) -> Any:
        targets = assign.targets
        result = self._execute_ast(assign.value)

        for target in targets:
            self._assign(target, result)
        return result

    def _assign(self, target: ast.expr, value: Any):
        if isinstance(target, ast.Name):
            self.state[target.id] = value
        elif isinstance(target, ast.Tuple):
            if not isinstance(value, tuple):
                raise InterpreterError(
                    f"预期类型为tuple，但得到的是"
                    f"{value.__class__.__name__}。"
                )
            if len(target.elts) != len(value):
                raise InterpreterError(
                    f"预期 {len(target.elts)} 个值，但得到"
                    f" {len(value)} 个。"
                )
            for t, v in zip(target.elts, value):
                self.state[self._execute_ast(t)] = v
        else:
            raise InterpreterError(
                f"不支持的变量类型。预期"
                f"ast.Name或ast.Tuple，得到的是"
                f"{target.__class__.__name__}。"
            )

    def _execute_call(self, call: ast.Call) -> Any:
        callable_func = self._execute_ast(call.func)

        # 待处理参数
        args = [self._execute_ast(arg) for arg in call.args]
        kwargs = {
            keyword.arg: self._execute_ast(keyword.value)
            for keyword in call.keywords
        }
        return callable_func(*args, **kwargs)

    def _execute_subscript(self, subscript: ast.Subscript):
        index = self._execute_ast(subscript.slice)
        value = self._execute_ast(subscript.value)
        if not isinstance(subscript.ctx, ast.Load):
            raise InterpreterError(
                f"{subscript.ctx.__class__.__name__} 不支持用于"
                "下标。"
            )
        if isinstance(value, (list, tuple)):
            return value[int(index)]
        if index in value:
            return value[index]
        if isinstance(index, str) and isinstance(value, dict):
            close_matches = difflib.get_close_matches(
                index,
                [key for key in list(value.keys()) if isinstance(key, str)],
            )
            if len(close_matches) > 0:
                return value[close_matches[0]]

        raise InterpreterError(f"无法用 '{index}' 索引 {value}。")

    def _execute_name(self, name: ast.Name):
        if isinstance(name.ctx, ast.Store):
            return name.id
        elif isinstance(name.ctx, ast.Load):
            return self._get_value_from_state(name.id)
        else:
            raise InterpreterError(f"{name.ctx} 不受支持。")

    def _execute_condition(self, condition: ast.Compare):
        if len(condition.ops) > 1:
            raise InterpreterError(
                "无法计算具有多个运算符的条件"
            )

        left = self._execute_ast(condition.left)
        comparator = condition.ops[0]
        right = self._execute_ast(condition.comparators[0])

        if isinstance(comparator, ast.Eq):
            return left == right
        elif isinstance(comparator, ast.NotEq):
            return left != right
        elif isinstance(comparator, ast.Lt):
            return left < right
        elif isinstance(comparator, ast.LtE):
            return left <= right
        elif isinstance(comparator, ast.Gt):
            return left > right
        elif isinstance(comparator, ast.GtE):
            return left >= right
        elif isinstance(comparator, ast.Is):
            return left is right
        elif isinstance(comparator, ast.IsNot):
            return left is not right
        elif isinstance(comparator, ast.In):
            return left in right
        elif isinstance(comparator, ast.NotIn):
            return left not in right
        else:
            raise InterpreterError(f"不支持的运算符：{comparator}")

    def _execute_if(self, if_statement: ast.If):
        result = None
        if not isinstance(if_statement.test, ast.Compare):
            raise InterpreterError(
                "if语句中仅支持Compare表达式，得到的是"
                f" {if_statement.test.__class__.__name__}"
            )
        if self._execute_condition(if_statement.test):
            for line in if_statement.body:
                line_result = self._execute_ast(line)
                if line_result is not None:
                    result = line_result
        else:
            for line in if_statement.orelse:
                line_result = self._execute_ast(line)
                if line_result is not None:
                    result = line_result
        return result

    def _execute_for(self, for_statement: ast.For):
        result = None
        for value in self._execute_ast(for_statement.iter):
            self._assign(for_statement.target, value)
            for line in for_statement.body:
                line_result = self._execute_ast(line)
                if line_result is not None:
                    result = line_result

        return result

    def _execute_import(self, import_module: ast.Import) -> None:
        for module in import_module.names:
            self._validate_import(module.name)
            alias = module.asname or module.name
            self.state[alias] = importlib.import_module(module.name)

    def _execute_import_from(self, import_from: ast.ImportFrom):
        if import_from.module is None:
            raise InterpreterError("不支持\"from . import\"。")
        for import_name in import_from.names:
            full_name = import_from.module + f".{import_name.name}"
            self._validate_import(full_name)
            imported_module = importlib.import_module(import_from.module)
            alias = import_name.asname or import_name.name
            self.state[alias] = getattr(imported_module, import_name.name)

    def _validate_import(self, full_name: str):
        tmp_name = ""
        found_name = False
        for name in full_name.split("."):
            tmp_name += name if tmp_name == "" else f".{name}"
            if tmp_name in self.import_white_list:
                found_name = True
                return

        if not found_name:
            raise InterpreterError(
                f"不允许导入模块白名单之外的模块（尝试导入"
                f"{full_name}）。"
            )

    def _execute_binop(self, binop: ast.BinOp):
        left = self._execute_ast(binop.left)
        operator = binop.op
        right = self._execute_ast(binop.right)

        if isinstance(operator, ast.Add):
            return left + right
        elif isinstance(operator, ast.Sub):
            return left - right
        elif isinstance(operator, ast.Mult):
            return left * right
        elif isinstance(operator, ast.Div):
            return left / right
        elif isinstance(operator, ast.FloorDiv):
            return left // right
        elif isinstance(operator, ast.Mod):
            return left % right
        elif isinstance(operator, ast.Pow):
            return left ** right
        elif isinstance(operator, ast.LShift):
            return left << right
        elif isinstance(operator, ast.RShift):
            return left >> right
        elif isinstance(operator, ast.MatMult):
            return left @ right
        else:
            raise InterpreterError(f"不支持的运算符：{operator}")

    def _execute_unaryop(self, unaryop: ast.UnaryOp):
        operand = self._execute_ast(unaryop.operand)
        operator = unaryop.op

        if isinstance(operator, ast.UAdd):
            return +operand
        elif isinstance(operator, ast.USub):
            return -operand
        elif isinstance(operator, ast.Not):
            return not operand
        else:
            raise InterpreterError(f"不支持的运算符：{operator}")

    def _get_value_from_state(self, key: str) -> Any:
        if key in self.state:
            return self.state[key]
        else:
            close_matches = difflib.get_close_matches(
                key, list(self.fuzz_state.keys()), n=1
            )
            if close_matches:
                return self.fuzz_state[close_matches[0]]
            else:
                raise InterpreterError(f"变量 `{key}` 未定义。")
