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
指标计算器：独立分析statement_evaluator生成的结果并计算性能指标
支持单个文件分析和批量汇总分析
"""

import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


def calculate_file_metrics(results_dir: Path, arxiv_id: str) -> Optional[Dict]:
    """计算单个文件的指标，如果关键文件缺失则返回None"""
    print(f"\n==> 计算 {arxiv_id} 的指标...")
    
    # 检查关键文件是否存在
    citations_file = results_dir / "citations.csv"
    if not citations_file.exists():
        print(f"[!] 关键文件缺失，跳过 {arxiv_id}: citations.csv 不存在")
        return None
    
    metrics = {
        'arxiv_id': arxiv_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        
        # 基础统计
        'total_citations': 0,
        'total_no_citations': 0,
        'total_statements': 0,
        
        # 匹配统计
        'matched_statements': 0,
        'match_rate': 0.0,
        
        # 验证统计
        'aligned_statements': 0,
        'alignment_rate': 0.0,
        
        # 无引用验证统计
        'no_citations_correct': 0,
        'no_citations_incorrect': 0,
        'no_citations_tie': 0,
        'no_citations_accuracy': 0.0,
        
        # 文件状态
        'has_citations': False,
        'has_no_citations': False,
        'has_matched': False,
        'has_final': False,
        'has_no_citations_verification': False,
        
        # 缺失文件统计
        'missing_files': []
    }
    
    # 读取各个CSV文件
    try:
        # 1. citations.csv (已检查存在)
        try:
            df_citations = pd.read_csv(citations_file)
            metrics['total_citations'] = len(df_citations)
            metrics['has_citations'] = True
        except Exception as e:
            print(f"[!] 读取citations.csv失败，跳过 {arxiv_id}: {e}")
            return None
        
        # 2. no_citations.csv
        no_citations_file = results_dir / "no_citations.csv"
        if no_citations_file.exists():
            try:
                df_no_citations = pd.read_csv(no_citations_file)
                metrics['total_no_citations'] = len(df_no_citations)
                metrics['has_no_citations'] = True
            except Exception as e:
                print(f"[!] 读取no_citations.csv失败: {e}")
                metrics['missing_files'].append('no_citations.csv')
        else:
            metrics['missing_files'].append('no_citations.csv')
        
        # 总表述数
        metrics['total_statements'] = metrics['total_citations'] + metrics['total_no_citations']
        
        # 3. matched.csv
        matched_file = results_dir / "matched.csv"
        if matched_file.exists():
            try:
                df_matched = pd.read_csv(matched_file)
                metrics['matched_statements'] = len(df_matched)
                metrics['has_matched'] = True
                
                # 计算匹配率
                if metrics['total_citations'] > 0:
                    metrics['match_rate'] = metrics['matched_statements'] / metrics['total_citations']
            except Exception as e:
                print(f"[!] 读取matched.csv失败: {e}")
                metrics['missing_files'].append('matched.csv')
        else:
            metrics['missing_files'].append('matched.csv')
        
        # 4. final.csv
        final_file = results_dir / "final.csv"
        if final_file.exists():
            try:
                df_final = pd.read_csv(final_file)
                metrics['aligned_statements'] = df_final['match'].sum() if 'match' in df_final.columns else 0
                metrics['has_final'] = True
                
                # 计算对齐率
                if len(df_final) > 0:
                    metrics['alignment_rate'] = metrics['aligned_statements'] / len(df_final)
            except Exception as e:
                print(f"[!] 读取final.csv失败: {e}")
                metrics['missing_files'].append('final.csv')
        else:
            metrics['missing_files'].append('final.csv')
        
        # 5. no_citations_web_final.csv
        no_citations_final_file = results_dir / "no_citations_web_final.csv"
        if no_citations_final_file.exists():
            try:
                df_no_citations_final = pd.read_csv(no_citations_final_file)
                metrics['has_no_citations_verification'] = True
                
                if 'final_decision' in df_no_citations_final.columns:
                    metrics['no_citations_correct'] = len(df_no_citations_final[df_no_citations_final['final_decision'] == '正确'])
                    metrics['no_citations_incorrect'] = len(df_no_citations_final[df_no_citations_final['final_decision'] == '错误'])
                    metrics['no_citations_tie'] = len(df_no_citations_final[df_no_citations_final['final_decision'] == '平局'])
                    
                    # 计算准确率（正确的比例）
                    total_verified = len(df_no_citations_final)
                    if total_verified > 0:
                        metrics['no_citations_accuracy'] = metrics['no_citations_correct'] / total_verified
            except Exception as e:
                print(f"[!] 读取no_citations_web_final.csv失败: {e}")
                metrics['missing_files'].append('no_citations_web_final.csv')
        else:
            metrics['missing_files'].append('no_citations_web_final.csv')
    
    except Exception as e:
        print(f"[!] 计算 {arxiv_id} 指标时出错: {e}")
        return None
    
    # 报告缺失文件
    if metrics['missing_files']:
        print(f"[!] {arxiv_id} 缺失文件: {', '.join(metrics['missing_files'])}")
    
    return metrics


def save_file_metrics(metrics: Optional[Dict], results_dir: Path):
    """保存单个文件的指标到CSV"""
    if metrics is None:
        print(f"[!] 无法保存指标: 计算失败")
        return
    
    metrics_file = results_dir / "metrics.csv"
    
    # 转换为DataFrame
    df_metrics = pd.DataFrame([metrics])
    
    # 保存到CSV
    df_metrics.to_csv(metrics_file, index=False, encoding='utf-8')
    
    print(f"[✓] 文件指标已保存到: {metrics_file}")
    
    # 打印指标摘要
    print_file_summary(metrics)


def print_file_summary(metrics: Dict):
    """打印单个文件的指标摘要"""
    print(f"\n==============================")
    print(f"文件指标摘要 - {metrics['arxiv_id']}")
    print(f"==============================")
    print(f"总表述数: {metrics['total_statements']}")
    print(f"├─ 带引用表述: {metrics['total_citations']}")
    print(f"└─ 无引用表述: {metrics['total_no_citations']}")
    print(f"")
    print(f"匹配统计:")
    print(f"├─ 成功匹配: {metrics['matched_statements']}")
    print(f"└─ 匹配率: {metrics['match_rate']:.2%}")
    print(f"")
    print(f"对齐验证:")
    print(f"├─ 对齐成功: {metrics['aligned_statements']}")
    print(f"└─ 对齐率: {metrics['alignment_rate']:.2%}")
    print(f"")
    if metrics['has_no_citations_verification']:
        print(f"无引用验证:")
        print(f"├─ 正确: {metrics['no_citations_correct']}")
        print(f"├─ 错误: {metrics['no_citations_incorrect']}")
        print(f"├─ 平局: {metrics['no_citations_tie']}")
        print(f"└─ 准确率: {metrics['no_citations_accuracy']:.2%}")
    
    # 显示缺失文件信息
    if 'missing_files' in metrics and metrics['missing_files']:
        print(f"")
        print(f"缺失文件: {', '.join(metrics['missing_files'])}")
    
    print(f"==============================\n")


def calculate_batch_metrics(results_dir: Path) -> pd.DataFrame:
    """计算批量处理的汇总指标"""
    print(f"\n==> 计算批量处理汇总指标...")
    
    # 收集所有文件的指标
    all_metrics = []
    skipped_files = []
    total_dirs = 0
    
    # 遍历所有子目录（每个arxiv_id一个目录）
    for subdir in results_dir.iterdir():
        if subdir.is_dir():
            total_dirs += 1
            # 检查是否已有metrics.csv，如果没有则计算
            metrics_file = subdir / "metrics.csv"
            if not metrics_file.exists():
                print(f"[→] 为 {subdir.name} 计算指标...")
                metrics = calculate_file_metrics(subdir, subdir.name)
                if metrics is not None:
                    save_file_metrics(metrics, subdir)
                else:
                    skipped_files.append(subdir.name)
                    print(f"[!] 跳过 {subdir.name}，无法计算指标")
                    continue
            
            # 读取指标文件
            if metrics_file.exists():
                try:
                    df_file_metrics = pd.read_csv(metrics_file)
                    all_metrics.append(df_file_metrics.iloc[0].to_dict())
                except Exception as e:
                    print(f"[!] 读取 {metrics_file} 时出错: {e}")
                    skipped_files.append(subdir.name)
            else:
                skipped_files.append(subdir.name)
    
    print(f"[✓] 发现 {total_dirs} 个目录，成功处理 {len(all_metrics)} 个，跳过 {len(skipped_files)} 个")
    if skipped_files:
        print(f"[!] 跳过的文件: {', '.join(skipped_files)}")
    
    if not all_metrics:
        print(f"[!] 未找到任何有效的指标文件")
        return pd.DataFrame()
    
    # 合并所有指标
    df_all_metrics = pd.DataFrame(all_metrics)
    
    # 计算汇总统计
    summary_metrics = {
        'metric_type': '批量汇总',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_files': len(df_all_metrics),
        
        # 总计
        'total_statements_sum': df_all_metrics['total_statements'].sum(),
        'total_citations_sum': df_all_metrics['total_citations'].sum(),
        'total_no_citations_sum': df_all_metrics['total_no_citations'].sum(),
        'matched_statements_sum': df_all_metrics['matched_statements'].sum(),
        'aligned_statements_sum': df_all_metrics['aligned_statements'].sum(),
        'no_citations_correct_sum': df_all_metrics['no_citations_correct'].sum(),
        'no_citations_incorrect_sum': df_all_metrics['no_citations_incorrect'].sum(),
        
        # 平均值
        'avg_statements_per_file': df_all_metrics['total_statements'].mean(),
        'avg_citations_per_file': df_all_metrics['total_citations'].mean(),
        'avg_no_citations_per_file': df_all_metrics['total_no_citations'].mean(),
        'avg_match_rate': df_all_metrics['match_rate'].mean(),
        'avg_alignment_rate': df_all_metrics['alignment_rate'].mean(),
        'avg_no_citations_accuracy': df_all_metrics['no_citations_accuracy'].mean(),
        
        # 总体率
        'overall_match_rate': df_all_metrics['matched_statements'].sum() / df_all_metrics['total_citations'].sum() if df_all_metrics['total_citations'].sum() > 0 else 0,
        'overall_alignment_rate': df_all_metrics['aligned_statements'].sum() / df_all_metrics['matched_statements'].sum() if df_all_metrics['matched_statements'].sum() > 0 else 0,
        'overall_no_citations_accuracy': df_all_metrics['no_citations_correct'].sum() / (df_all_metrics['no_citations_correct'].sum() + df_all_metrics['no_citations_incorrect'].sum()) if (df_all_metrics['no_citations_correct'].sum() + df_all_metrics['no_citations_incorrect'].sum()) > 0 else 0,
        
        # 文件完成状态统计
        'files_with_citations': df_all_metrics['has_citations'].sum(),
        'files_with_no_citations': df_all_metrics['has_no_citations'].sum(),
        'files_with_matched': df_all_metrics['has_matched'].sum(),
        'files_with_final': df_all_metrics['has_final'].sum(),
        'files_with_no_citations_verification': df_all_metrics['has_no_citations_verification'].sum(),
    }
    
    # 保存详细指标
    detailed_metrics_file = results_dir / "detailed_metrics.csv"
    df_all_metrics.to_csv(detailed_metrics_file, index=False, encoding='utf-8')
    
    # 保存汇总指标
    summary_metrics_file = results_dir / "batch_summary_metrics.csv"
    df_summary = pd.DataFrame([summary_metrics])
    df_summary.to_csv(summary_metrics_file, index=False, encoding='utf-8')
    
    print(f"[✓] 详细指标已保存到: {detailed_metrics_file}")
    print(f"[✓] 汇总指标已保存到: {summary_metrics_file}")
    
    # 打印汇总报告
    print_batch_summary(summary_metrics)
    
    return df_all_metrics


def print_batch_summary(summary_metrics: Dict):
    """打印批量处理汇总报告"""
    print(f"\n" + "="*50)
    print(f"批量处理汇总报告")
    print(f"="*50)
    print(f"处理时间: {summary_metrics['timestamp']}")
    print(f"处理文件数: {summary_metrics['total_files']}")
    print(f"")
    
    print(f"总体统计:")
    print(f"├─ 总表述数: {summary_metrics['total_statements_sum']}")
    print(f"├─ 带引用表述: {summary_metrics['total_citations_sum']}")
    print(f"└─ 无引用表述: {summary_metrics['total_no_citations_sum']}")
    print(f"")
    
    print(f"平均每文件:")
    print(f"├─ 平均表述数: {summary_metrics['avg_statements_per_file']:.1f}")
    print(f"├─ 平均引用数: {summary_metrics['avg_citations_per_file']:.1f}")
    print(f"└─ 平均无引用数: {summary_metrics['avg_no_citations_per_file']:.1f}")
    print(f"")
    
    print(f"总体性能指标:")
    print(f"├─ 总体匹配率: {summary_metrics['overall_match_rate']:.2%}")
    print(f"├─ 总体对齐率: {summary_metrics['overall_alignment_rate']:.2%}")
    print(f"└─ 总体无引用准确率: {summary_metrics['overall_no_citations_accuracy']:.2%}")
    print(f"")
    
    print(f"平均性能指标:")
    print(f"├─ 平均匹配率: {summary_metrics['avg_match_rate']:.2%}")
    print(f"├─ 平均对齐率: {summary_metrics['avg_alignment_rate']:.2%}")
    print(f"└─ 平均无引用准确率: {summary_metrics['avg_no_citations_accuracy']:.2%}")
    print(f"")
    
    print(f"处理完成状态:")
    print(f"├─ 有引用提取: {summary_metrics['files_with_citations']}/{summary_metrics['total_files']}")
    print(f"├─ 有无引用提取: {summary_metrics['files_with_no_citations']}/{summary_metrics['total_files']}")
    print(f"├─ 有匹配结果: {summary_metrics['files_with_matched']}/{summary_metrics['total_files']}")
    print(f"├─ 有最终结果: {summary_metrics['files_with_final']}/{summary_metrics['total_files']}")
    print(f"└─ 有无引用验证: {summary_metrics['files_with_no_citations_verification']}/{summary_metrics['total_files']}")
    print(f"="*50 + "\n")


def generate_comparison_report(results_dir: Path, output_file: Optional[str] = None):
    """生成文件对比报告，展示各文件的性能差异"""
    print(f"\n==> 生成文件对比报告...")
    
    detailed_metrics_file = results_dir / "detailed_metrics.csv"
    if not detailed_metrics_file.exists():
        print(f"[!] 未找到详细指标文件: {detailed_metrics_file}")
        print(f"[!] 请先运行批量指标计算")
        return
    
    df_metrics = pd.read_csv(detailed_metrics_file)
    
    # 按匹配率排序
    df_sorted = df_metrics.sort_values('match_rate', ascending=False)
    
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("文件性能对比报告")
    report_lines.append("="*80)
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"总文件数: {len(df_metrics)}")
    report_lines.append("")
    
    # 性能排行榜
    report_lines.append("匹配率排行榜 (Top 10):")
    report_lines.append("-" * 50)
    for i, (_, row) in enumerate(df_sorted.head(10).iterrows(), 1):
        report_lines.append(f"{i:2d}. {str(row['arxiv_id']):15s} - {row['match_rate']:6.2%} (对齐率: {row['alignment_rate']:6.2%})")
    
    report_lines.append("")
    report_lines.append("对齐率排行榜 (Top 10):")
    report_lines.append("-" * 50)
    df_alignment_sorted = df_metrics.sort_values('alignment_rate', ascending=False)
    for i, (_, row) in enumerate(df_alignment_sorted.head(10).iterrows(), 1):
        report_lines.append(f"{i:2d}. {str(row['arxiv_id']):15s} - {row['alignment_rate']:6.2%} (匹配率: {row['match_rate']:6.2%})")
    
    # 统计分布
    report_lines.append("")
    report_lines.append("性能分布统计:")
    report_lines.append("-" * 50)
    
    # 匹配率分布
    match_rate_ranges = [
        ("90%+", df_metrics[df_metrics['match_rate'] >= 0.9]),
        ("80-89%", df_metrics[(df_metrics['match_rate'] >= 0.8) & (df_metrics['match_rate'] < 0.9)]),
        ("70-79%", df_metrics[(df_metrics['match_rate'] >= 0.7) & (df_metrics['match_rate'] < 0.8)]),
        ("60-69%", df_metrics[(df_metrics['match_rate'] >= 0.6) & (df_metrics['match_rate'] < 0.7)]),
        ("<60%", df_metrics[df_metrics['match_rate'] < 0.6])
    ]
    
    report_lines.append("匹配率分布:")
    for range_name, df_range in match_rate_ranges:
        count = len(df_range)
        percentage = count / len(df_metrics) * 100 if len(df_metrics) > 0 else 0
        report_lines.append(f"  {range_name:8s}: {count:3d} 个文件 ({percentage:5.1f}%)")
    
    # 表述数量统计
    report_lines.append("")
    report_lines.append("表述数量统计:")
    report_lines.append(f"  平均表述数: {df_metrics['total_statements'].mean():.1f}")
    report_lines.append(f"  最多表述数: {df_metrics['total_statements'].max()}")
    report_lines.append(f"  最少表述数: {df_metrics['total_statements'].min()}")
    report_lines.append(f"  中位表述数: {df_metrics['total_statements'].median():.1f}")
    
    report_content = "\n".join(report_lines)
    
    # 输出报告
    if output_file:
        output_path = Path(output_file)
        output_path.write_text(report_content, encoding='utf-8')
        print(f"[✓] 对比报告已保存到: {output_path}")
    else:
        default_output = results_dir / "comparison_report.txt"
        default_output.write_text(report_content, encoding='utf-8')
        print(f"[✓] 对比报告已保存到: {default_output}")
    
    # 在控制台显示简化版本
    print("\n" + report_content)


def main():
    parser = argparse.ArgumentParser(description="计算引用审计结果的性能指标")
    parser.add_argument("results_dir", help="结果目录路径 (包含各个arxiv_id子目录)")
    parser.add_argument(
        "--mode", 
        choices=["single", "batch", "compare"],
        default="batch",
        help="运行模式: single=单个文件, batch=批量汇总, compare=生成对比报告 (默认: batch)"
    )
    parser.add_argument(
        "--arxiv-id",
        help="单个文件模式下要分析的arxiv_id"
    )
    parser.add_argument(
        "--output",
        help="对比报告输出文件路径 (仅在compare模式下使用)"
    )
    parser.add_argument(
        "--force-recalculate",
        action="store_true",
        help="强制重新计算所有指标 (即使metrics.csv已存在)"
    )
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    
    if not results_dir.exists() or not results_dir.is_dir():
        print(f"[!] 结果目录不存在或不是目录: {results_dir}")
        return
    
    if args.mode == "single":
        if not args.arxiv_id:
            print(f"[!] 单个文件模式需要指定 --arxiv-id 参数")
            return
        
        file_dir = results_dir / args.arxiv_id
        if not file_dir.exists():
            print(f"[!] 找不到目录: {file_dir}")
            return
        
        # 强制重新计算或不存在metrics.csv时计算
        metrics_file = file_dir / "metrics.csv"
        if args.force_recalculate or not metrics_file.exists():
            metrics = calculate_file_metrics(file_dir, args.arxiv_id)
            if metrics is not None:
                save_file_metrics(metrics, file_dir)
            else:
                print(f"[!] 无法计算 {args.arxiv_id} 的指标，可能缺少关键文件")
        else:
            print(f"[✓] 指标文件已存在: {metrics_file}")
            # 读取并显示现有指标
            try:
                df_metrics = pd.read_csv(metrics_file)
                metrics = df_metrics.iloc[0].to_dict()
                print_file_summary(metrics)
            except Exception as e:
                print(f"[!] 读取现有指标文件失败: {e}")
    
    elif args.mode == "batch":
        # 如果需要强制重新计算，先删除现有的metrics.csv文件
        if args.force_recalculate:
            for subdir in results_dir.iterdir():
                if subdir.is_dir():
                    metrics_file = subdir / "metrics.csv"
                    if metrics_file.exists():
                        metrics_file.unlink()
                        print(f"[✓] 已删除现有指标文件: {metrics_file}")
        
        calculate_batch_metrics(results_dir)
    
    elif args.mode == "compare":
        generate_comparison_report(results_dir, args.output)


if __name__ == "__main__":
    main() 