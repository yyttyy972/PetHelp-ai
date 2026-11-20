
from app.ai.retriever import search_rules

print("===== 邻宠帮 AI 规则检索助手 =====")
print("输入 exit 退出")

while True:
    question = input("\n请输入你的问题：")

    if question.strip().lower() == "exit":
        break

    results = search_rules(question, top_k=3)

    if not results:
        print("\n没有找到相关业务规则。")
        continue

    print(f"\n找到 {len(results)} 条相关规则：")

    for index, rule in enumerate(results, 1):
        print(f"\n----- 结果 {index} -----")
        print(rule)
