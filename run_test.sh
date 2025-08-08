# Web OpenAI Deep Research
python openai_processor.py --input=openai-web-results --output=openai-web-results-parsed --markdown
python statement_evaluator.py openai-web-results-parsed --output-dir openai-web-results-parsed-stat-results
python related_work_evaluator.py --survey-dir openai-web-results-parsed --ground-truth-dir ReportBench_v1.1_GT --result-dir openai-web-results-parsed-related-work-results
python metrics_calculator.py openai-web-results-parsed-stat-results

# Web Gemini Deep Research
python related_work_evaluator.py --survey-dir gemini-web-results-parsed --ground-truth-dir ReportBench_v1.1_GT --result-dir gemini-web-results-parsed-related-work-results
python statement_evaluator.py gemini-web-results-parsed --output-dir gemini-web-results-parsed-stat-results
python metrics_calculator.py gemini-web-results-parsed-stat-results


python related_work_evaluator.py --survey-dir gemini-2.5-pro-preview-05-06 --ground-truth-dir ReportBench_v1.1_GT --result-dir results/gemini-2.5-pro-preview-05-06-related-work-results
python statement_evaluator.py gemini-2.5-pro-preview-05-06 --output-dir results/gemini-2.5-pro-preview-05-06-stat-results
python metrics_calculator.py results/gemini-2.5-pro-preview-05-06-stat-results

python related_work_evaluator.py --survey-dir o3 --ground-truth-dir ReportBench_v1.1_GT --result-dir results/o3-related-work-results
python statement_evaluator.py o3 --output-dir results/o3-stat-results
python metrics_calculator.py results/o3-stat-results