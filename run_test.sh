# Web OpenAI Deep Research
python openai_processor.py --input=v1.0-openai-721-collected --output=v1.0-openai-721-collected-parsed --markdown
python statement_evaluator.py v1.0-openai-721-collected-parsed --output-dir v1.0-openai-721-collected-parsed-stat-results
python related_work_evaluator.py --survey-dir v1.0-openai-721-collected-parsed --ground-truth-dir ReportBench_v1.1_GT --result-dir v1.0-openai-721-collected-parsed-related-work-results
python metrics_calculator.py v1.0-openai-721-collected-parsed-stat-results

# Web Gemini Deep Research
python related_work_evaluator.py --survey-dir v1.0-gemini-722-collected-parsed --ground-truth-dir ReportBench_v1.1_GT --result-dir v1.0-gemini-722-collected-parsed-related-work-results
python statement_evaluator.py v1.0-gemini-722-collected-parsed --output-dir v1.0-gemini-722-collected-parsed-stat-results
python metrics_calculator.py v1.0-gemini-722-collected-parsed-stat-results


python related_work_evaluator.py --survey-dir zy_3m_3sample/gcp-claude4-opus --ground-truth-dir ReportBench_v1.1_GT --result-dir zy_3m_3sample_results/gcp-claude4-opus-related-work-results
python statement_evaluator.py zy_3m_3sample/gcp-claude4-opus --output-dir zy_3m_3sample_results/gcp-claude4-opus-stat-results
python metrics_calculator.py zy_3m_3sample_results/gcp-claude4-opus-stat-results

python related_work_evaluator.py --survey-dir zy_3m_3sample/gemini-2.5-pro-preview-05-06 --ground-truth-dir ReportBench_v1.1_GT --result-dir zy_3m_3sample_results/gemini-2.5-pro-preview-05-06-related-work-results
python statement_evaluator.py zy_3m_3sample/gemini-2.5-pro-preview-05-06 --output-dir zy_3m_3sample_results/gemini-2.5-pro-preview-05-06-stat-results
python metrics_calculator.py zy_3m_3sample_results/gemini-2.5-pro-preview-05-06-stat-results

python related_work_evaluator.py --survey-dir zy_3m_3sample/o4-mini-2025-04-16 --ground-truth-dir ReportBench_v1.1_GT --result-dir zy_3m_3sample_results/o4-mini-2025-04-16-related-work-results
python statement_evaluator.py zy_3m_3sample/o4-mini-2025-04-16 --output-dir zy_3m_3sample_results/o4-mini-2025-04-16-stat-results
python metrics_calculator.py zy_3m_3sample_results/o4-mini-2025-04-16-stat-results

python related_work_evaluator.py --survey-dir zy_3m_3sample/o3-2025-04-16 --ground-truth-dir ReportBench_v1.1_GT --result-dir zy_3m_3sample_results/o3-2025-04-16-related-work-results
python statement_evaluator.py zy_3m_3sample/o3-2025-04-16 --output-dir zy_3m_3sample_results/o3-2025-04-16-stat-results
python metrics_calculator.py zy_3m_3sample_results/o3-2025-04-16-stat-results