# Prompt contract

The executable rules live in `scripts/prompt_compile.py`. This page is the agent-facing summary.

`local-image-gen` is a transport layer. Image quality is usually decided by the **last prompt the image model sees**, not by which backend you picked. Each family has its own official writing craft. The CLI will not silently rewrite you. It will compile when you ask, and it will re-adapt when you switch families.

## Who writes the prompt

| Situation | What to do |
| --- | --- |
| User wrote a detailed prompt, or said verbatim / 原文 / `--raw` | Send it unchanged |
| User wrote a short or generic request | Expand it yourself from the **target family** section below, **or** pass `--optimize auto` |
| User named an asset type (`cover`, poster, portrait, product) | `--prompt-profile` and/or `--optimize auto` |
| Edit / reference image (`-i`) | Name what stays and what changes. Do not restyle the whole frame |
| You already expanded the prompt **for this family** | Do **not** also pass `--optimize on` |
| Previous result was for another family; user wants to retry here | Re-adapt. `--optimize auto` detects labeled `$imagegen` vs prose and remaps. Imagine ↔ Nano Banana are both prose — pass `--optimize on` to force that craft change |

`--optimize` is default `off`. `auto` rewrites:

- short, unstructured prompts: one clause, at most 180 characters, no labeled fields, not a `--prompt-file`
- **or** a finished prompt whose format belongs to a different family (gpt-image-2 labels on Grok/agy, or Imagine/Nano Banana prose on official OpenAI)

Two or more sentence terminators (`。！？.!?`) count as already specific **for the same family**. It never runs on `--provider codex` (that path already has a response model in the loop) and never launches `agy`, `cursor-agent`, or Codex as an agent.

`--raw` and `--optimize off` always send the text as-is, even after a family switch.

## Shared invariants

These are CLI safety rules, not a shared thinking scaffold:

- Same language as the user.
- Detailed user prompts: normalize, do not add a story.
- Family remaps keep subject, visible text, and constraints. They change craft only.
- Do not invent brands, slogans, celebrities, extra people, or objects.
- No Midjourney / SD tag soup (`masterpiece`, `8k`, `1girl`, `--ar`).
- Aspect as composition words (`wide landscape`, `tall portrait`, `square`). Never `16:9` in the prompt.
- Distinct assets are separate CLI calls.

Grok Imagine API and Antigravity/Cursor workers do not rewrite on the CLI path — they paint whatever you (or `--optimize`) send.

## Imagine (Grok, xAI)

Official craft: Grok Build `imagine` skill.

Think: **subject → action/pose → setting → style → composition → lighting/mood → one key detail**. Skip empty beats. Do not over-specify.

Emit 2–5 cinematic sentences. Front-load the subject. Positive. One coherent scene. **Do not print labels** — Imagine sometimes paints `Use case:`.

```text
雪林里一只停住的水彩狐狸，锈红皮毛衬着淡蓝阴影。纸面带着水渍边，细长松干和落雪，偏低的侧向取景。没有文字、字母、标志或水印。
```

Edits: desired end state plus what must stay identical.

## gpt-image-2 (official OpenAI; Codex `$imagegen` in a live Codex session)

Official craft: Codex `$imagegen` labeled spec.

Think and emit filled labeled lines. Skip empty slots. Keep English labels; write values in the user's language. For campaigns, write `Scene/backdrop` as a spatial story, reserve type area in `Composition`, and treat on-image copy as `Text` + `Typography`. `Avoid` is this job's failure modes, not quality-tag soup.

```text
Use case: ads-marketing
Asset type: tall campaign poster
Primary request: reusable rocket launch and ocean recovery
Scene/backdrop: two-moment poster; rocket climbs through storm cloud; first stage lands on a night ocean pad
Subject: one reusable orbital vehicle and its recovered first stage
Style/medium: cinematic photoreal aerospace key visual
Composition/framing: tall portrait; deep-navy negative space at top left for type
Lighting/mood: bright exhaust against indigo space
Color palette: midnight navy, cobalt, cyan, white, molten orange
Materials/textures: ceramic-white skin, grid fins, ocean reflections
Text (verbatim): "冲破边界"
Typography: large white Simplified Chinese headline, bold sans, top left, fully inside the canvas
Constraints: readable story of launch plus recovery; no other words
Avoid: extra rockets, flags, logos, watermarks, distorted Chinese
```

CLI `--provider codex` skips `--optimize` because the unofficial Responses path already has a controller. That path is not the Codex `$imagegen` skill.

## Nano Banana (agy, Cursor, Gemini)

Official craft: Google's Nano Banana prompting guide.

Think: **[Subject] + [Action] + [Location] + [Composition] + [Style]**. With references: **[relationship] + [new scenario]**.

Emit a director brief. Start generates with a strong verb (`创建` / `Create` / `Present` / `Using`). Concrete materials, wardrobe, surfaces, camera, lighting. Positive framing. If there is on-image text, put the exact words in quotes and name the type style. Denser than Imagine is OK. **Do not print `$imagegen` labels.**

```text
创建一幅雪林水彩：一只锈红狐狸停在细长松干边，淡蓝阴影，纸面水渍边清晰可见。偏低侧向中景，冷日光，落雪很轻。画面里不要文字、字母、标志或水印。
```

## Edit

Name what stays and what changes. Image 1 is the source unless the user assigned roles.

```text
Keep the same person, face, pose, clothing, and camera framing. Replace only the
background with a clean white studio wall and soft even light. Do not restyle
the subject or change their identity.
```

## Switching families

Same intent, different painter. Re-adapt the **last prompt the previous model saw** (`prompt.used` in the JSON), not a new story.

| From → To | `auto` | `on` | `off` / `--raw` |
| --- | --- | --- | --- |
| `$imagegen` labels → Grok / agy / Cursor / Gemini | Remap to that family's prose | Remap | Send labels unchanged (Imagine may paint them) |
| Imagine / Nano Banana prose → official OpenAI | Remap to labeled `$imagegen` | Remap | Send prose unchanged |
| Imagine prose → Nano Banana, or the reverse | Keep (both are prose) | Force the target craft | Unchanged |
| Any → `--provider codex` | Skip compile | Skip compile | Unchanged |

JSON `prompt.optimize` includes `family`, `source_format` (`gpt_image` / `prose` / `unknown`), and `adapt_reason` (`family_mismatch` when auto/on remapped).

Do not translate a Chinese request into English unless the user asked.

## CLI flags

| Flag | Effect |
| --- | --- |
| `--raw` | Verbatim. Wins over profile and optimize |
| `--prompt-profile cover\|poster\|portrait\|product\|edit` | Deterministic wrap. Labeled for gpt-image-2; prose for Grok/agy |
| `--optimize off\|on\|auto` | Target-family compiler, frozen system prompt, no tools. Default `off` |
| `--optimize-model` | Override the compiler text model |
| `--prompt-file` | `auto` will not rewrite a same-family file the user already wrote. A **wrong-family** file is remapped |

The JSON result always includes `prompt.original`, `prompt.used`, and `prompt.optimize`. `--dry-run` with `--optimize on|auto` may call the **text** model so you can inspect `prompt.used` without spending an image.

Compiler text models (override with env or `--optimize-model`):

| Family | Default | Env |
| --- | --- | --- |
| Imagine | `grok-4.6` | `LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_GROK` |
| gpt-image-2 | `gpt-5.6-terra` | `LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_OPENAI` |
| Nano Banana | `gemini-2.5-flash` | `LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_GEMINI` |

Same-family first: Grok login / `XAI_API_KEY`, then `OPENAI_API_KEY`, then `GEMINI_API_KEY`. Each vendor keeps its own text model (`grok-4.6`, `gpt-5.6-terra`, `gemini-2.5-flash`). Terra is the default OpenAI compiler: structured rewrites do not need Sol. Override with `LOCAL_IMAGE_GEN_OPTIMIZE_MODEL_OPENAI=gpt-5.6` / `gpt-5.6-sol` for harder edits, or `gpt-5.6-luna` for cheaper bulk drafts. The compiler sends `reasoning_effort=low` for `gpt-5.6*`. `auto` skips if no text backend is available. `on` may fall back to another official text backend and says so in `prompt.optimize`. A failed Grok login refresh is “Grok text unavailable”, not a hard job death. Images are never uploaded to the compiler.

When `-o` is omitted, the default filename hash is of `prompt.original`, not the compiled text.

## Profiles

`--prompt-profile` only wraps. It does not invent a subject.

| Profile | For | Locked constraints |
| --- | --- | --- |
| `cover` | course / book / thumbnail covers | text-free, hierarchy, negative space |
| `poster` | campaign key art | text-free, room for later type |
| `portrait` | one person | one subject, no extra people |
| `product` | catalog stills | accurate materials, no fake marks |
| `edit` | any `-i` change | keep identity/pose/framing; change only what was named |

Profiles stay text-free on purpose. gpt-image-2 can render Chinese when the user (or `--optimize`) supplies `Text` + `Typography`; Grok / agy CLI paths are less reliable at on-image type, so the profile still leaves type for later.

When `--optimize` also runs, the profile becomes compiler constraints instead of a second wrap.

## What not to do

- Do not default `--optimize on` for every call.
- Do not optimize a prompt you already expanded for the **same** family.
- Do not send a previous family's finished prompt to a new painter without remapping (`auto` or `on`).
- Do not use coding-agent CLIs as a second prompt writer.
- Do not put inpaint instructions in the prompt and skip `--mask` on OpenAI. `--mask` is official Images edits only.
