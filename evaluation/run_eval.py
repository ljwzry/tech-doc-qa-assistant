"""RAG 评估脚本 — 检索准确率 + 回答质量评估

不依赖 RAGAS，直接计算核心指标：
- Hit@K: 检索结果中包含 ground_truth 关键词的比例
- MRR: 平均 reciprocal rank
- Context Precision: 检索结果相关性
- Faithfulness (简化版): 回答中关键词出现在上下文中的比例
"""
import json
import os
import re
from datetime import datetime
from app.rag.hybrid_retriever import hybrid_search
from app.agent.graph import build_graph
from langchain_core.messages import HumanMessage
from evaluation.eval_dataset import EVAL_DATASET


def compute_hit_at_k(results, ground_truth, k=5):
    """Hit@K: 前 K 条结果中是否包含正确答案关键词"""
    top_k = results[:k]
    gt_words = set(re.findall(r'[\w]+', ground_truth.lower()))
    hit = False
    for r in top_k:
        text = r.get("text", "").lower()
        if any(w in text for w in gt_words if len(w) > 1):
            hit = True
            break
    return 1.0 if hit else 0.0


def compute_mrr(results, ground_truth, k=10):
    """MRR: 平均 reciprocal rank"""
    gt_words = set(re.findall(r'[\w]+', ground_truth.lower()))
    for i, r in enumerate(results[:k]):
        text = r.get("text", "").lower()
        if any(w in text for w in gt_words if len(w) > 1):
            return 1.0 / (i + 1)
    return 0.0


def compute_context_precision(results, ground_truth, k=5):
    """Context Precision: 前 K 条结果中相关文档的比例"""
    top_k = results[:k]
    gt_words = set(re.findall(r'[\w]+', ground_truth.lower()))
    relevant = 0
    for r in top_k:
        text = r.get("text", "").lower()
        if any(w in text for w in gt_words if len(w) > 1):
            relevant += 1
    return relevant / len(top_k) if top_k else 0.0


def compute_faithfulness(answer, contexts):
    """简化版 Faithfulness: 回答中的关键词是否出现在上下文中"""
    if not answer or not contexts:
        return 0.0
    answer_words = set(re.findall(r'[\w]+', answer.lower()))
    answer_words = {w for w in answer_words if len(w) > 2}
    if not answer_words:
        return 1.0
    context_combined = " ".join(contexts).lower()
    grounded = sum(1 for w in answer_words if w in context_combined)
    return grounded / len(answer_words)


def compute_answer_relevancy(answer, question):
    """简化版 Answer Relevancy: 回答是否包含问题中的关键词"""
    if not answer:
        return 0.0
    q_words = set(re.findall(r'[\w]+', question.lower()))
    q_words = {w for w in q_words if len(w) > 1}
    if not q_words:
        return 1.0
    answer_lower = answer.lower()
    covered = sum(1 for w in q_words if w in answer_lower)
    return covered / len(q_words)


def run_evaluation():
    graph = build_graph()
    all_metrics = {
        "hit_at_1": [],
        "hit_at_3": [],
        "hit_at_5": [],
        "mrr": [],
        "context_precision": [],
        "faithfulness": [],
        "answer_relevancy": [],
    }

    print(f"\n开始评估，共 {len(EVAL_DATASET)} 条测试数据...\n")

    for i, item in enumerate(EVAL_DATASET, 1):
        q = item["question"]
        gt = item["ground_truth"]
        print(f"  [{i}/{len(EVAL_DATASET)}] {q[:50]}...", end="", flush=True)

        try:
            # 1. 检索
            results = hybrid_search(q, top_k=5)
            contexts = [r["text"] for r in results] if results else []

            # 2. 生成回答
            graph_input = {
                "messages": [HumanMessage(content=q)],
                "query": q,
                "retrieved_docs": [],
                "retries": 0,
            }
            graph_result = graph.invoke(graph_input)
            answer = graph_result["messages"][-1].content

            # 3. 计算指标
            all_metrics["hit_at_1"].append(compute_hit_at_k(results, gt, k=1))
            all_metrics["hit_at_3"].append(compute_hit_at_k(results, gt, k=3))
            all_metrics["hit_at_5"].append(compute_hit_at_k(results, gt, k=5))
            all_metrics["mrr"].append(compute_mrr(results, gt))
            all_metrics["context_precision"].append(compute_context_precision(results, gt))
            all_metrics["faithfulness"].append(compute_faithfulness(answer, contexts))
            all_metrics["answer_relevancy"].append(compute_answer_relevancy(answer, q))

            print(" ✓")
        except Exception as e:
            print(f" ✗ ({e})")
            for key in all_metrics:
                all_metrics[key].append(0.0)

    # 汇总
    summary = {}
    for key, values in all_metrics.items():
        summary[key] = round(sum(values) / len(values), 4) if values else 0.0

    print("\n" + "=" * 60)
    print("RAG 评估结果")
    print("=" * 60)
    print(f"  Hit@1 (检索命中率)       : {summary['hit_at_1']:.4f}")
    print(f"  Hit@3 (前3条命中率)      : {summary['hit_at_3']:.4f}")
    print(f"  Hit@5 (前5条命中率)      : {summary['hit_at_5']:.4f}")
    print(f"  MRR (平均倒数排名)       : {summary['mrr']:.4f}")
    print(f"  Context Precision        : {summary['context_precision']:.4f}")
    print(f"  Faithfulness (忠实度)    : {summary['faithfulness']:.4f}")
    print(f"  Answer Relevancy (相关性): {summary['answer_relevancy']:.4f}")

    overall_retrieval = (summary["hit_at_3"] + summary["mrr"]) / 2
    overall_quality = (summary["faithfulness"] + summary["answer_relevancy"]) / 2
    print("-" * 60)
    print(f"  综合检索准确率           : {overall_retrieval:.4f}")
    print(f"  综合回答质量             : {overall_quality:.4f}")

    # 保存结果
    os.makedirs("evaluation/results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "timestamp": ts,
        "total_questions": len(EVAL_DATASET),
        "metrics": summary,
        "overall_retrieval_accuracy": round(overall_retrieval, 4),
        "overall_answer_quality": round(overall_quality, 4),
    }
    filepath = f"evaluation/results/eval_{ts}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {filepath}")

    return output


if __name__ == "__main__":
    run_evaluation()
