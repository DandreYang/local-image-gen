#!/usr/bin/env python3
"""Deterministic prompt profiles and frozen optimizer contracts.

Stdlib only. The CLI calls this before any image backend. It never launches
agy, cursor-agent, or Codex as an agent. Live text-model HTTP stays in
local_image_gen.py so this module stays easy to unit-test.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


PROMPT_PROFILES = ("cover", "poster", "portrait", "product", "edit")
OPTIMIZE_MODES = ("off", "on", "auto")
PROMPT_FAMILIES = ("imagine", "gpt_image", "nano_banana")

GENERIC_MAX_CHARS = 180

STRUCTURED_MARKERS = (
    "asset type:",
    "use case:",
    "primary request:",
    "scene/backdrop:",
    "style/medium:",
    "composition/framing:",
    "lighting/mood:",
    "color palette:",
    "materials/textures:",
    "text (verbatim):",
    "typography:",
    "constraints:",
    "keep ",
    "change only",
    "change only ",
    "do not restyle",
    "用途：",
    "用途:",
    "资产类型：",
    "资产类型:",
    "主体：",
    "主体:",
    "构图：",
    "构图:",
    "约束：",
    "约束:",
    "保留",
    "只改",
    "不要改",
    "不要重绘",
)

GPT_IMAGE_LABELS = (
    "use case:",
    "asset type:",
    "primary request:",
    "scene/backdrop:",
    "style/medium:",
    "composition/framing:",
    "lighting/mood:",
    "color palette:",
    "materials/textures:",
    "text (verbatim):",
    "typography:",
    "input images:",
    "用途：",
    "用途:",
    "资产类型：",
    "资产类型:",
)

REFUSAL_MARKERS = (
    "i can't",
    "i cannot",
    "i'm unable",
    "i am unable",
    "as an ai",
    "sorry, i",
    "cannot help",
    "can't help",
    "无法",
    "我不能",
    "抱歉",
    "对不起，我",
)

VENDOR_TEXT_MODELS = {
    "grok": "grok-4.6",
    "openai": "gpt-5.6-terra",
    "gemini": "gemini-2.5-flash",
}

VENDOR_TEXT_MODEL_ENV = {
    "grok": "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_GROK",
    "openai": "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_OPENAI",
    "gemini": "LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_GEMINI",
}

FAMILY_TO_TEXT_VENDOR = {
    "imagine": "grok",
    "gpt_image": "openai",
    "nano_banana": "gemini",
}

PROVIDER_FAMILY = {
    "grok": "imagine",
    "xai": "imagine",
    "openai": "gpt_image",
    "codex": "gpt_image",
    "gemini": "nano_banana",
    "antigravity": "nano_banana",
    "agy": "nano_banana",
    "cursor": "nano_banana",
}

FAMILY_TEXT_BACKENDS = {
    "imagine": ("grok", "openai", "gemini"),
    "gpt_image": ("openai", "grok", "gemini"),
    "nano_banana": ("gemini", "grok", "openai"),
}

_SHARED_COMPILER_RULES = """
You are a prompt compiler for a local image CLI. Emit ONE final prompt the
image model will receive.

Hard rules:
- Output ONLY the final prompt. No title, no quotes, no markdown, no preamble.
- Same language as the user request. Chinese in, Chinese out. English in, English out.
- If the user already wrote a detailed prompt, normalize it. Do not add a story.
- If the input is already a finished prompt for a different image family,
  rewrite only craft and structure. Keep subject, visible text, constraints,
  and language. Do not invent a new scene.
- Do not add brands, slogans, celebrities, named real people, extra objects, or
  a narrative the user did not ask for.
- No Midjourney / Stable Diffusion tag soup. Never write masterpiece, 8k,
  best quality, 1girl, --ar, or comma-separated quality tags.
- Prefer positive description. If the user forbade text, say once: no text,
  letters, logos, or watermarks.
- Translate aspect into composition words (wide landscape, tall portrait,
  square). Do not write ratio numerals such as 16:9 — models sometimes paint them.
- For edits: name what stays and what changes. Do not invent a new scene.
- If reference images are present, treat image 1 as the source to edit unless
  the user assigned roles. Extra images are references, not extra subjects.
- Grok Imagine and Antigravity/Cursor Nano Banana do not rewrite the prompt
  on the CLI path. Your output is what they paint. Write it fully.
""".strip()

IMAGINE_SCAFFOLD = """
Think in this order, then write. Skip a beat if you have nothing true to say.
Do not invent a brand, person, or object to fill a beat. Do not over-specify.

subject → action/pose → setting → style → composition → lighting/mood → one key detail

Grok Imagine wants 2 to 5 cinematic sentences, one coherent scene.
Front-load the subject. Give strong high-level direction. Do not fill every slot.
Positive description. No keyword tags. No "award-winning" or "ultra-premium" padding.
Never print labels such as "Use case:" or "Asset type:".
For edits, describe the desired end state and what must stay identical.
""".strip()

GPT_IMAGE_SCAFFOLD = """
Fill this Codex $imagegen scaffold. Skip empty slots.
Do not invent a use-case slug, brand, or object just to fill a line.
Add Typography: only when the user asked for visible text.

Use case: <photorealistic-natural | product-mockup | ui-mockup | ads-marketing |
  illustration-story | stylized-concept | identity-preserve | precise-object-edit |
  lighting-weather | background-extraction | style-transfer | compositing | other>
Asset type: <where the asset will be used>
Primary request: <the user's main ask>
Input images: <Image 1: edit target | reference | style | scene> (only if images exist)
Scene/backdrop: <setting; for campaigns, a spatial story — where each beat sits>
Subject: <main subject>
Style/medium: <photo / illustration / 3D / watercolor / ...>
Composition/framing: <wide / tall / square / close / reserved type area>
Lighting/mood: <light + mood>
Color palette: <closed set of colors, only if it helps>
Materials/textures: <real surfaces>
Text (verbatim): "<exact text>" (only if the user asked for visible text)
Typography: <hierarchy, face, placement; only if there is on-image text>
Constraints: <must keep; for campaigns, the readable story>
Avoid: <this job's failure modes, not quality-tag soup>
""".strip()

NANO_BANANA_SCAFFOLD = """
Think with Google's Nano Banana formula. Skip a beat if you have nothing true to say.
Do not invent a brand, person, or object to fill a beat.

Generate: [Subject] + [Action] + [Location/context] + [Composition] + [Style]
With references: [Relationship of each image] + [New scenario]
Edits: what changes + what stays exactly the same

Start a generate prompt with a strong verb (Create / Present / Using).
Write a director brief: concrete materials, wardrobe, surfaces, camera/framing,
and lighting. Positive framing ("empty street", not "no cars").
If the user asked for visible text, put the exact words in quotes and name
the type style. One dense paragraph or 3 to 8 sentences is fine.
Never print labels such as "Use case:" or "Asset type:".
""".strip()

FAMILY_SCAFFOLDS = {
    "imagine": IMAGINE_SCAFFOLD,
    "gpt_image": GPT_IMAGE_SCAFFOLD,
    "nano_banana": NANO_BANANA_SCAFFOLD,
}

FAMILY_COMPILER_RULES = {
    "imagine": """
Output format: 2 to 5 natural-language sentences. Front-load the subject.
Do NOT print scaffold labels such as "Use case:" or "Asset type:".
Grok Imagine paints cinematic prose. Keep it high-level and one scene.
""".strip(),
    "gpt_image": """
Output format: the filled scaffold only. One labeled line per used slot.
Skip empty slots. Keep English labels; write values in the user's language.
gpt-image-2 follows concrete nouns, spatial layout, and labeled specs.
Name materials and where empty space or type sits. For campaigns, write
Scene as a spatial story and treat on-image copy as first-class slots.
For edits, preserve identity and geometry unless the user asked to restyle.
""".strip(),
    "nano_banana": """
Output format: a director brief in natural language. No scaffold labels.
Nano Banana / Gemini follow detailed conversational language, including Chinese.
Be concrete about materials, wardrobe, surfaces, camera, and lighting.
For edits, keep the subject and only describe the requested change.
""".strip(),
}

COMPILER_EXAMPLES = {
    "imagine": """
Examples of the only thing you should output:

User: 水彩狐狸在雪林里
雪林里一只停住的水彩狐狸，锈红皮毛衬着淡蓝阴影。纸面带着水渍边，细长松干和落雪，偏低的侧向取景。没有文字、字母、标志或水印。

User: 保留人物，只把背景换成干净白墙
保留同一个人、面孔、姿势、衣服和取景。只把背景换成干净白墙和均匀柔光。不要重绘主体，也不要改身份。
""".strip(),
    "nano_banana": """
Examples of the only thing you should output:

User: 水彩狐狸在雪林里
创建一幅雪林水彩：一只锈红狐狸停在细长松干边，淡蓝阴影，纸面水渍边清晰可见。偏低侧向中景，冷日光，落雪很轻。画面里不要文字、字母、标志或水印。

User: 保留人物，只把背景换成干净白墙
Keep the same person, face, pose, clothing, and framing exactly. Change only the background to a clean white studio wall with even soft light. Do not restyle the subject or change identity.

User: 可回收火箭海报，大标题「冲破边界」
创建一张竖构图航天活动海报：一枚白蓝可回收运载火箭斜向穿出风暴云进入近太空，金蓝尾焰拉出对角线；下方同一枚一子级在夜间海上回收平台受控着陆，灯环倒映水面。左上留出干净深蓝负空间。大标题写「冲破边界」，粗黑体，纯白，必须完整清晰。陶瓷白箭体、栅格舵、凝结、乱云、海面反光。没有其它字，没有商标。
""".strip(),
    "gpt_image": """
Examples of the only thing you should output:

User: 水彩狐狸在雪林里
Use case: illustration-story
Asset type: storybook plate
Primary request: 水彩狐狸在雪林里
Scene/backdrop: quiet snow forest, falling flakes
Subject: a fox pausing, rust fur against pale blue shadow
Style/medium: watercolor on paper with wet edges
Composition/framing: tall vertical, low sideways view
Lighting/mood: cold daylight, calm
Constraints: no text, letters, logos, or watermarks

User: 保留人物，只把背景换成干净白墙
Use case: identity-preserve
Asset type: portrait retouch
Primary request: 只把背景换成干净白墙
Input images: Image 1: edit target
Constraints: keep the same person, face, pose, clothing, and framing; change only the background to a clean white studio wall with even soft light; do not restyle the subject

User: 可回收火箭海报，大标题「冲破边界」
Use case: ads-marketing
Asset type: tall campaign poster
Primary request: reusable rocket launch and ocean recovery, headline 冲破边界
Scene/backdrop: two-moment poster; upper two-thirds a white-and-blue reusable rocket climbs diagonally through storm cloud into near-space; a curved earth limb splits the frame; lower third the first stage lands at night on a lit ocean pad
Subject: one technically credible reusable orbital vehicle and its recovered first stage, no logos
Style/medium: cinematic photoreal aerospace key visual
Composition/framing: tall portrait; reserved deep-navy negative space at top left for type
Lighting/mood: bright exhaust against indigo space, cyan rim, molten-orange plume
Color palette: midnight navy, cobalt, cyan, white, molten orange
Materials/textures: ceramic-white skin, grid fins, condensation, turbulent cloud, ocean reflections
Text (verbatim): "冲破边界"
Typography: large white Simplified Chinese headline, bold contemporary sans, top left, fully inside the canvas
Constraints: immediately readable story of launch plus recovery; no other words
Avoid: extra rockets, astronauts, flags, logos, watermarks, distorted Chinese, science-fiction fantasy hardware
""".strip(),
}

PROFILE_SPECS: Dict[str, Dict[str, Any]] = {
    "cover": {
        "label": "editorial cover",
        "constraints": (
            "text-free cover artwork with a single clear subject",
            "generous negative space and a readable hierarchy at small size",
            "no text, letters, logos, watermarks, or UI chrome",
            "no extra people or brands the user did not name",
        ),
        "template": (
            "Use case: editorial cover\n"
            "Asset type: text-free cover artwork, {aspect}\n"
            "Primary request: {prompt}\n"
            "Composition: clear subject hierarchy, generous negative space\n"
            "Lighting/mood: controlled, confident, not neon\n"
            "Constraints: no text, no letters, no logos, no watermarks, no UI chrome\n"
            "Avoid: clutter, generic blue SaaS gradients, extra people or brands not named"
        ),
    },
    "poster": {
        "label": "campaign poster background",
        "constraints": (
            "text-free campaign key art with room for later typography",
            "wide, uncluttered negative space on one side",
            "no text, letters, logos, watermarks, or interface labels",
            "no recognizable third-party marks",
        ),
        "template": (
            "Use case: ads-marketing\n"
            "Asset type: text-free poster background, {aspect}\n"
            "Primary request: {prompt}\n"
            "Composition: strong focal point, quiet negative space reserved for type\n"
            "Style/medium: refined cinematic editorial key art\n"
            "Constraints: absolutely no text, letters, logos, or watermarks\n"
            "Avoid: busy dashboards, tiny UI, cyberpunk neon overload"
        ),
    },
    "portrait": {
        "label": "portrait",
        "constraints": (
            "one subject, identity-preserving if a reference is present",
            "clean portrait lighting and an uncluttered backdrop",
            "no extra people, no text, no logos",
        ),
        "template": (
            "Use case: portrait\n"
            "Asset type: single-subject portrait, {aspect}\n"
            "Primary request: {prompt}\n"
            "Composition: subject sharp and centered enough to read the face\n"
            "Lighting/mood: controlled portrait light, believable skin and fabric\n"
            "Constraints: one subject, no extra people, no text, no logos\n"
            "Avoid: beauty-filter plastic skin, collage, watermark"
        ),
    },
    "product": {
        "label": "product still",
        "constraints": (
            "catalog-true materials and silhouette",
            "clean still-life lighting, uncluttered surface",
            "no extra logos, slogans, or invented packaging copy",
        ),
        "template": (
            "Use case: product still life\n"
            "Asset type: clean product photograph or studio render, {aspect}\n"
            "Primary request: {prompt}\n"
            "Composition: product as hero, simple surface, shallow uncluttered scene\n"
            "Constraints: accurate materials, no extra logos, no slogans, no text\n"
            "Avoid: lifestyle crowds, fake brand marks, busy props"
        ),
    },
    "edit": {
        "label": "source-image edit",
        "constraints": (
            "keep identity, pose, and composition unless the user asked to change them",
            "change only what the user named",
            "do not restyle the whole image unless asked",
        ),
        "template": (
            "Use case: precise-object-edit\n"
            "Asset type: source-image edit\n"
            "Primary request: {prompt}\n"
            "Input images: Image 1: edit target\n"
            "Constraints: keep identity, pose, framing, and unmentioned details; "
            "change only what the request names; do not restyle the whole image"
        ),
    },
}

PROFILE_PROSE: Dict[str, str] = {
    "cover": (
        "{prompt}. {aspect} editorial cover with one clear subject and generous "
        "negative space, controlled lighting. No text, letters, logos, watermarks, or UI chrome."
    ),
    "poster": (
        "{prompt}. {aspect} campaign key art with quiet negative space for later type, "
        "refined cinematic editorial look. No text, letters, logos, or watermarks."
    ),
    "portrait": (
        "{prompt}. {aspect} single-subject portrait, face readable, uncluttered backdrop, "
        "controlled portrait light. No extra people, no text, no logos."
    ),
    "product": (
        "{prompt}. {aspect} product still, accurate materials, simple surface. "
        "No extra logos, slogans, or text."
    ),
    "edit": (
        "{prompt}. Keep identity, pose, framing, and unmentioned details. "
        "Change only what the request names. Do not restyle the whole image."
    ),
}


class PromptCompileResult:
    """Public prompt metadata attached to every CLI JSON result."""

    def __init__(
        self,
        original: str,
        used: str,
        *,
        profile: Optional[str] = None,
        optimize_mode: str = "off",
        applied: bool = False,
        skipped_reason: Optional[str] = None,
        family: Optional[str] = None,
        text_model: Optional[str] = None,
        text_provider: Optional[str] = None,
        source_format: Optional[str] = None,
        adapt_reason: Optional[str] = None,
        notes: Optional[Sequence[str]] = None,
    ) -> None:
        self.original = original
        self.used = used
        self.profile = profile
        self.optimize_mode = optimize_mode
        self.applied = applied
        self.skipped_reason = skipped_reason
        self.family = family
        self.text_model = text_model
        self.text_provider = text_provider
        self.source_format = source_format
        self.adapt_reason = adapt_reason
        self.notes = [item for item in (notes or []) if item]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "used": self.used,
            "profile": self.profile,
            "optimize": {
                "mode": self.optimize_mode,
                "applied": self.applied,
                "skipped_reason": self.skipped_reason,
                "family": self.family,
                "source_format": self.source_format,
                "adapt_reason": self.adapt_reason,
                "text_model": self.text_model,
                "text_provider": self.text_provider,
            },
        }


def prompt_family(provider: str) -> str:
    return PROVIDER_FAMILY.get(provider, "imagine")


def text_vendor(vendor_or_family: str) -> str:
    return FAMILY_TO_TEXT_VENDOR.get(vendor_or_family, vendor_or_family)


def default_text_model(
    vendor_or_family: str,
    override: Optional[str] = None,
    *,
    allow_override: bool = True,
) -> str:
    vendor = text_vendor(vendor_or_family)
    if allow_override and override and override.strip():
        return override.strip()
    env_name = VENDOR_TEXT_MODEL_ENV.get(vendor)
    if env_name:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            return env_value
    global_override = os.environ.get("LOCAL_IMAGE_GEN_OPTIMIZE_MODEL", "").strip()
    if allow_override and global_override:
        return global_override
    return VENDOR_TEXT_MODELS.get(vendor, "grok-4.6")


def preferred_text_backends(family: str) -> Tuple[str, ...]:
    return FAMILY_TEXT_BACKENDS.get(family, ("grok", "openai", "gemini"))


def is_generic_prompt(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    compact = " ".join(stripped.split())
    lower = compact.lower()
    if any(marker in lower or marker in compact for marker in STRUCTURED_MARKERS):
        return False
    if stripped.count("\n") >= 2:
        return False
    clauses = [part for part in re.split(r"[。！？.!?]+", compact) if part.strip()]
    if len(clauses) >= 2:
        return False
    return len(compact) <= GENERIC_MAX_CHARS


def _label_hits(text: str) -> int:
    compact = " ".join((text or "").split())
    lower = compact.lower()
    return sum(1 for marker in GPT_IMAGE_LABELS if marker in lower or marker in compact)


def detect_prompt_format(text: str) -> str:
    """Classify an incoming prompt as gpt_image labels, unlabeled prose, or unknown."""
    stripped = (text or "").strip()
    if not stripped:
        return "unknown"
    hits = _label_hits(stripped)
    if hits >= 2:
        return "gpt_image"
    strong = (
        "use case:",
        "asset type:",
        "primary request:",
        "用途：",
        "用途:",
        "资产类型：",
        "资产类型:",
    )
    compact = " ".join(stripped.split())
    lower = compact.lower()
    if hits == 1 and any(marker in lower or marker in compact for marker in strong):
        return "gpt_image"
    clauses = [part for part in re.split(r"[。！？.!?]+", compact) if part.strip()]
    if len(clauses) >= 2 or stripped.count("\n") >= 2 or len(compact) > GENERIC_MAX_CHARS:
        return "prose"
    return "unknown"


def format_mismatches_family(fmt: str, family: str) -> bool:
    """Hard mismatch only: labeled spec vs Imagine/Nano Banana, or prose vs gpt-image-2.

    Imagine and Nano Banana are both prose, so auto does not rewrite one into the
    other. Use --optimize on to force that craft change.
    """
    if fmt == "unknown":
        return False
    if family == "gpt_image":
        return fmt == "prose"
    return fmt == "gpt_image"


def decide_optimize(
    mode: str,
    prompt: str,
    *,
    raw: bool,
    from_file: bool,
    provider: str,
) -> Tuple[bool, Optional[str]]:
    family = prompt_family(provider)
    mismatch = format_mismatches_family(detect_prompt_format(prompt), family)
    if raw:
        return False, "raw"
    if mode not in OPTIMIZE_MODES:
        return False, "off"
    if mode == "off":
        return False, "off"
    if provider == "codex":
        return False, "codex_response_model"
    if mode == "on":
        return True, "family_mismatch" if mismatch else None
    if mismatch:
        return True, "family_mismatch"
    if from_file:
        return False, "prompt_file"
    if not is_generic_prompt(prompt):
        return False, "already_specific"
    return True, None


def apply_profile(
    prompt: str,
    profile: str,
    *,
    aspect: Optional[str] = None,
    family: Optional[str] = None,
) -> str:
    spec = PROFILE_SPECS.get(profile)
    if spec is None:
        raise ValueError(f"Unknown prompt profile: {profile}")
    composition = aspect_to_composition(aspect)
    if family in {"imagine", "nano_banana"}:
        prose = PROFILE_PROSE.get(profile) or str(spec["template"])
        return prose.format(prompt=prompt.strip(), aspect=composition)
    return str(spec["template"]).format(
        prompt=prompt.strip(),
        aspect=composition,
    )


def profile_constraints(profile: Optional[str]) -> Tuple[str, ...]:
    if not profile:
        return ()
    spec = PROFILE_SPECS.get(profile) or {}
    return tuple(spec.get("constraints") or ())


def compiler_system_prompt(family: str) -> str:
    extra = FAMILY_COMPILER_RULES.get(family, FAMILY_COMPILER_RULES["imagine"])
    examples = COMPILER_EXAMPLES.get(family, COMPILER_EXAMPLES["imagine"])
    scaffold = FAMILY_SCAFFOLDS.get(family, IMAGINE_SCAFFOLD)
    return f"{_SHARED_COMPILER_RULES}\n\n{scaffold}\n\n{extra}\n\n{examples}"


def aspect_to_composition(aspect: Optional[str]) -> str:
    if not aspect:
        return "unspecified"
    mapping = {
        "1:1": "square frame",
        "16:9": "wide landscape",
        "2:1": "very wide landscape",
        "9:16": "tall portrait",
        "1:2": "very tall portrait",
        "4:3": "horizontal photo",
        "3:2": "horizontal photo",
        "3:4": "vertical photo",
        "2:3": "vertical photo",
    }
    return mapping.get(aspect, aspect)


def build_optimize_user_message(
    prompt: str,
    *,
    family: str,
    edit: bool,
    aspect: Optional[str],
    profile: Optional[str],
    image_count: int,
) -> str:
    source_format = detect_prompt_format(prompt)
    remapping = format_mismatches_family(source_format, family)
    lines = [
        f"Image model family: {family}",
        f"Mode: {'edit' if edit or image_count else 'generate'}",
        f"Composition: {aspect_to_composition(aspect)}",
        f"Reference images: {image_count}",
        f"Incoming prompt format: {source_format}",
    ]
    if remapping:
        lines.append(
            "Family remapping: rewrite this finished prompt into the target "
            "family's craft. Keep subject, visible text, constraints, and "
            "language. Do not add a new story."
        )
    if profile:
        spec = PROFILE_SPECS.get(profile) or {}
        lines.append(f"Required asset profile: {spec.get('label', profile)}")
        for item in spec.get("constraints") or ():
            lines.append(f"- {item}")
    if image_count:
        lines.append(
            "This is an edit or reference-guided request. Image 1 is the source "
            "unless the user assigned roles. Name what stays and what changes."
        )
    lines.append("")
    lines.append("User request:")
    lines.append(prompt.strip())
    if family == "gpt_image":
        lines.append("Emit filled scaffold lines only. Do not write a prose paragraph.")
    elif family == "nano_banana":
        lines.append(
            "Emit a Nano Banana director brief. No scaffold labels. "
            "Start generates with a strong verb."
        )
    else:
        lines.append(
            "Emit 2-5 Imagine prose sentences. Front-load the subject. "
            "Do not print scaffold labels."
        )
    lines.append("")
    lines.append("Compile the final image prompt now.")
    return "\n".join(lines)


def build_optimize_messages(
    prompt: str,
    *,
    family: str,
    edit: bool,
    aspect: Optional[str],
    profile: Optional[str],
    image_count: int,
) -> Tuple[str, str]:
    return (
        compiler_system_prompt(family),
        build_optimize_user_message(
            prompt,
            family=family,
            edit=edit,
            aspect=aspect,
            profile=profile,
            image_count=image_count,
        ),
    )


def looks_like_refusal(text: str) -> bool:
    lower = text.strip().lower()
    return any(marker in lower for marker in REFUSAL_MARKERS)


def sanitize_optimized_prompt(text: str) -> Optional[str]:
    if not text or not str(text).strip():
        return None
    out = str(text).strip()
    if out.startswith("```"):
        out = re.sub(r"^```(?:[A-Za-z0-9_-]+)?\s*", "", out)
        out = re.sub(r"\s*```$", "", out)
        out = out.strip()
    if len(out) >= 2 and (
        (out[0] == out[-1] and out[0] in {'"', "'"})
        or (out.startswith("“") and out.endswith("”"))
        or (out.startswith("「") and out.endswith("」"))
    ):
        out = out[1:-1].strip()
    out = re.sub(r"^(?:final\s+)?prompt\s*[:：]\s*", "", out, flags=re.IGNORECASE).strip()
    if len(out) < 8:
        return None
    if looks_like_refusal(out):
        return None
    if len(out) > 2500:
        trimmed = out[:2500]
        cut = trimmed.rsplit(" ", 1)[0]
        out = cut if len(cut) >= 80 else trimmed
    return out


def fallback_prompt(
    original: str,
    profile: Optional[str],
    aspect: Optional[str],
    family: Optional[str] = None,
) -> str:
    if profile:
        return apply_profile(original, profile, aspect=aspect, family=family)
    return original
