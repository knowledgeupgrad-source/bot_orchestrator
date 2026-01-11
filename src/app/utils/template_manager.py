import json

from jinja2 import Environment

from app.utils.enums import TemplateName, TemplateType
from app.utils.postgress import Postgress

class TemplateManager:
    _instance = None
    _template_cache = {}

    GET_TEMPLATE_BY_AGENT_NAME = """
        SELECT ts.template_id, ts.name, ts.template_text, ts.version, ts.template_type
        FROM template_store ts
        INNER JOIN agent_template at ON ts.template_id = at.template_id
        INNER JOIN agent a ON at.agent_id = a.agent_id
        WHERE a.name = %s
        ORDER BY ts.created_at DESC;
    """

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, agent_name: str):
        if len(self._template_cache) == 0:
            self._agent_name = agent_name
            self._load_agent_templates()

    def get_template(self, template_type: TemplateType, template_name: TemplateName, render: bool = False, **kwargs) -> str:
        template_data = self._template_cache.get(self._agent_name, {}).get(template_type.value, {}).get(template_name.value, {})
        prompt_text = template_data.get('prompt_text', '')
        if not render:
            return prompt_text
        template_env = Environment()
        template = template_env.from_string(prompt_text)
        rendered_template = template.render(**kwargs)
        return rendered_template

    def render_template(self, template_type: TemplateType, template_name: TemplateName, **kwargs) -> str:
        return self.get_template(template_type, template_name, render=True, **kwargs)

    def _load_agent_templates(self):
        db = Postgress()
        rows = db.execute_query(self.GET_TEMPLATE_BY_AGENT_NAME, params=(self._agent_name,), fetch=True)
        self._template_cache[self._agent_name] = {}
        for row in rows:
            template_type = row[4]
            template_name = row[1]
            if template_type not in self._template_cache[self._agent_name]:
                self._template_cache[self._agent_name][template_type] = {}

            self._template_cache[self._agent_name][template_type][template_name] = {
                'template_id': row[0],
                'template_name': row[1],
                'prompt_text': row[2],
                'version': row[3],
                'template_type': row[4],
            }




