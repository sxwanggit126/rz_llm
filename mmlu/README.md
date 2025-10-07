# 接口使用

```shell
# 获取可用模型列表
curl -X GET "http://localhost:8000/evaluation/models" \
  -H "accept: application/json"

# 获取可用Prompt类型
curl -X GET "http://localhost:8000/evaluation/prompt-types" \
  -H "accept: application/json"

# 启动评估任务
curl -X POST "http://localhost:8000/evaluation/start" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "subjects": ["astronomy", "business_ethics"],
    "models": ["gpt-3.5-turbo", "gpt-4.1-nano"],
    "prompt_types": ["zero_shot", "zero_shot_cot", "few_shot", "few_shot_cot"],
    "data_count_per_subject": 10
  }'

# 查询评估任务状态（需要替换task_id）
# 从上面的响应中获取task_id，例如：12345678-1234-1234-1234-123456789abc
curl -X GET "http://localhost:8000/evaluation/status/79b03e9f-8d8f-47c9-8fe8-db3ca3a4c9a8" \
  -H "accept: application/json"

# 获取评估结果（需要替换task_id）
curl -X GET "http://localhost:8000/evaluation/results/79b03e9f-8d8f-47c9-8fe8-db3ca3a4c9a8/details" \
  -H "accept: application/json"

# 获取详细评估结果（需要替换task_id）
curl -X GET "http://localhost:8000/evaluation/results/12345678-1234-1234-1234-123456789abc/details" \
  -H "accept: application/json"

# 列出所有评估任务
curl -X GET "http://localhost:8000/evaluation/tasks" \
  -H "accept: application/json"
```