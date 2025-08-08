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

import os
import shutil
import json

gemini_dir = "results/v1.0-gemini-722-collected"
output_dir = "results/rerun_gemini/collected"
for file in os.listdir(gemini_dir):
    if file.endswith(".json"):
        with open(os.path.join(gemini_dir, file), "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                arxiv_id = file.replace(".json", "")
                json.dump({'messages': data, 'activity': ''}, open(os.path.join(output_dir, file), "w"))
                shutil.copyfile(os.path.join(gemini_dir, arxiv_id + ".md"), os.path.join(output_dir, arxiv_id + ".md"))
