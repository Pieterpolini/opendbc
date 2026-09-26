"""Minimal KiCad s-expression reader / writer."""

def parse(text):
    i = 0
    n = len(text)

    def skip_ws():
        nonlocal i
        while i < n and text[i] in " \t\r\n":
            i += 1

    def read_node():
        nonlocal i
        skip_ws()
        assert text[i] == "(", (i, text[i - 20:i + 20])
        i += 1
        items = []
        while True:
            skip_ws()
            if text[i] == ")":
                i += 1
                return items
            if text[i] == "(":
                items.append(read_node())
            elif text[i] == '"':
                i += 1
                buf = []
                while text[i] != '"':
                    if text[i] == "\\":
                        buf.append(text[i:i + 2])
                        i += 2
                    else:
                        buf.append(text[i])
                        i += 1
                i += 1
                items.append(Str("".join(buf)))
            else:
                start = i
                while text[i] not in " \t\r\n()":
                    i += 1
                items.append(text[start:i])
        # unreachable

    skip_ws()
    return read_node()


class Str(str):
    """A token that must be emitted quoted."""
    pass


def dumps(node, indent=0):
    if isinstance(node, Str):
        return '"' + str(node).replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(node, str):
        return node
    if isinstance(node, (int, float)):
        return fmt(node)
    parts = [dumps(x) for x in node]
    return "(" + " ".join(parts) + ")"


def fmt(v):
    if isinstance(v, float):
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return str(v)


def find(node, key):
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def findall(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
