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

PREFERENCE_PROMPTS = {"en": PREFERENCE_CATEGORY_PROMPT_EN, "zh": PREFERENCE_CATEGORY_PROMPT_ZH}
