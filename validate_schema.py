import json
from pathlib import Path
from jsonschema import Draft202012Validator

# 读取 Schema
with open("docs/week9/ai-parse-schema.json",
          "r", encoding="utf-8") as f:
    schema = json.load(f)

# 读取测试数据
with open("docs/week9/manual-test-case.json",
          "r", encoding="utf-8") as f:
    data = json.load(f)

# 检查 Schema 自身是否合法
Draft202012Validator.check_schema(schema)

# 校验测试数据
validator = Draft202012Validator(schema)
errors = list(validator.iter_errors(data))

if errors:
    print("FAIL：数据不符合 Schema")
    for error in errors:
        print(error.message)
else:
    print("PASS：数据符合 Schema")