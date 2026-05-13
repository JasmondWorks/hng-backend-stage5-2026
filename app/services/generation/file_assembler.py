from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.models.skill import Skill
from app.schemas.agent import AgentDraft

_TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,
    undefined=StrictUndefined,
)

# Maps output filename → (template name, draft field that provides the "content" block)
_TEMPLATE_MAP: list[tuple[str, str, str | None]] = [
    ("identity.md", "identity.md.j2", "identity"),
    ("soul.md", "soul.md.j2", "soul"),
    ("dna.md", "dna.md.j2", "dna"),
    ("heartbeat.md", "heartbeat.md.j2", "heartbeat"),
    ("README.md", "README.md.j2", None),
]


async def assemble_files(draft: AgentDraft, skills: list[Skill]) -> dict[str, str]:
    """Render all five Jinja2 templates and return filename → content mapping."""
    skill_data = [
        {"name": s.name, "description": s.description} for s in skills
    ]
    base_ctx = {
        "name": draft.name or "",
        "category": draft.category or "",
        "description_summary": draft.description_summary or "",
        "skills": skill_data,
    }

    files: dict[str, str] = {}
    for filename, template_name, draft_field in _TEMPLATE_MAP:
        template = _env.get_template(template_name)
        ctx = dict(base_ctx)
        if draft_field is not None:
            ctx["content"] = getattr(draft, draft_field) or ""
        files[filename] = template.render(**ctx)

    return files
