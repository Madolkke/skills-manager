"""受限 TTP 模板语法；与锁定的 TTP 版本共同维护。"""
import ast
import re
from xml.etree import ElementTree as ET

from skillhub.models.errors import CommandParseError

PATTERNS = {"WORD", "PHRASE", "ROW", "ORPHRASE", "DIGIT", "IP", "PREFIX", "IPV6", "PREFIXV6", "MAC"}
CONTROLS = {"_start_", "_end_", "_line_", "_exact_", "_exact_space_", "ignore"}
FUNCTIONS = PATTERNS | CONTROLS | {
    "re", "to_int", "to_float", "to_str", "to_list", "to_unicode", "lower", "upper", "strip", "lstrip", "rstrip",
    "split", "join", "replace", "contains", "exclude", "equal", "notequal", "isdigit", "notdigit",
    "contains_re", "exclude_re", "startswith_re", "endswith_re", "notstartswith_re", "notendswith_re",
    "set", "default", "joinmatches",
}
VARIABLE = re.compile(r"^[^\W\d]\w*$", re.UNICODE)
PLACEHOLDER = re.compile(r"{{([\s\S]+?)}}")


def invalid() -> CommandParseError:
    """统一模板诊断，不回显原模板中的敏感内容。"""
    return CommandParseError("TTP_TEMPLATE_INVALID", "TTP 模板无效或使用了本接口不支持的标签、属性、函数或参数。", 400)


def literal_attributes(line: str) -> list[dict]:
    """替代 TTP 的 eval 参数加载器，仅允许名称和字面量参数。"""
    result = []
    for part in line.split("|"):
        part = part.strip()
        if not part:
            raise invalid()
        try:
            node = ast.parse(part, mode="eval").body
            if isinstance(node, ast.Name):
                name, args, kwargs = node.id, [], {}
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                args = [ast.literal_eval(arg) for arg in node.args]
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
                if None in kwargs or len(kwargs) != len(node.keywords):
                    raise invalid()
            else:
                raise invalid()
            result.append({"name": name, "args": args, "kwargs": kwargs})
        except (SyntaxError, ValueError, TypeError, RecursionError) as exc:
            raise invalid() from exc
    return result


def validate_template(template: str) -> str:
    """只接受单模板中的 group；先检查标签再交给 TTP，阻止隐式执行路径。"""
    if not template.strip() or len(template) > 50000 or "<!" in template or "<?" in template:
        raise invalid()
    try:
        root = ET.fromstring("<root>" + template + "</root>")
    except (ET.ParseError, RecursionError) as exc:
        raise invalid() from exc
    children = list(root)
    if len(children) == 1 and children[0].tag == "template":
        if (root.text or "").strip() or (children[0].tail or "").strip() or children[0].attrib:
            raise invalid()
        root = children[0]
    for element in root.iter():
        if element is not root:
            if element.tag != "group" or set(element.attrib) - {"name", "method"}:
                raise invalid()
            if element.get("method", "group") not in {"group", "table"}:
                raise invalid()
            name = element.get("name", "")
            if name and not re.fullmatch(r"[\w.*{} -]+", name):
                raise invalid()
            for match in PLACEHOLDER.finditer(name):
                if not VARIABLE.fullmatch(match[1].strip()):
                    raise invalid()
        for text in (element.text or "", element.tail or ""):
            residue = PLACEHOLDER.sub("", text)
            if "{{" in residue or "}}" in residue:
                raise invalid()
            for match in PLACEHOLDER.finditer(text):
                attributes = literal_attributes(match[1])
                first = attributes[0]
                if not VARIABLE.fullmatch(first["name"]) or first["args"] or first["kwargs"]:
                    raise invalid()
                for item in attributes[1:]:
                    if item["name"] not in FUNCTIONS:
                        raise invalid()
    if not PLACEHOLDER.search("".join(root.itertext())):
        raise invalid()
    root.tag = "template"
    return ET.tostring(root, encoding="unicode")
