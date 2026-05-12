from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import DESIGN_SESSION_DIR, DESIGN_WORKSPACE_DIR, Settings
from app.llama_client import LlamaClient
from app.storage import Storage


class DesignStudioService:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self.llama = LlamaClient(settings)

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.storage.list_design_sessions()

    def create_session(self, name: str, brief: str, language: str) -> dict[str, Any]:
        slug = self._slugify(name)
        suffix = uuid.uuid4().hex[:8]
        workspace = DESIGN_WORKSPACE_DIR / f"{slug}-{suffix}"
        artifacts_dir = workspace / "artifacts"
        workspace.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        design_spec_path = workspace / "DESIGN.md"
        brief_path = workspace / "brief.md"
        design_spec_path.write_text(self._default_design_spec(name, brief, language), encoding="utf-8")
        brief_path.write_text(brief.strip() + "\n", encoding="utf-8")

        session = self.storage.create_design_session(
            name=name,
            brief=brief,
            language=language,
            workspace_path=str(workspace),
            design_spec_path=str(design_spec_path),
        )
        payload = {
            "name": name,
            "language": language,
            "workspace_path": str(workspace),
            "design_spec_path": str(design_spec_path),
            "brief_path": str(brief_path),
        }
        self.storage.add_design_event(session["id"], "session_created", payload)
        self._append_session_log(session["id"], "session_created", payload)
        return session

    def session_detail(self, session_id: str) -> dict[str, Any]:
        session = self.storage.get_design_session(session_id)
        if not session:
            raise KeyError("Design session not found")
        session["artifacts"] = self.storage.list_design_artifacts(session_id)
        session["events"] = self.storage.list_design_events(session_id)
        return session

    def advisor(self, session_id: str, goal: str) -> dict[str, Any]:
        session = self.storage.get_design_session(session_id)
        if not session:
            raise KeyError("Design session not found")

        effective_goal = (goal or "").strip() or session["brief"]
        warning = None
        raw_output = ""

        try:
            raw_output = self.llama.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are Huashu Local Advisor. "
                            "Return exactly one JSON object with keys: summary, directions. "
                            "directions must be an array of exactly 3 objects with keys "
                            "name, philosophy, palette, typography, rationale, scene_focus. "
                            "Each direction must be clearly different. "
                            "When user language is Chinese, write Traditional Chinese."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Design brief:\n"
                            f"{session['brief']}\n\n"
                            "Current goal:\n"
                            f"{effective_goal}\n\n"
                            "Constraints:\n"
                            "- local-first deliverable\n"
                            "- avoid generic AI slop defaults\n"
                            "- include color palette in hex strings\n"
                            "- each direction should map to one primary scene focus"
                        ),
                    },
                ],
                temperature=0.45,
            )
            parsed = self._parse_json_object(raw_output)
            directions = self._normalize_directions(parsed.get("directions", []))
            summary = str(parsed.get("summary", "")).strip()
            if not summary:
                summary = "已產出 3 個差異化設計方向，建議先選 1 個方向再進入產物生成。"
        except Exception as exc:  # noqa: BLE001
            warning = f"方向顧問暫時無法呼叫模型，已改用本地 fallback。錯誤：{exc}"
            directions = self._fallback_directions(effective_goal)
            summary = "使用本地 fallback 產出 3 個方向，仍可直接生成原型並再迭代。"

        payload = {
            "goal": effective_goal,
            "summary": summary,
            "directions": directions,
            "warning": warning,
            "raw_output": raw_output[:4000],
        }
        self.storage.add_design_event(session_id, "advisor", payload)
        self._append_session_log(session_id, "advisor", payload)
        return {
            "summary": summary,
            "directions": directions,
            "warning": warning,
        }

    def generate_artifact(
        self,
        session_id: str,
        artifact_type: str,
        direction_name: str,
        requirements: str,
    ) -> dict[str, Any]:
        session = self.storage.get_design_session(session_id)
        if not session:
            raise KeyError("Design session not found")

        workspace = Path(session["workspace_path"])
        artifacts_dir = workspace / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        spec_path = Path(session["design_spec_path"])
        design_spec = spec_path.read_text(encoding="utf-8", errors="ignore")[:8000] if spec_path.exists() else ""

        warning = None
        html = ""
        try:
            fallback = self._fallback_html(session, artifact_type, direction_name, requirements)
            html = self._generate_html_with_llm(
                session=session,
                artifact_type=artifact_type,
                direction_name=direction_name,
                requirements=requirements,
                design_spec=design_spec,
            )
            html = self._extract_html_document(html, fallback)
        except Exception as exc:  # noqa: BLE001
            warning = f"模型生成失敗，已使用本地模板。錯誤：{exc}"
            html = self._fallback_html(session, artifact_type, direction_name, requirements)

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        title = f"{artifact_type}-{timestamp}"
        file_path = artifacts_dir / f"{title}.html"
        file_path.write_text(html, encoding="utf-8")

        preview_text = self._preview_text(html)
        metadata = {
            "direction_name": direction_name,
            "requirements": requirements,
            "language": session["language"],
            "warning": warning,
            "mode": artifact_type,
            "generator": "llama.cpp" if warning is None else "local-template",
        }
        artifact = self.storage.add_design_artifact(
            session_id=session_id,
            artifact_type=artifact_type,
            title=title,
            file_path=str(file_path),
            preview_text=preview_text,
            metadata=metadata,
        )

        payload = {
            "artifact_id": artifact["id"],
            "artifact_type": artifact_type,
            "title": title,
            "file_path": str(file_path),
            "warning": warning,
        }
        self.storage.add_design_event(session_id, "artifact_generated", payload)
        self._append_session_log(session_id, "artifact_generated", payload)

        return {
            **artifact,
            "warning": warning,
        }

    def critique_artifact(self, session_id: str, artifact_id: str, focus: str) -> dict[str, Any]:
        artifact = self.storage.get_design_artifact(artifact_id)
        if not artifact or artifact["session_id"] != session_id:
            raise KeyError("Artifact not found")

        html_path = Path(artifact["file_path"])
        if not html_path.exists():
            raise FileNotFoundError("Artifact file not found on disk")

        html_content = html_path.read_text(encoding="utf-8", errors="ignore")
        snippet = html_content[:16000]
        warning = None

        try:
            raw = self.llama.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a design reviewer. Return exactly one JSON object with keys: "
                            "overview, dimensions, keep, fix, quick_wins. "
                            "dimensions is an array of 5 objects: name, score(0-10), note. "
                            "The five names must be: 哲學一致性, 視覺層級, 細節執行, 功能性, 創新性. "
                            "When context is Chinese, write Traditional Chinese."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Review focus: {(focus or '整體品質')}\n\n"
                            "Artifact HTML snippet:\n"
                            f"{snippet}"
                        ),
                    },
                ],
                temperature=0.2,
            )
            critique = self._parse_json_object(raw)
            normalized = self._normalize_critique(critique)
        except Exception as exc:  # noqa: BLE001
            warning = f"評審模型呼叫失敗，已使用本地規則評估。錯誤：{exc}"
            normalized = self._fallback_critique(html_content)

        payload = {
            "artifact_id": artifact_id,
            "focus": focus,
            "result": normalized,
            "warning": warning,
        }
        self.storage.add_design_event(session_id, "artifact_critique", payload)
        self._append_session_log(session_id, "artifact_critique", payload)
        return {
            **normalized,
            "warning": warning,
        }

    def apply_tweaks(self, session_id: str, artifact_id: str, values: dict[str, str]) -> dict[str, Any]:
        artifact = self.storage.get_design_artifact(artifact_id)
        if not artifact or artifact["session_id"] != session_id:
            raise KeyError("Artifact not found")

        file_path = Path(artifact["file_path"])
        if not file_path.exists():
            raise FileNotFoundError("Artifact file not found on disk")

        original = file_path.read_text(encoding="utf-8", errors="ignore")
        updated, applied = self._update_editmode_block(original, values)
        if not applied:
            raise ValueError("This artifact has no editable EDITMODE keys to update")

        file_path.write_text(updated, encoding="utf-8")

        metadata = {
            **artifact.get("metadata", {}),
            "last_tweaks": applied,
            "last_tweaked_at": datetime.now(UTC).isoformat(),
        }
        preview_text = self._preview_text(updated)
        self.storage.update_design_artifact(artifact_id, preview_text=preview_text, metadata=metadata)

        payload = {
            "artifact_id": artifact_id,
            "applied": applied,
        }
        self.storage.add_design_event(session_id, "artifact_tweaked", payload)
        self._append_session_log(session_id, "artifact_tweaked", payload)

        refreshed = self.storage.get_design_artifact(artifact_id)
        if refreshed is None:
            raise RuntimeError("Artifact disappeared after tweak update")
        return refreshed

    def read_artifact_content(self, session_id: str, artifact_id: str) -> dict[str, Any]:
        artifact = self.storage.get_design_artifact(artifact_id)
        if not artifact or artifact["session_id"] != session_id:
            raise KeyError("Artifact not found")

        file_path = Path(artifact["file_path"])
        if not file_path.exists():
            raise FileNotFoundError("Artifact file not found on disk")

        return {
            "artifact": artifact,
            "content": file_path.read_text(encoding="utf-8", errors="ignore"),
        }

    def _generate_html_with_llm(
        self,
        session: dict[str, Any],
        artifact_type: str,
        direction_name: str,
        requirements: str,
        design_spec: str,
    ) -> str:
        mode_instruction = {
            "prototype": (
                "Build one interactive product prototype page with at least 3 stateful zones "
                "(tabs, cards, or flow steps) and visible interaction cues."
            ),
            "slides": (
                "Build a 16:9 HTML slide deck scene with 5 slide sections in one document. "
                "Add keyboard navigation logic for left/right." 
            ),
            "motion": (
                "Build an animation scene that can loop continuously (about 18-25 seconds feeling), "
                "using CSS/JS timeline-style choreography."
            ),
            "infographic": (
                "Build a data-rich infographic page with at least one SVG chart and one ranked list."
            ),
        }[artifact_type]

        user_language = "Traditional Chinese" if "zh" in session["language"].lower() else "English"

        response = self.llama.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are Huashu Local Designer implemented in Python local-first stack. "
                        "Output only one complete HTML document. No markdown fence. "
                        "No external CDN/script/image. "
                        "Use distinctive typography and avoid generic AI slop defaults. "
                        "Include :root design tokens and one EDITMODE block with 4-8 keys in a <script> using markers "
                        "/*EDITMODE-BEGIN*/ and /*EDITMODE-END*/. "
                        "Apply EDITMODE keys to CSS variables on load and listen to "
                        "window.postMessage({type:'__edit_mode_set_keys', edits:{...}})."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Language: {user_language}\n"
                        f"Brief: {session['brief']}\n"
                        f"Direction: {direction_name or 'auto'}\n"
                        f"Extra requirements: {requirements or 'none'}\n"
                        f"Artifact type: {artifact_type}\n"
                        f"Mode instruction: {mode_instruction}\n\n"
                        "DESIGN.md excerpt:\n"
                        f"{design_spec}\n\n"
                        "Hard constraints:\n"
                        "1) responsive on desktop and mobile\n"
                        "2) meaningful motion with prefers-reduced-motion fallback\n"
                        "3) include obvious headline, core content, and call-to-action\n"
                        "4) keep document self-contained"
                    ),
                },
            ],
            temperature=0.6,
        )
        return response

    def _extract_html_document(self, content: str, fallback_html: str) -> str:
        text = content.strip()
        fenced = re.search(r"```html\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()

        if "<html" not in text.lower():
            return fallback_html
        return text

    def _fallback_html(
        self,
        session: dict[str, Any],
        artifact_type: str,
        direction_name: str,
        requirements: str,
    ) -> str:
        brief = (session.get("brief") or "設計任務").strip()
        language = session.get("language", "zh-Hant")
        is_zh = "zh" in language.lower()

        mode_block = {
            "prototype": "<button class='chip' data-tab='flow'>Flow</button><button class='chip' data-tab='states'>States</button><button class='chip' data-tab='cta'>CTA</button>",
            "slides": "<div class='slide'>01 Problem</div><div class='slide'>02 Insight</div><div class='slide'>03 Solution</div><div class='slide'>04 Evidence</div><div class='slide'>05 Ask</div>",
            "motion": "<div class='orb one'></div><div class='orb two'></div><div class='orb three'></div>",
            "infographic": "<svg viewBox='0 0 420 210' class='chart'><rect x='40' y='120' width='56' height='70'></rect><rect x='130' y='95' width='56' height='95'></rect><rect x='220' y='70' width='56' height='120'></rect><rect x='310' y='42' width='56' height='148'></rect></svg>",
        }[artifact_type]

        zh_title = {
            "prototype": "互動原型",
            "slides": "簡報草案",
            "motion": "動態場景",
            "infographic": "資訊圖表",
        }[artifact_type]

        en_title = {
            "prototype": "Interactive Prototype",
            "slides": "Slide Draft",
            "motion": "Motion Scene",
            "infographic": "Infographic",
        }[artifact_type]

        title = zh_title if is_zh else en_title
        heading = f"{title} · {direction_name or ('本地預設方向' if is_zh else 'Local fallback direction')}"
        subtitle = brief if is_zh else brief
        requirement_line = requirements.strip() or ("可再補充細節需求" if is_zh else "Add detailed requirements next")

        return f"""<!doctype html>
<html lang=\"{'zh-Hant' if is_zh else 'en'}\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f6f1e8;
      --surface: #fff8ef;
      --ink: #191613;
      --muted: #62564b;
      --accent: #c4491d;
      --radius: 18px;
      --space: 16px;
      --display: 'Georgia', 'Times New Roman', serif;
      --body: 'Aptos', 'Segoe UI', sans-serif;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: var(--body);
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 10%, rgba(196, 73, 29, 0.18), transparent 36%),
        radial-gradient(circle at 85% 85%, rgba(39, 108, 120, 0.16), transparent 30%),
        var(--bg);
      padding: 20px;
    }}

    .frame {{
      max-width: 1120px;
      margin: 0 auto;
      background: var(--surface);
      border-radius: calc(var(--radius) + 6px);
      border: 1px solid rgba(25, 22, 19, 0.12);
      box-shadow: 0 24px 50px rgba(34, 28, 22, 0.1);
      padding: clamp(20px, 4vw, 40px);
    }}

    .eyebrow {{
      margin: 0;
      letter-spacing: 0.14em;
      color: var(--accent);
      font-size: 0.74rem;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 10px 0 8px;
      font-family: var(--display);
      font-size: clamp(1.8rem, 4vw, 3rem);
      line-height: 1.05;
    }}

    p {{ margin: 0; line-height: 1.7; color: var(--muted); }}

    .panel {{
      margin-top: calc(var(--space) * 1.3);
      border: 1px solid rgba(25, 22, 19, 0.1);
      border-radius: var(--radius);
      background: rgba(255, 255, 255, 0.62);
      padding: calc(var(--space) * 1.1);
      display: grid;
      gap: 10px;
    }}

    .chips {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .chip {{
      border: 0;
      border-radius: 999px;
      padding: 8px 14px;
      background: rgba(196, 73, 29, 0.13);
      color: var(--accent);
      font-weight: 600;
    }}

    .slide {{
      border: 1px dashed rgba(25, 22, 19, 0.2);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.66);
      margin-bottom: 10px;
    }}

    .chart rect {{ fill: var(--accent); opacity: 0.82; }}
    .orb {{ width: 84px; height: 84px; border-radius: 50%; background: var(--accent); opacity: 0.86; position: absolute; filter: blur(1px); }}
    .one {{ top: 12px; left: 8%; animation: drift 8s ease-in-out infinite; }}
    .two {{ top: 88px; left: 36%; animation: drift 11s ease-in-out infinite reverse; }}
    .three {{ top: 36px; right: 12%; animation: drift 9s ease-in-out infinite; }}

    @keyframes drift {{
      0%, 100% {{ transform: translateY(0) scale(1); }}
      50% {{ transform: translateY(32px) scale(1.12); }}
    }}

    @media (max-width: 780px) {{
      .frame {{ padding: 18px; }}
      .orb {{ position: static; display: inline-block; margin-right: 8px; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ animation: none !important; transition: none !important; }}
    }}
  </style>
</head>
<body>
  <main class=\"frame\">
    <p class=\"eyebrow\">Huashu Python Local</p>
    <h1>{heading}</h1>
    <p>{subtitle}</p>

    <section class=\"panel\">{mode_block}</section>

    <section class=\"panel\">
      <strong>{'待補需求' if is_zh else 'Pending requirements'}</strong>
      <p>{requirement_line}</p>
    </section>
  </main>

  <script>
  /*EDITMODE-BEGIN*/
  {{
    "bg": "#f6f1e8",
    "surface": "#fff8ef",
    "ink": "#191613",
    "accent": "#c4491d",
    "radius": "18px",
    "space": "16px"
  }}
  /*EDITMODE-END*/

  (function () {{
    const script = document.currentScript;
    const text = script ? script.textContent : "";
    const match = text ? text.match(/\\/\\*EDITMODE-BEGIN\\*\\/([\\s\\S]*?)\\/\\*EDITMODE-END\\*\\//) : null;
    const root = document.documentElement;

    function apply(edits) {{
      for (const [key, value] of Object.entries(edits || {{}})) {{
        root.style.setProperty("--" + key, String(value));
      }}
    }}

    if (match) {{
      try {{
        apply(JSON.parse(match[1]));
      }} catch (_error) {{
        // keep defaults
      }}
    }}

    window.addEventListener("message", (event) => {{
      if (!event.data || event.data.type !== "__edit_mode_set_keys") return;
      apply(event.data.edits || {{}});
    }});

    document.querySelectorAll("[data-tab]").forEach((button) => {{
      button.addEventListener("click", () => {{
        button.style.transform = "translateY(-1px)";
        setTimeout(() => {{
          button.style.transform = "";
        }}, 120);
      }});
    }});
  }})();
  </script>
</body>
</html>
"""

    @staticmethod
    def _preview_text(html: str) -> str:
        cleaned = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:360]

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
        return slug or "design-session"

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        candidate = raw.strip()
        fenced = re.search(r"```json\s*(.*?)```", candidate, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1).strip()

        first = candidate.find("{")
        last = candidate.rfind("}")
        if first == -1 or last == -1 or last <= first:
            raise ValueError("No JSON object found")

        payload = candidate[first : last + 1]
        return json.loads(payload)

    def _normalize_directions(self, directions: list[dict[str, Any]] | list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(directions[:3], start=1):
            if not isinstance(item, dict):
                continue
            palette = item.get("palette")
            if not isinstance(palette, list):
                palette = []
            normalized.append(
                {
                    "name": str(item.get("name") or f"Direction {index}").strip(),
                    "philosophy": str(item.get("philosophy") or "").strip(),
                    "palette": [str(color).strip() for color in palette if str(color).strip()][:6],
                    "typography": str(item.get("typography") or "").strip(),
                    "rationale": str(item.get("rationale") or "").strip(),
                    "scene_focus": str(item.get("scene_focus") or "").strip(),
                }
            )

        if len(normalized) == 3:
            return normalized
        return self._fallback_directions("")

    @staticmethod
    def _fallback_directions(goal: str) -> list[dict[str, Any]]:
        return [
            {
                "name": "資訊建築極簡",
                "philosophy": "以明確資訊層級和留白為主，先讓訊息可讀，再讓視覺出彩。",
                "palette": ["#F5F1E8", "#1B1714", "#C04E22", "#2F6F76"],
                "typography": "Display: Cormorant Garamond / Body: Noto Sans TC",
                "rationale": f"適合把『{goal or '主題'}』拆成可快速掃讀的內容塊。",
                "scene_focus": "重點訊息卡 + 穩定導覽節奏",
            },
            {
                "name": "動勢敘事",
                "philosophy": "用連續位移與節奏變化做敘事，讓重點在時間軸上被看見。",
                "palette": ["#101820", "#F2EEE6", "#E4632A", "#28A0A0"],
                "typography": "Display: Playfair Display / Body: Source Sans 3",
                "rationale": "適合需要 demo 感與提案張力的展示場景。",
                "scene_focus": "首屏吸睛動效 + 中段證據呈現 + 結尾 CTA",
            },
            {
                "name": "東方留白編排",
                "philosophy": "以留白、比例與克制色彩建立高質感，避免噪音。",
                "palette": ["#F7F3EA", "#23201C", "#8A2D1F", "#6E7E6B"],
                "typography": "Display: Noto Serif TC / Body: Noto Sans TC",
                "rationale": "適合教育、研究、知識型內容，閱讀壓力低。",
                "scene_focus": "單一主敘事 + 穩定排版網格",
            },
        ]

    def _normalize_critique(self, critique: dict[str, Any]) -> dict[str, Any]:
        dims = critique.get("dimensions")
        normalized_dims: list[dict[str, Any]] = []
        if isinstance(dims, list):
            for raw in dims[:5]:
                if not isinstance(raw, dict):
                    continue
                try:
                    score = float(raw.get("score", 0))
                except Exception:  # noqa: BLE001
                    score = 0.0
                normalized_dims.append(
                    {
                        "name": str(raw.get("name") or "維度").strip(),
                        "score": max(0.0, min(score, 10.0)),
                        "note": str(raw.get("note") or "").strip(),
                    }
                )

        if not normalized_dims:
            return self._fallback_critique("")

        return {
            "overview": str(critique.get("overview") or "").strip() or "整體可用，建議先修正高影響細節。",
            "dimensions": normalized_dims,
            "keep": self._normalize_string_list(critique.get("keep")),
            "fix": self._normalize_string_list(critique.get("fix")),
            "quick_wins": self._normalize_string_list(critique.get("quick_wins")),
        }

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:8]

    def _fallback_critique(self, html_content: str) -> dict[str, Any]:
        has_tokens = "--accent" in html_content or ":root" in html_content
        has_mobile = "@media" in html_content
        has_motion_gate = "prefers-reduced-motion" in html_content

        base = 6.8
        bonus = (0.6 if has_tokens else 0.0) + (0.6 if has_mobile else 0.0) + (0.4 if has_motion_gate else 0.0)
        score = min(9.1, round(base + bonus, 1))

        return {
            "overview": "本地規則評估完成：整體結構已具備可展示品質，仍建議補強內容層級與情境化細節。",
            "dimensions": [
                {"name": "哲學一致性", "score": score, "note": "主視覺語言一致，方向可辨識。"},
                {"name": "視覺層級", "score": score - 0.4, "note": "主次訊息明確，但可再強化重點對比。"},
                {"name": "細節執行", "score": score - 0.2, "note": "版面與元件規整，仍可加強字距與邊界細節。"},
                {"name": "功能性", "score": score + 0.1, "note": "結構可互動、可擴充，具備後續迭代基礎。"},
                {"name": "創新性", "score": score - 0.6, "note": "方向安全可用，可再加入更鮮明的記憶點。"},
            ],
            "keep": [
                "維持目前的色彩 token 與分層策略",
                "保留本地化、單檔可攜的交付形式",
            ],
            "fix": [
                "補強主標與次要資訊的字級差，避免閱讀節奏過平",
                "增加與任務情境直接對應的內容區塊，避免過度模板感",
            ],
            "quick_wins": [
                "把 CTA 區塊對比再提高一階",
                "新增一段 2-3 行的證據型內容",
                "行動版把主要操作區塊提前到首屏",
            ],
        }

    @staticmethod
    def _update_editmode_block(content: str, values: dict[str, str]) -> tuple[str, dict[str, str]]:
        if not values:
            return content, {}

        pattern = re.compile(r"/\*EDITMODE-BEGIN\*/([\s\S]*?)/\*EDITMODE-END\*/", flags=re.IGNORECASE)
        match = pattern.search(content)
        if not match:
            return content, {}

        block = match.group(1).strip()
        params = json.loads(block)
        applied: dict[str, str] = {}

        for key, value in values.items():
            key_s = str(key).strip()
            value_s = str(value).strip()
            if not key_s or not value_s:
                continue
            if key_s not in params:
                continue
            params[key_s] = value_s
            applied[key_s] = value_s

        if not applied:
            return content, {}

        json_block = json.dumps(params, ensure_ascii=False, indent=2)
        replacement = f"/*EDITMODE-BEGIN*/\n{json_block}\n/*EDITMODE-END*/"
        updated = pattern.sub(replacement, content, count=1)
        return updated, applied

    def _append_session_log(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        log_path = DESIGN_SESSION_DIR / f"{session_id}.jsonl"
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _default_design_spec(name: str, brief: str, language: str) -> str:
        return f"""---
version: alpha
name: {name} Design System
description: Local-first design system for {name}
colors:
  background: \"#F6F1E8\"
  surface: \"#FFF8EF\"
  text: \"#191613\"
  muted: \"#62564B\"
  accent: \"#C4491D\"
typography:
  display:
    fontFamily: \"Noto Serif TC\"
    fontSize: \"56px\"
    fontWeight: 700
    lineHeight: 1.05
rounded:
  sm: \"8px\"
  md: \"14px\"
  lg: \"22px\"
spacing:
  sm: \"8px\"
  md: \"16px\"
  lg: \"28px\"
components:
  button-primary:
    backgroundColor: \"{{colors.accent}}\"
    textColor: \"#FFFFFF\"
    rounded: \"{{rounded.md}}\"
---

## Overview
- Project: {name}
- Language: {language}
- Local-first requirement: true

## Brief
{brief.strip()}

## Do's
- Preserve strong typography hierarchy.
- Keep artifact self-contained and editable.

## Don'ts
- Do not use generic AI default purple gradients.
- Do not import external runtime dependencies.
"""
