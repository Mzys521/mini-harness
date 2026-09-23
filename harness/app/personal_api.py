"""Local HTTP surface for personal context, automations and volatile chat."""
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from harness.app.personal import AutomationInput, PreferenceInput, SkillInput, parse_skill_document


class SkillDocument(BaseModel):
    document: str = Field(max_length=20000)


class EnabledInput(BaseModel):
    enabled: bool


class TemporaryMessage(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    input: str = Field(min_length=1, max_length=16000)
    skill_ids: list[str] = Field(default_factory=list, max_length=8)


def register_personal_routes(api, runtime):
    personal = runtime.personal

    @api.get('/v1/preferences')
    def preferences():
        return {'content': personal.get_preferences()}

    @api.put('/v1/preferences')
    def save_preferences(body: PreferenceInput):
        return personal.save_preferences(body.content)

    @api.get('/v1/skills')
    def skills():
        return {'items': personal.get_skills()}

    @api.post('/v1/skills', status_code=201)
    def create_skill(body: SkillInput):
        return personal.save_skill(body)

    @api.post('/v1/skills/import', status_code=201)
    def import_skill(body: SkillDocument):
        return personal.save_skill(SkillInput.model_validate(parse_skill_document(body.document)))

    @api.put('/v1/skills/{skill_id}')
    def update_skill(skill_id: str, body: SkillInput):
        return personal.save_skill(body, skill_id)

    @api.delete('/v1/skills/{skill_id}')
    def delete_skill(skill_id: str):
        if not personal.store.execute('DELETE FROM personal_skills WHERE id=?', (skill_id,)):
            raise LookupError('技能不存在')
        return {'removed': True}

    @api.get('/v1/automations')
    def automations():
        items = personal.get_automations()
        for item in items:
            if item['last_run_id']:
                try:
                    item['run_status'] = runtime.durable.get_result(item['last_run_id']).status.value
                except (LookupError, ValueError):
                    item['run_status'] = 'removed'
        return {'items': items}

    @api.post('/v1/automations', status_code=201)
    def create_automation(body: AutomationInput):
        return personal.create_automation(body)

    @api.patch('/v1/automations/{task_id}')
    def toggle_automation(task_id: str, body: EnabledInput):
        personal.set_automation_enabled(task_id, body.enabled)
        return {'updated': True}

    @api.delete('/v1/automations/{task_id}')
    def delete_automation(task_id: str):
        if not personal.store.execute('DELETE FROM personal_automations WHERE id=?', (task_id,)):
            raise LookupError('定时任务不存在')
        return {'removed': True}

    @api.post('/v1/temporary-chats', status_code=201)
    def temporary_chat():
        return runtime.temporary.create()

    @api.post('/v1/temporary-chats/{session_id}/messages')
    async def temporary_message(session_id: str, body: TemporaryMessage):
        return StreamingResponse(runtime.temporary.stream(session_id, body.input, body.skill_ids),
                                 media_type='text/event-stream', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @api.post('/v1/temporary-chats/{session_id}/end')
    async def end_temporary(session_id: str):
        runtime.temporary.end(session_id)
        return {'ended': True}
