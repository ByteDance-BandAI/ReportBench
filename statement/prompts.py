# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
所有 Prompt 模板放这里，方便后期统一调整
"""

# 1) 抽取"带引用的表述 + 链接"
PROMPT_EXTRACT_CITATIONS = """
You are given a research report delimited by triple backticks.
Identify every statement that cites an external source (e.g. has a URL, DOI, or explicit citation marker) and pair it with the corresponding URL.
Return a JSON list where each item has two keys:
  "statement": the single‑sentence claim, stripped of leading/trailing whitespace
  "url": the canonical URL that supports that claim
If a citation contains multiple URLs, duplicate the statement for each URL.
ONLY return valid JSON.
Report:
```{report}```
"""

# 2) 抽取"无引用的表述"
PROMPT_EXTRACT_NO_CITATIONS = """
You are given a research report delimited by triple backticks.
You are also given a list of statements that already have citations.

Your task is to identify factual claims or statements that:
1. Make specific assertions about facts, data, or events
2. Are NOT already included in the cited statements list
3. Could potentially be verified through external sources
4. Are NOT common knowledge or widely accepted facts

Exclude:
- Opinions, analysis, or subjective interpretations
- Statements that are already cited (provided in the cited_statements list)
- Common knowledge or universally accepted facts
- Vague or general statements

Return a JSON list where each item has one key:
  "statement": the factual claim that lacks citation support

ONLY return valid JSON.

Report:
```{report}```

Already cited statements:
{cited_statements}
"""

# 3) 从网页原文里找到与表述最相近的句子
PROMPT_MATCH_SENTENCE = """
You are provided with
[Statement]: {statement}

[Source Document]:
\"\"\"{source_text}\"\"\"

Return any relevant content from the source document that supports the statement. This can be a sentence, paragraph, or even the entire text if necessary.
If no content supports it, return "NOT_FOUND".
Return plain text only.
"""

# 4) 判断是否一致
PROMPT_VERIFY_ALIGNMENT = """
You will decide whether a claim is correctly supported by a source sentence.

[Claim] (summary from report):
{statement}

[Source Sentence] (pulled from original source):
{source_sentence}

Respond with JSON containing:
  "reason": one short sentence explaining your decision
  "match": true or false          // true if the source sentence faithfully supports the claim
Return ONLY the JSON.
"""

# 6) 使用联网LLM验证表述正确性
PROMPT_WEB_VERIFY_STATEMENT = """
You are tasked with verifying the accuracy of a factual statement using web search capabilities.

[Statement to verify]:
{statement}

Please:
1. Use web search to find reliable, authoritative sources about this statement
2. Analyze the information you find from multiple sources
3. Determine if the statement is factually correct or incorrect based on your research

Respond with JSON containing:
  "reason": a detailed explanation of your verification process and findings (2-3 sentences)
  "decision": true if the statement is correct, false if it is incorrect

Only return the JSON response.
"""