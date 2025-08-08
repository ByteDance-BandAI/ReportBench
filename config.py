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
集中管理所有可配置项（支持 OpenAI / Azure OpenAI）
"""
import json
import os
from dotenv import load_dotenv

load_dotenv()  # 读取 .env

# ◆ 通用 ◆ --------------------------------------------------------
OPENAI_PROVIDER: str = os.getenv("OPENAI_PROVIDER", "openai").lower()
TEMPERATURE: float = float(os.getenv("TEMPERATURE", 0.0))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", 8192))
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

# ◆ SerpAPI 配置 ◆ -------------------------------------------------
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# ◆ OpenAI 官方 ◆ --------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# ◆ Azure OpenAI ◆ -------------------------------------------------
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")

# ◆ WebLLM ◆ -------------------------------------------------
WEB_LLM_KEY = os.getenv("WEB_LLM_KEY", "")
WEB_LLM_BASE_URL = os.getenv("WEB_LLM_BASE_URL", "")