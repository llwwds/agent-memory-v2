"""Per-category extraction prompts (agent-memory-v2 own module).

One prompt per category key, mirroring the cloud `custom_extract_prompt` shape:
all prompts consume the same conversation window text and return strict JSON
whose records match the category's response-view contract fields.

M1: preference. detail_factual stays on the upstream prompt (see registry).

Placeholders are substituted with str.replace (upstream convention), so JSON
braces stay single-braced here.
"""

PREFERENCE_CATEGORY_PROMPT_EN = """You are a preference extractor. Analyze the conversation below and extract the user's preferences.

A preference is a stable inclination of the user that should persist across sessions:
- explicit preference: the user states it directly ("I prefer X", "always do Y", "don't use Z").
- implicit preference: reliably inferable from the user's behavior or choices in the conversation.

Rules:
- Only extract preferences about the USER, not facts about the world or the assistant.
- One preference per record; keep each `preference` a single self-contained sentence.
- `reasoning` must briefly cite the evidence from the conversation.
- `context_summary` is one or two sentences describing the dialog context this preference came from.
- Do NOT invent preferences. If the conversation contains no extractable preference, return an empty list.

Return ONLY a JSON object in exactly this shape, with no extra commentary:
{"preference list": [{"preference": "...", "preference_type": "explicit", "reasoning": "...", "context_summary": "..."}]}

Conversation:
${conversation}"""

PREFERENCE_CATEGORY_PROMPT_ZH = """你是一个偏好抽取器。分析下面的对话，抽取用户的偏好。

偏好是用户稳定的倾向，应当跨会话长期保留：
- explicit（显式偏好）：用户直接说出的喜欢、讨厌、习惯、要求（如"我喜欢用 X"、"以后都 Y"、"不要 Z"）。
- implicit（隐式偏好）：从用户的提问方式、行为和选择中可以可靠推断出的倾向。

规则：
- 只抽取关于「用户」的偏好，不要抽取客观事实或助手的偏好。
- 每条记录只含一个偏好，`preference` 必须是一句自包含的陈述。
- `reasoning` 简要引用对话中的依据。
- `context_summary` 用一两句话概括该偏好所处的对话上下文。
- 严禁编造。若对话中没有可抽取的偏好，返回空列表。

只返回如下形状的 JSON 对象，不要任何额外说明：
{"preference list": [{"preference": "...", "preference_type": "explicit", "reasoning": "...", "context_summary": "..."}]}

对话内容：
${conversation}"""

EVENT_CATEGORY_PROMPT_EN = """You are an event extractor. Analyze the conversation below and extract the events (experiences) that occurred or were decided.

An event is something that happened or will happen at a specific time and/or place, involving specific people:
- meetings, discussions and decisions made, task completions, milestones, trips, incidents, plans.

Rules:
- Do NOT extract stable states, preferences, background facts or general knowledge — those belong to other memory categories.
- One event per record; keep `event_value` a single self-contained sentence describing what happened.
- `event_key` is a short title (at most about 20 characters).
- `event_time`: if the time can be resolved from the conversation (including message timestamps), normalize it to "YYYY-MM-DD HH:MM" when possible; otherwise keep the phrase as stated; use null when truly unknown.
- `event_location`: the place where it happened; null when unknown.
- `event_roles`: list of participant names, e.g. ["user", "Zhang San"]; use [] when unknown.
- Do NOT invent events. If the conversation contains no event, return an empty list.

Return ONLY a JSON object in exactly this shape, with no extra commentary:
{"event list": [{"event_key": "...", "event_value": "...", "event_time": "YYYY-MM-DD HH:MM", "event_location": "...", "event_roles": ["..."]}]}

Conversation:
${conversation}"""

EVENT_CATEGORY_PROMPT_ZH = """你是一个事件抽取器。分析下面的对话，抽取其中发生过（或已确定将发生）的事件（经历）。

事件是在特定时间和/或地点发生、有具体人物参与的事情：
- 会议与讨论、做出的决策、任务完成、项目里程碑、行程、事故、计划安排等。

规则：
- 不要抽取稳定状态、偏好、背景事实或通用知识——那些属于其他记忆类别。
- 每条记录只含一个事件，`event_value` 用一句自包含的话描述发生了什么。
- `event_key` 是短标题（不超过 20 字左右）。
- `event_time`：能从对话（含消息时间戳）解析出时间时，尽量归一化为"YYYY-MM-DD HH:MM"；无法解析时保留原表述；完全未知填 null。
- `event_location`：事件发生地点；未知填 null。
- `event_roles`：参与者姓名列表，如 ["用户", "张三"]；未知填 []。
- 严禁编造。若对话中没有事件，返回空列表。

只返回如下形状的 JSON 对象，不要任何额外说明：
{"event list": [{"event_key": "...", "event_value": "...", "event_time": "YYYY-MM-DD HH:MM", "event_location": "...", "event_roles": ["..."]}]}

对话内容：
${conversation}"""

PREFERENCE_PROMPTS = {"en": PREFERENCE_CATEGORY_PROMPT_EN, "zh": PREFERENCE_CATEGORY_PROMPT_ZH}
EVENT_PROMPTS = {"en": EVENT_CATEGORY_PROMPT_EN, "zh": EVENT_CATEGORY_PROMPT_ZH}
