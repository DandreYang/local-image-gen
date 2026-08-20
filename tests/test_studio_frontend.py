from __future__ import annotations

import mimetypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "studio" / "static"
sys.path.insert(0, str(ROOT / "studio"))


class TestStaticMime(unittest.TestCase):
    """ES Modules 在错误 MIME 下会被浏览器拒绝执行，必须钉死。"""

    def test_js_resolves_to_javascript(self):
        guessed = mimetypes.guess_type("main.js")[0]
        self.assertIn(
            guessed,
            {"text/javascript", "application/javascript"},
            f"main.js 被识别为 {guessed}，浏览器会拒绝执行 ES Module",
        )

    def test_css_resolves_to_css(self):
        self.assertEqual(mimetypes.guess_type("tokens.css")[0], "text/css")

    def test_server_static_branch_has_mime_fallback(self):
        """server.py 不能只依赖 mimetypes.guess_type 的系统注册表。"""
        source = (ROOT / "studio" / "server.py").read_text(encoding="utf-8")
        self.assertIn(
            "STATIC_MIME",
            source,
            "server.py 缺少显式 MIME 兜底表；系统 mimetypes 注册表在部分环境会把 .js 判成 text/plain",
        )


import re

HEX = re.compile(r"^#([0-9a-fA-F]{6})$")


def _srgb_channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    m = HEX.match(hex_color)
    if not m:
        raise ValueError(f"not a 6-digit hex color: {hex_color}")
    r, g, b = (int(m.group(1)[i : i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _srgb_channel(r)
        + 0.7152 * _srgb_channel(g)
        + 0.0722 * _srgb_channel(b)
    )


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


def read_tokens() -> dict:
    text = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text))


class TestContrast(unittest.TestCase):
    """spec 验收 #3：所有正文与次要文字对比度 >= 4.5:1。"""

    REQUIRED = [
        ("--n-200", "--n-900", 4.5),
        ("--n-200", "--n-850", 4.5),
        ("--n-400", "--n-900", 4.5),
        ("--n-400", "--n-850", 4.5),
        ("--n-050", "--n-950", 4.5),
        ("--accent", "--n-900", 4.5),
    ]

    def test_all_required_pairs_meet_aa(self):
        tokens = read_tokens()
        for fg, bg, floor in self.REQUIRED:
            with self.subTest(fg=fg, bg=bg):
                self.assertIn(fg, tokens, f"tokens.css 缺少 {fg}")
                self.assertIn(bg, tokens, f"tokens.css 缺少 {bg}")
                ratio = contrast_ratio(tokens[fg], tokens[bg])
                self.assertGreaterEqual(
                    round(ratio, 2), floor, f"{fg} on {bg} 只有 {ratio:.2f}:1"
                )

    def test_spacing_scale_defined(self):
        """spec §4.3：间距基数 4px，级数 4/6/8/11/14/18/22。"""
        text = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
        for step in (4, 6, 8, 11, 14, 18, 22):
            with self.subTest(step=step):
                self.assertRegex(
                    text, rf"--s-{step}\s*:\s*{step}px\s*;", f"tokens.css 缺少 --s-{step}"
                )

    def test_legacy_accent_is_gone_in_every_form(self):
        """#e0893c 饱和度过高，与暖调作品抢同一色相。

        会审 P0-4：旧橙在 app.css 里有 6 处是 rgba(224, 137, 60, ...) 形式，
        只查 hex 会全部漏掉。这里同时扫 css/ 全目录与两种写法。
        """
        for path in (STATIC / "css").glob("*.css"):
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(css=path.name):
                self.assertNotIn("#e0893c", text)
                self.assertNotIn("#e79a4e", text)
                self.assertNotIn("#8a5a28", text)
                self.assertNotRegex(
                    text,
                    r"rgba?\(\s*224\s*,\s*137\s*,\s*60",
                    "旧橙以 rgba 形式存活",
                )


class TestCssStructure(unittest.TestCase):
    FILES = ["tokens.css", "base.css", "components.css", "views.css"]

    def test_all_css_files_exist(self):
        for name in self.FILES:
            with self.subTest(name=name):
                self.assertTrue((STATIC / "css" / name).is_file(), f"缺少 css/{name}")

    def test_no_literal_color_outside_tokens(self):
        """除 tokens.css 外不准写字面色值，否则分层配色会被绕过。

        会审 P0-4：只查 #RRGGBB 会被 rgba() / hsl() 绕过，而 app.css 里
        恰恰有 32 种 rgb/rgba 形式。这里三种写法一起查。
        允许 rgba(0,0,0,a) 与 rgba(255,255,255,a) —— 纯黑纯白的透明叠加
        是阴影与高光的通用手法，不属于配色决策。
        """
        pattern = re.compile(
            r"#[0-9a-fA-F]{3,8}\b|hsla?\([^)]*\)|rgba?\([^)]*\)", re.I
        )
        neutral = re.compile(
            r"rgba?\(\s*(0\s*,\s*0\s*,\s*0|255\s*,\s*255\s*,\s*255)\b", re.I
        )
        for name in self.FILES[1:]:
            text = (STATIC / "css" / name).read_text(encoding="utf-8")
            stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            found = [m for m in pattern.findall(stripped) if not neutral.match(m)]
            with self.subTest(name=name):
                self.assertEqual(found, [], f"css/{name} 出现字面色值 {found}，应改用 token")

    def test_index_links_css_in_order(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        order = re.findall(r'href="/static/css/([\w-]+\.css)', html)
        self.assertEqual(order, self.FILES, f"CSS 加载顺序错误：{order}")

    def test_old_monolith_is_gone(self):
        self.assertFalse((STATIC / "app.css").exists(), "app.css 应在拆分后删除")


IMPORT_RE = re.compile(r'^\s*import\s+(?:[^"\']*?\s+from\s+)?["\']([^"\']+)["\']', re.M)


def module_graph() -> dict:
    """返回 {相对路径: [它 import 的相对路径]}，只收本地相对导入。"""
    root = STATIC / "js"
    graph = {}
    for path in sorted(root.rglob("*.js")):
        key = path.relative_to(root).as_posix()
        deps = []
        for spec in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
            if not spec.startswith("."):
                continue
            target = (path.parent / spec).resolve()
            deps.append(target.relative_to(root.resolve()).as_posix())
        graph[key] = deps
    return graph


class TestModuleGraph(unittest.TestCase):
    def test_entry_exists(self):
        self.assertTrue((STATIC / "js" / "main.js").is_file())

    def test_every_import_target_exists(self):
        root = STATIC / "js"
        for module, deps in module_graph().items():
            for dep in deps:
                with self.subTest(module=module, dep=dep):
                    self.assertTrue(
                        (root / dep).is_file(), f"{module} 导入了不存在的 {dep}"
                    )

    def test_imports_carry_explicit_extension(self):
        """浏览器不做扩展名解析，省略 .js 会 404。"""
        root = STATIC / "js"
        for path in root.rglob("*.js"):
            for spec in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
                if spec.startswith("."):
                    with self.subTest(module=path.name, spec=spec):
                        self.assertTrue(spec.endswith(".js"), f"{spec} 缺少 .js 后缀")

    def test_no_cycles(self):
        graph = module_graph()
        state = {}

        def walk(node, stack):
            if state.get(node) == "done":
                return
            if state.get(node) == "visiting":
                self.fail(f"模块循环依赖：{' -> '.join(stack + [node])}")
            state[node] = "visiting"
            for dep in graph.get(node, []):
                walk(dep, stack + [node])
            state[node] = "done"

        for node in graph:
            walk(node, [])

    def test_index_uses_module_type(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn('src="/static/js/main.js"', html)


NAMED_IMPORT_RE = re.compile(
    r'import\s*\{([^}]*)\}\s*from\s*["\'](\.[^"\']+)["\']', re.S
)
EXPORT_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)"
)


class TestSymbolResolution(unittest.TestCase):
    """会审 P0-2：模块存在但导出名拼错，浏览器会静默拒绝整张模块图。

    这是 Task 5 搬运 1431 行时的头号失败模式，而模块图测试只查文件存在。
    """

    def test_every_named_import_is_actually_exported(self):
        root = STATIC / "js"
        for path in sorted(root.rglob("*.js")):
            text = path.read_text(encoding="utf-8")
            for names, spec in NAMED_IMPORT_RE.findall(text):
                target = (path.parent / spec).resolve()
                if not target.is_file():
                    continue  # 由 test_every_import_target_exists 负责
                exported = set(EXPORT_RE.findall(target.read_text(encoding="utf-8")))
                for raw in names.split(","):
                    name = raw.split(" as ")[0].strip()
                    if not name:
                        continue
                    with self.subTest(module=path.name, name=name, target=target.name):
                        self.assertIn(
                            name,
                            exported,
                            f"{path.name} 从 {target.name} 导入了未导出的 {name}",
                        )


DOM_ID_RE = re.compile(r'getElementById\(\s*["\']([\w-]+)["\']')
QUERY_ID_RE = re.compile(r'querySelector(?:All)?\(\s*["\']#([\w-]+)')


class TestDomIdsResolve(unittest.TestCase):
    """会审 P0-2：JS 引用了 HTML 里不存在的 id，运行时才炸。"""

    def test_every_referenced_id_exists_in_html(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        declared = set(re.findall(r'id="([\w-]+)"', html))
        missing = {}
        for path in sorted((STATIC / "js").rglob("*.js")):
            text = path.read_text(encoding="utf-8")
            for ident in DOM_ID_RE.findall(text) + QUERY_ID_RE.findall(text):
                if ident not in declared:
                    missing.setdefault(path.name, set()).add(ident)
        self.assertEqual(missing, {}, f"JS 引用了 index.html 里不存在的 id：{missing}")


if __name__ == "__main__":
    unittest.main()
