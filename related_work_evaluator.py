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
学术论文综述评估工作流程
遍历survey_bench_result目录下的JSON文件，提取URL并与ground truth比较评估
"""
import json
import re
import os
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import pandas as pd
from collections import defaultdict

from utils import build_llm, save_csv
from cache_utils import normalize_url


class SurveyEvaluationWorkflow:
    """学术论文综述评估工作流程"""
    
    def __init__(self, survey_dir, ground_truth_dir, result_dir, use_cache=True, no_url=False, cache_file="url_cache.csv"):
        self.survey_dir = Path(survey_dir)
        self.ground_truth_dir = Path(ground_truth_dir)
        self.result_dir = Path(result_dir)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.use_cache = use_cache  # 是否使用缓存的开关
        self.no_url = no_url  # 是否启用no-url模式
        self.cache_file = cache_file  # URL缓存文件路径
        
        # 汇总结果
        self.evaluation_results = []
        
    def process_all_files(self):
        """处理所有文件的完整流程"""
        mode_desc = "no-url模式" if self.no_url else "标准URL模式"
        print(f"开始处理survey_bench_result目录下的所有JSON文件... ({mode_desc})")
        
        # 获取所有JSON文件
        json_files = list(self.survey_dir.glob("*.json"))
        if not json_files:
            print(f"错误: {self.survey_dir} 目录下没有找到JSON文件")
            return
        
        print(f"找到 {len(json_files)} 个JSON文件")
        
        # 逐文件处理
        for i, json_file in enumerate(json_files, 1):
            print(f"\n{'='*80}")
            print(f"处理文件 {i}/{len(json_files)}: {json_file.name}")
            print(f"{'='*80}")
            
            try:
                result = self.process_single_file(json_file)
                if result:
                    self.evaluation_results.append(result)
                    print(f"✓ 文件 {json_file.name} 处理完成")
                else:
                    print(f"✗ 文件 {json_file.name} 处理失败")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"✗ 文件 {json_file.name} 处理失败: {e}")
                continue
        
        # 生成最终统计报告
        self.generate_final_report()
        print(f"\n处理完成! 结果保存在: {self.result_dir}")
        
    def extract_arxiv_id(self, filename: str) -> Optional[str]:
        """从文件名中提取arXiv ID"""
        # 文件名格式: parsed_liminghao+openai+2108.09091.json
        # 提取最后的数字部分作为arXiv ID
        match = re.search(r'(\d{4}\.\d{5})', filename)
        if match:
            return match.group(1)
        return None
        
    def process_single_file(self, json_file: Path) -> Optional[Dict]:
        """处理单个JSON文件"""
        # 1. 提取arXiv ID
        arxiv_id = self.extract_arxiv_id(json_file.name)
        if not arxiv_id:
            print(f"警告: 无法从文件名 {json_file.name} 中提取arXiv ID")
            return None
        
        print(f"arXiv ID: {arxiv_id}")
        
        if self.no_url:
            # no-url模式：直接从JSON文件中提取参考文献论文题目
            predicted_papers = self.extract_papers_no_url(json_file, arxiv_id)
            urls = []  # no-url模式下没有URLs
            contents = []  # no-url模式下没有内容
        else:
            # 标准模式：提取URLs->抓取内容->识别论文
            # 2. 读取JSON文件，提取URLs
            urls = self.extract_urls_from_file(json_file)
            if not urls:
                print("警告: 未提取到任何URL")
                return None
            
            print(f"提取到 {len(urls)} 个URL")
            
            # 3. 抓取URL内容
            contents = self.fetch_url_contents(urls)
            
            # 4. LLM判断是否是论文
            predicted_papers = self.analyze_papers(contents, arxiv_id)
        
        if not predicted_papers:
            print("警告: 未识别到任何学术论文")
            return None
        
        # 5. 读取ground truth
        ground_truth_papers = self.load_ground_truth(arxiv_id)
        if not ground_truth_papers:
            print(f"警告: 找不到arXiv ID {arxiv_id} 的ground truth")
            return None
        
        # 6. 计算precision和recall
        evaluation = self.evaluate_predictions(predicted_papers, ground_truth_papers, arxiv_id)
        
        # 7. 保存单文件结果
        self.save_single_file_results(arxiv_id, urls, contents, predicted_papers, ground_truth_papers, evaluation)
        
        return evaluation
    
    def extract_papers_no_url(self, json_file: Path, arxiv_id: str) -> List[Dict]:
        """no-url模式：直接从JSON文件中使用LLM提取参考文献论文题目"""
        print("使用LLM直接从文件内容中提取参考文献论文题目...")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                response = data.get('response', '')
                
            if not response:
                print("警告: JSON文件中没有response内容")
                return []
            
            llm = build_llm()
            
            # 构造提取参考文献的prompt
            prompt = f"""
请分析以下学术综述内容，提取其中引用的所有学术论文的标题和作者信息。

综述内容:
{response[:12000]}  

请以JSON格式回复，包含一个papers数组，每个论文对象包含以下字段：
- title: 论文标题
- authors: 作者列表
- is_academic_paper: true（表示这是学术论文）

示例格式:
{{
    "papers": [
        {{
            "title": "Deep Learning for Natural Language Processing",
            "authors": ["John Smith", "Jane Doe"],
            "is_academic_paper": true
        }},
        {{
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "is_academic_paper": true
        }}
    ]
}}

注意：只提取明确提到的学术论文，不要包含书籍、网站或其他类型的文献。
"""
            
            response_text = llm.invoke(prompt)
            result_text = response_text.content
            
            # 解析LLM回复
            try:
                # 提取JSON部分
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_text = result_text[json_start:json_end]
                    analysis = json.loads(json_text)
                    papers_list = analysis.get('papers', [])
                else:
                    print("警告: LLM回复格式错误，找不到JSON")
                    papers_list = []
                    
            except json.JSONDecodeError as e:
                print(f"警告: JSON解析失败: {e}")
                papers_list = []
            
            # 转换为标准格式
            papers = []
            for paper in papers_list:
                papers.append({
                    'url': '',  # no-url模式下没有URL
                    'is_academic_paper': paper.get('is_academic_paper', True),
                    'title': paper.get('title', ''),
                    'authors': ', '.join(paper.get('authors', [])) if paper.get('authors') else '',
                    'reason': 'no-url模式直接提取',
                    'llm_response': result_text
                })
            
            print(f"从文件内容中提取到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            print(f"no-url模式提取失败: {e}")
            return []
        
    def extract_urls_from_file(self, json_file: Path) -> List[str]:
        """从JSON文件中直接用正则表达式提取所有http/https开头的URL"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                response = data.get('response', '')
                
                # 直接用正则表达式提取所有http/https开头的URL
                url_pattern = r'(https?://[^\s\)\]\"\'>]+)'
                urls = re.findall(url_pattern, response)
                
                # 去重，保持顺序
                unique_urls = list(dict.fromkeys(urls))
                return unique_urls
                
        except Exception as e:
            print(f"读取文件失败: {e}")
            return []
    
    def fetch_url_contents(self, urls: List[str]) -> List[Dict]:
        """抓取URL内容，复用现有的缓存机制"""
        from cache_utils import load_or_create_url_cache, get_or_create_id_for_url, save_url_cache
        from firecrawl import FirecrawlApp
        from config import FIRECRAWL_API_KEY
        from utils import retry_async
        
        # 去重URL（基于normalize后的URL）
        unique_urls = self._deduplicate_urls(urls)
        print(f"去重后: {len(unique_urls)} 个URL")
        
        # 加载URL缓存
        url_cache = load_or_create_url_cache(self.cache_file)
        
        # 创建缓存目录
        cache_dir = Path("raw_texts")
        cache_dir.mkdir(exist_ok=True)
        
        contents = []

        @retry_async(attempts=2) 
        def _load_with_firecrawl(url: str) -> str | None:
            if not FIRECRAWL_API_KEY:
                return None
            app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
            try:
                res = app.scrape_url(url, formats=['markdown'], timeout=60*10e3)
                return res.markdown
            except Exception as e:
                if "Failed to scrape URL" in str(e) and "All scraping engines failed" in str(e):
                    print(f"  ✗ URL无法访问导致抓取失败: {url}")
                    return None
                else:
                    raise e
        
        for i, url in enumerate(unique_urls, 1):
            print(f"处理URL {i}/{len(unique_urls)}: {url[:80]}...")
            
            try:
                # 获取或创建URL对应的随机ID
                random_id, url_cache = get_or_create_id_for_url(url, url_cache)
                cache_file_path = cache_dir / f"{random_id}.txt"
                
                # 检查缓存
                if self.use_cache and cache_file_path.exists():
                    print(f"  ✓ 使用缓存: {random_id}.txt")
                    content = cache_file_path.read_text(encoding='utf-8')
                    contents.append({
                        'url': url,
                        'status': 'success',
                        'content': content,
                        'random_id': random_id,
                        'from_cache': True
                    })
                else:
                    # 抓取内容
                    print(f"  → 抓取新内容...")
                    content = None
                    
                    try:
                        content = _load_with_firecrawl(url)
                    except Exception as e:
                        print(f"  ✗ 抓取失败: {e}")
                    
                    if content:
                        # 保存到缓存
                        cache_file_path.write_text(content, encoding='utf-8')
                        print(f"  ✓ 抓取成功，已缓存: {random_id}.txt")
                        contents.append({
                            'url': url,
                            'status': 'success', 
                            'content': content,
                            'random_id': random_id,
                            'from_cache': False
                        })
                    else:
                        print(f"  ✗ 抓取失败: 无法获取内容")
                        contents.append({
                            'url': url,
                            'status': 'failed',
                            'content': '',
                            'random_id': random_id,
                            'from_cache': False,
                            'error': '抓取失败'
                        })
                        
            except Exception as e:
                print(f"  ✗ 处理失败: {e}")
                contents.append({
                    'url': url,
                    'status': 'failed',
                    'content': '',
                    'random_id': '',
                    'from_cache': False,
                    'error': str(e)
                })
        
        # 保存URL缓存
        save_url_cache(url_cache, self.cache_file)
        
        success_count = len([c for c in contents if c['status'] == 'success'])
        print(f"完成URL内容抓取: 成功 {success_count}/{len(unique_urls)} 个")
        
        return contents
    
    def _deduplicate_urls(self, urls: List[str]) -> List[str]:
        """基于标准化URL去重"""
        unique_urls = []
        seen_normalized = set()
        duplicates = 0
        
        for url in urls:
            normalized = normalize_url(url)
            if normalized not in seen_normalized:
                unique_urls.append(url)
                seen_normalized.add(normalized)
            else:
                duplicates += 1
                # 使用原始URL进行日志记录，避免过长
                url_display = url[:80] + "..." if len(url) > 80 else url
                print(f"重复URL已跳过: {url_display}")
        
        if duplicates > 0:
            print(f"去重完成: 移除了 {duplicates} 个重复URL")
        
        return unique_urls
    
    def analyze_papers(self, contents: List[Dict], arxiv_id: str) -> List[Dict]:
        """使用LLM分析学术论文"""
        print("使用LLM分析学术论文...")
        
        llm = build_llm()
        papers = []
        
        # 只处理成功获取内容的URL
        valid_contents = [c for c in contents if c['status'] == 'success' and c['content']]
        
        for i, item in enumerate(valid_contents, 1):
            print(f"分析 {i}/{len(valid_contents)}: {item['url'][:80]}...")
            
            try:
                # 构造分析prompt
                prompt = f"""
请分析以下网页内容，判断它是否是一篇学术论文。如果是学术论文，请提取标题和作者信息。

网页URL: {item['url']}

网页内容:
{item['content'][:8000]}

请以JSON格式回复，包含以下字段：
- is_academic_paper: true/false
- title: 论文标题（如果是学术论文）
- authors: 作者列表（如果是学术论文）
- reason: 判断理由

示例:
{{
    "is_academic_paper": true,
    "title": "Deep Learning for Natural Language Processing",
    "authors": ["John Smith", "Jane Doe"],
    "reason": "包含摘要、关键词、实验结果等学术论文特征"
}}
"""
                retry = True
                while retry:
                    try:
                        response = llm.invoke(prompt)
                        result_text = response.content
                        retry = False
                    except Exception as e:
                        if "reach token limit" in str(e):
                            print(f"[!] 速率墙，重试... {e}")
                            retry = True
                        else:
                            print(f"[!] 其他错误，不重试... {e}")
                            retry = False
                            raise e
                
                # 解析LLM回复
                try:
                    # 提取JSON部分
                    json_start = result_text.find('{')
                    json_end = result_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_text = result_text[json_start:json_end]
                        analysis = json.loads(json_text)
                    else:
                        analysis = {"is_academic_paper": False, "reason": "LLM回复格式错误"}
                        
                except json.JSONDecodeError:
                    analysis = {"is_academic_paper": False, "reason": "JSON解析失败"}
                
                papers.append({
                    'url': item['url'],
                    'is_academic_paper': analysis.get('is_academic_paper', False),
                    'title': analysis.get('title', ''),
                    'authors': ', '.join(analysis.get('authors', [])) if analysis.get('authors') else '',
                    'reason': analysis.get('reason', ''),
                    'llm_response': result_text
                })
                
            except Exception as e:
                print(f"分析失败: {item['url']} - {e}")
                papers.append({
                    'url': item['url'],
                    'is_academic_paper': False,
                    'title': '',
                    'authors': '',
                    'reason': f'分析错误: {e}',
                    'llm_response': ''
                })
        
        # 只返回被识别为学术论文的结果
        academic_papers = [p for p in papers if p['is_academic_paper']]
        print(f"识别出 {len(academic_papers)} 篇学术论文")
        
        return papers  # 返回所有分析结果以便调试
    
    def load_ground_truth(self, arxiv_id: str) -> List[Dict]:
        """加载ground truth数据"""
        ground_truth_file = self.ground_truth_dir / f"{arxiv_id}.jsonl"
        
        if not ground_truth_file.exists():
            return []
        
        papers = []
        try:
            with open(ground_truth_file, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    papers.append({
                        'bib_id': data.get('bib_id', ''),
                        'title': data.get('title', ''),
                        'author': data.get('author', ''),
                        'meta_info': data.get('meta_info', {})
                    })
        except Exception as e:
            print(f"读取ground truth失败: {e}")
            return []
        
        print(f"加载了 {len(papers)} 篇ground truth论文")
        return papers
    
    def evaluate_predictions(self, predicted_papers: List[Dict], ground_truth_papers: List[Dict], arxiv_id: str) -> Dict:
        """计算precision和recall"""
        print("计算Precision和Recall...")
        
        # 提取预测的学术论文标题（标准化）
        predicted_titles = set()
        for paper in predicted_papers:
            if paper['is_academic_paper'] and paper['title']:
                title = self.normalize_title(paper['title'])
                if title:
                    predicted_titles.add(title)
        
        # 提取ground truth论文标题（标准化）
        ground_truth_titles = set()
        for paper in ground_truth_papers:
            title = self.normalize_title(paper['title'])
            if title:
                ground_truth_titles.add(title)
        
        # 计算交集
        intersection = predicted_titles & ground_truth_titles
        
        # 计算precision和recall
        precision = len(intersection) / len(predicted_titles) if predicted_titles else 0
        recall = len(intersection) / len(ground_truth_titles) if ground_truth_titles else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        evaluation = {
            'arxiv_id': arxiv_id,
            'predicted_count': len(predicted_titles),
            'ground_truth_count': len(ground_truth_titles),
            'intersection_count': len(intersection),
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'predicted_titles': list(predicted_titles),
            'ground_truth_titles': list(ground_truth_titles),
            'intersection_titles': list(intersection)
        }
        
        print(f"Precision: {precision:.3f} ({len(intersection)}/{len(predicted_titles)})")
        print(f"Recall: {recall:.3f} ({len(intersection)}/{len(ground_truth_titles)})")
        print(f"F1-Score: {f1:.3f}")
        
        return evaluation
    
    def normalize_title(self, title: str) -> str:
        """标准化论文标题用于比较"""
        if not title:
            return ""
        
        # 转换为小写，移除标点和多余空格
        import string
        title = title.lower()
        title = title.translate(str.maketrans('', '', string.punctuation))
        title = ' '.join(title.split())
        return title
    
    def save_single_file_results(self, arxiv_id: str, urls: List[str], contents: List[Dict], 
                                predicted_papers: List[Dict], ground_truth_papers: List[Dict], 
                                evaluation: Dict):
        """保存单个文件的处理结果"""
        file_result_dir = self.result_dir / arxiv_id
        file_result_dir.mkdir(exist_ok=True)
        
        # 保存URL列表（no-url模式下为空）
        if urls:
            df_urls = pd.DataFrame([{'url': url} for url in urls])
            save_csv(df_urls, file_result_dir / "extracted_urls.csv")
        
        # 保存URL内容获取结果（no-url模式下为空）
        if contents:
            df_contents = pd.DataFrame(contents)
            save_csv(df_contents, file_result_dir / "url_contents.csv")
        
        # 保存论文分析结果
        df_predicted = pd.DataFrame(predicted_papers)
        save_csv(df_predicted, file_result_dir / "predicted_papers.csv")
        
        # 保存ground truth
        df_ground_truth = pd.DataFrame(ground_truth_papers)
        save_csv(df_ground_truth, file_result_dir / "ground_truth_papers.csv")
        
        # 保存评估结果
        evaluation_summary = {
            'arxiv_id': evaluation['arxiv_id'],
            'predicted_count': evaluation['predicted_count'],
            'ground_truth_count': evaluation['ground_truth_count'],
            'intersection_count': evaluation['intersection_count'],
            'precision': evaluation['precision'],
            'recall': evaluation['recall'],
            'f1_score': evaluation['f1_score']
        }
        
        df_evaluation = pd.DataFrame([evaluation_summary])
        save_csv(df_evaluation, file_result_dir / "evaluation_summary.csv")
        
        # 保存详细的标题比较
        title_comparison = []
        
        # 预测的标题
        for title in evaluation['predicted_titles']:
            title_comparison.append({
                'title': title,
                'type': 'predicted',
                'in_intersection': title in evaluation['intersection_titles']
            })
        
        # Ground truth标题
        for title in evaluation['ground_truth_titles']:
            if title not in evaluation['predicted_titles']:
                title_comparison.append({
                    'title': title,
                    'type': 'ground_truth',
                    'in_intersection': title in evaluation['intersection_titles']
                })
        
        df_titles = pd.DataFrame(title_comparison)
        save_csv(df_titles, file_result_dir / "title_comparison.csv")
    
    def generate_final_report(self):
        """生成最终统计报告"""
        print("\n生成最终统计报告...")
        
        if not self.evaluation_results:
            print("没有评估结果可供统计")
            return
        
        # 创建汇总表格
        summary_data = []
        for result in self.evaluation_results:
            summary_data.append({
                'arxiv_id': result['arxiv_id'],
                'predicted_count': result['predicted_count'],
                'ground_truth_count': result['ground_truth_count'],
                'intersection_count': result['intersection_count'],
                'precision': result['precision'],
                'recall': result['recall'],
                'f1_score': result['f1_score']
            })
        
        df_summary = pd.DataFrame(summary_data)
        save_csv(df_summary, self.result_dir / "final_evaluation_summary.csv")
        
        # 计算总体统计
        total_predicted = sum(r['predicted_count'] for r in self.evaluation_results)
        total_ground_truth = sum(r['ground_truth_count'] for r in self.evaluation_results)
        total_intersection = sum(r['intersection_count'] for r in self.evaluation_results)
        
        overall_precision = total_intersection / total_predicted if total_predicted > 0 else 0
        overall_recall = total_intersection / total_ground_truth if total_ground_truth > 0 else 0
        overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0
        
        # 计算平均指标
        avg_precision = sum(r['precision'] for r in self.evaluation_results) / len(self.evaluation_results)
        avg_recall = sum(r['recall'] for r in self.evaluation_results) / len(self.evaluation_results)
        avg_f1 = sum(r['f1_score'] for r in self.evaluation_results) / len(self.evaluation_results)
        
        # 保存总体统计
        overall_stats = {
            'total_files': len(self.evaluation_results),
            'total_predicted': total_predicted,
            'total_ground_truth': total_ground_truth,
            'total_intersection': total_intersection,
            'overall_precision': overall_precision,
            'overall_recall': overall_recall,
            'overall_f1': overall_f1,
            'average_precision': avg_precision,
            'average_recall': avg_recall,
            'average_f1': avg_f1
        }
        
        df_overall = pd.DataFrame([overall_stats])
        save_csv(df_overall, self.result_dir / "overall_statistics.csv")
        
        # 打印统计结果
        print(f"\n{'='*80}")
        print("最终评估结果:")
        print(f"{'='*80}")
        print(f"处理文件数: {len(self.evaluation_results)}")
        print(f"总预测论文数: {total_predicted}")
        print(f"总真实论文数: {total_ground_truth}")
        print(f"总匹配论文数: {total_intersection}")
        print(f"\n整体指标:")
        print(f"  Precision: {overall_precision:.3f}")
        print(f"  Recall: {overall_recall:.3f}")
        print(f"  F1-Score: {overall_f1:.3f}")
        print(f"\n平均指标:")
        print(f"  Precision: {avg_precision:.3f}")
        print(f"  Recall: {avg_recall:.3f}")
        print(f"  F1-Score: {avg_f1:.3f}")
        print(f"{'='*80}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='学术论文综述评估工作流程')
    
    parser.add_argument('--survey-dir', required=True, 
                        help='包含JSON文件的survey目录路径')
    parser.add_argument('--ground-truth-dir', default="ReportBench_v1.1_GT",
                        help='包含ground truth文件的目录路径')
    parser.add_argument('--result-dir', required=True,
                        help='保存结果的目录路径')
    parser.add_argument('--no-cache', action='store_true',
                        help='不使用缓存，每次都重新抓取URL内容')
    parser.add_argument('--no-url', action='store_true',
                        help='不进行URL提取和抓取，直接从文件内容中提取参考文献论文题目')
    parser.add_argument('--cache-file', default="url_cache.csv",
                        help='URL缓存文件路径')
    
    return parser.parse_args()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    survey_dir = args.survey_dir
    ground_truth_dir = args.ground_truth_dir
    result_dir = args.result_dir
    use_cache = not args.no_cache  # no_cache为True时，use_cache为False
    no_url = args.no_url
    cache_file = args.cache_file
    
    # 检查必要目录
    if not Path(survey_dir).exists():
        print(f"错误: 找不到目录 {survey_dir}")
        return

    if not Path(ground_truth_dir).exists():
        print(f"错误: 找不到目录 {ground_truth_dir}")
        return
    
    # 打印配置信息
    print(f"配置信息:")
    print(f"  Survey目录: {survey_dir}")
    print(f"  Ground Truth目录: {ground_truth_dir}")
    print(f"  结果目录: {result_dir}")
    print(f"  使用缓存: {use_cache}")
    print(f"  no-url模式: {no_url}")
    print(f"  缓存文件: {cache_file}")
    print()
    
    # 开始处理
    workflow = SurveyEvaluationWorkflow(survey_dir, ground_truth_dir, result_dir, 
                                       use_cache=use_cache, no_url=no_url, cache_file=cache_file)
    workflow.process_all_files()


if __name__ == "__main__":
    main() 