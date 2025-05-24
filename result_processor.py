# ===============================
# core/result_processor.py - 结果处理器
# ===============================
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re
import math
from collections import defaultdict

from ..config.settings import settings
from ..utils.exceptions import MathGradingException

logger = logging.getLogger(__name__)

class ResultProcessor:
    """批改结果处理器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def process_raw_results(self, raw_results: Dict[str, Any], grade_level: str) -> Dict[str, Any]:
        """
        处理原始批改结果

        Args:
            raw_results: AI模型返回的原始结果
            grade_level: 年级水平

        Returns:
            处理后的结构化结果
        """
        try:
            processed_results = {
                "success": True,
                "grade_level": grade_level,
                "processed_at": datetime.now().isoformat(),
                "questions": [],
                "statistics": {},
                "recommendations": []
            }

            # 处理问题列表
            raw_questions = raw_results.get("questions", [])
            if not raw_questions:
                self.logger.warning("未找到问题数据")
                processed_results["success"] = False
                processed_results["error"] = "未识别到任何题目"
                return processed_results

            # 逐题处理
            for i, raw_question in enumerate(raw_questions):
                processed_question = self._process_single_question(raw_question, i + 1, grade_level)
                processed_results["questions"].append(processed_question)

            # 计算统计信息
            processed_results["statistics"] = self._calculate_statistics(processed_results["questions"])

            # 生成学习建议
            processed_results["recommendations"] = self._generate_recommendations(
                processed_results["questions"],
                processed_results["statistics"],
                grade_level
            )

            self.logger.info(f"结果处理完成，共处理 {len(processed_results['questions'])} 道题目")
            return processed_results

        except Exception as e:
            self.logger.error(f"结果处理失败: {e}")
            return {
                "success": False,
                "error": f"结果处理失败: {e}",
                "raw_results": raw_results
            }

    def _process_single_question(self, raw_question: Dict[str, Any], question_num: int, grade_level: str) -> Dict[str, Any]:
        """处理单个问题"""
        processed_question = {
            "question_id": f"q_{question_num}",
            "question_number": question_num,
            "question_text": self._clean_text(raw_question.get("question_text", "")),
            "student_answer": self._clean_text(raw_question.get("student_answer", "")),
            "correct_answer": self._clean_text(raw_question.get("correct_answer", "")),
            "raw_score": raw_question.get("score", 0),
            "max_score": raw_question.get("max_score", 10),
            "is_correct": raw_question.get("is_correct", False),
            "raw_feedback": raw_question.get("feedback", ""),
            "topic": self._identify_topic(raw_question.get("question_text", ""), grade_level),
            "difficulty": raw_question.get("difficulty", "medium"),
            "error_type": None,
            "processed_at": datetime.now().isoformat()
        }

        # 标准化分数
        processed_question["score"] = self._normalize_score(
            processed_question["raw_score"],
            processed_question["max_score"]
        )

        # 分析错误类型
        if not processed_question["is_correct"]:
            processed_question["error_type"] = self._analyze_error_type(
                processed_question["question_text"],
                processed_question["student_answer"],
                processed_question["correct_answer"]
            )

        # 增强反馈
        processed_question["enhanced_feedback"] = self._enhance_feedback(
            processed_question["raw_feedback"],
            processed_question["error_type"],
            processed_question["topic"]
        )

        return processed_question

    def _clean_text(self, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""

        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text.strip())

        # 修正常见的OCR错误
        text = text.replace('×', '×').replace('÷', '÷')
        text = text.replace('（', '(').replace('）', ')')

        return text

    def _identify_topic(self, question_text: str, grade_level: str) -> str:
        """识别题目所属知识点"""
        question_lower = question_text.lower()

        # 高中数学知识点关键词映射
        topic_keywords = {
            "函数": ["函数", "f(x)", "图像", "定义域", "值域", "单调", "奇偶"],
            "方程": ["方程", "解", "根", "x=", "求解"],
            "不等式": ["不等式", "≥", "≤", ">", "<", "大于", "小于"],
            "三角函数": ["sin", "cos", "tan", "三角", "角度", "弧度"],
            "数列": ["数列", "通项", "求和", "等差", "等比"],
            "立体几何": ["体积", "表面积", "棱锥", "棱柱", "球", "圆锥"],
            "平面几何": ["三角形", "圆", "直线", "角", "面积", "周长"],
            "概率统计": ["概率", "统计", "均值", "方差", "随机"],
            "导数": ["导数", "导函数", "极值", "切线", "单调性"],
            "积分": ["积分", "面积", "定积分", "不定积分"],
            "向量": ["向量", "坐标", "夹角", "数量积"],
            "复数": ["复数", "虚数", "实部", "虚部", "i"],
            "排列组合": ["排列", "组合", "阶乘", "C", "A"],
            "对数": ["对数", "log", "ln", "指数"]
        }

        # 匹配知识点
        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in question_text or keyword in question_lower:
                    return topic

        return "综合"

    def _normalize_score(self, raw_score: float, max_score: float) -> float:
        """标准化分数"""
        if max_score <= 0:
            return 0.0

        normalized = (raw_score / max_score) * 10  # 标准化到10分制
        return round(min(max(normalized, 0), 10), 1)

    def _analyze_error_type(self, question: str, student_answer: str, correct_answer: str) -> str:
        """分析错误类型"""
        if not student_answer.strip():
            return "未作答"

        question_lower = question.lower()
        student_lower = student_answer.lower()
        correct_lower = correct_answer.lower()

        # 计算错误类型
        if "计算" in question_lower or any(op in question for op in ['+', '-', '×', '÷']):
            # 数值比较
            if self._contains_numbers(student_answer) and self._contains_numbers(correct_answer):
                student_nums = self._extract_numbers(student_answer)
                correct_nums = self._extract_numbers(correct_answer)

                if student_nums and correct_nums:
                    if abs(student_nums[0] - correct_nums[0]) < 0.01:
                        return "表达方式错误"
                    else:
                        return "计算错误"
            return "计算错误"

        elif "方程" in question_lower:
            return "解法错误"

        elif "证明" in question_lower:
            return "逻辑错误"

        elif len(student_answer) < len(correct_answer) * 0.5:
            return "答案不完整"

        else:
            return "理解错误"

    def _contains_numbers(self, text: str) -> bool:
        """检查文本是否包含数字"""
        return bool(re.search(r'\d+(?:\.\d+)?', text))

    def _extract_numbers(self, text: str) -> List[float]:
        """从文本中提取数字"""
        numbers = re.findall(r'-?\d+(?:\.\d+)?', text)
        return [float(n) for n in numbers]

    def _enhance_feedback(self, raw_feedback: str, error_type: str, topic: str) -> str:
        """增强反馈内容"""
        enhanced_parts = []

        # 基础反馈
        if raw_feedback:
            enhanced_parts.append(raw_feedback)

        # 错误类型特定建议
        error_suggestions = {
            "计算错误": "建议：仔细检查计算步骤，使用草稿纸逐步计算。",
            "解法错误": "建议：回顾相关解题方法，注意解题步骤的逻辑性。",
            "理解错误": "建议：重新审题，理解题目要求，明确已知条件。",
            "未作答": "建议：即使不确定也要尝试作答，可以写出思路或部分步骤。",
            "答案不完整": "建议：检查答案是否完整，是否回答了题目的所有要求。",
            "表达方式错误": "建议：答案正确但表达不规范，注意数学表达的准确性。",
            "逻辑错误": "建议：注意推理的逻辑性，每一步都要有充分的依据。"
        }

        if error_type in error_suggestions:
            enhanced_parts.append(error_suggestions[error_type])

        # 知识点特定建议
        topic_suggestions = {
            "函数": "复习函数的基本概念和性质，多练习函数图像分析。",
            "方程": "掌握各类方程的标准解法，注意验根和解的完整性。",
            "三角函数": "熟记三角函数的基本公式和图像性质。",
            "导数": "理解导数的几何意义和物理意义，掌握求导法则。",
            "概率统计": "明确概率的定义和计算方法，注意实际问题的建模。"
        }

        if topic in topic_suggestions:
            enhanced_parts.append(f"知识点建议：{topic_suggestions[topic]}")

        return " ".join(enhanced_parts)

    def _calculate_statistics(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        if not questions:
            return {}

        total_questions = len(questions)
        correct_count = sum(1 for q in questions if q["is_correct"])
        total_score = sum(q["score"] for q in questions)
        max_total_score = sum(q["max_score"] for q in questions)

        # 按知识点统计
        topic_stats = defaultdict(lambda: {"total": 0, "correct": 0, "total_score": 0, "max_score": 0})

        for question in questions:
            topic = question["topic"]
            topic_stats[topic]["total"] += 1
            topic_stats[topic]["max_score"] += question["max_score"]
            topic_stats[topic]["total_score"] += question["score"]
            if question["is_correct"]:
                topic_stats[topic]["correct"] += 1

        # 错误类型统计
        error_types = defaultdict(int)
        for question in questions:
            if not question["is_correct"] and question["error_type"]:
                error_types[question["error_type"]] += 1

        # 难度分布
        difficulty_stats = defaultdict(lambda: {"total": 0, "correct": 0})
        for question in questions:
            difficulty = question["difficulty"]
            difficulty_stats[difficulty]["total"] += 1
            if question["is_correct"]:
                difficulty_stats[difficulty]["correct"] += 1

        return {
            "total_questions": total_questions,
            "correct_questions": correct_count,
            "wrong_questions": total_questions - correct_count,
            "accuracy_rate": round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0,
            "total_score": round(total_score, 2),
            "max_total_score": round(max_total_score, 2),
            "score_rate": round((total_score / max_total_score * 100), 2) if max_total_score > 0 else 0,
            "topic_breakdown": dict(topic_stats),
            "error_type_distribution": dict(error_types),
            "difficulty_distribution": dict(difficulty_stats)
        }

    def _generate_recommendations(self, questions: List[Dict[str, Any]], statistics: Dict[str, Any], grade_level: str) -> List[Dict[str, Any]]:
        """生成学习建议"""
        recommendations = []

        # 基于正确率的建议
        accuracy_rate = statistics.get("accuracy_rate", 0)

        if accuracy_rate >= 90:
            recommendations.append({
                "type": "praise",
                "priority": "low",
                "title": "表现优秀",
                "content": "你的答题准确率很高，基础掌握得很好！建议挑战一些更有难度的题目。",
                "actions": ["练习综合题", "尝试竞赛题目", "帮助同学答疑"]
            })
        elif accuracy_rate >= 70:
            recommendations.append({
                "type": "improvement",
                "priority": "medium",
                "title": "继续努力",
                "content": "基础还不错，但还有提升空间。重点关注错误题目的知识点。",
                "actions": ["复习错题", "强化练习", "向老师请教"]
            })
        else:
            recommendations.append({
                "type": "attention",
                "priority": "high",
                "title": "需要加强",
                "content": "基础知识掌握不够扎实，建议系统复习相关章节。",
                "actions": ["回顾教材", "基础练习", "寻求帮助"]
            })

        # 基于知识点的建议
        topic_breakdown = statistics.get("topic_breakdown", {})
        weak_topics = []

        for topic, stats in topic_breakdown.items():
            if stats["total"] > 0:
                topic_accuracy = (stats["correct"] / stats["total"]) * 100
                if topic_accuracy < 60:  # 正确率低于60%
                    weak_topics.append((topic, topic_accuracy))

        if weak_topics:
            weak_topics.sort(key=lambda x: x[1])  # 按正确率排序
            top_weak_topic = weak_topics[0][0]

            recommendations.append({
                "type": "focus",
                "priority": "high",
                "title": f"重点关注：{top_weak_topic}",
                "content": f"在{top_weak_topic}方面错误较多，建议重点复习这部分内容。",
                "actions": [f"复习{top_weak_topic}相关概念", f"练习{top_weak_topic}基础题", "总结常见题型"]
            })

        # 基于错误类型的建议
        error_distribution = statistics.get("error_type_distribution", {})
        if error_distribution:
            most_common_error = max(error_distribution.items(), key=lambda x: x[1])
            error_type, count = most_common_error

            error_advice = {
                "计算错误": {
                    "title": "提高计算准确性",
                    "content": "计算错误比较多，建议加强基本运算练习。",
                    "actions": ["每日计算练习", "使用草稿纸", "验算结果"]
                },
                "理解错误": {
                    "title": "加强题意理解",
                    "content": "审题不够仔细，建议多花时间理解题目要求。",
                    "actions": ["仔细审题", "画图辅助理解", "标记关键词"]
                },
                "解法错误": {
                    "title": "巩固解题方法",
                    "content": "解题方法有误，建议回顾标准解法。",
                    "actions": ["复习解题模板", "总结方法规律", "多练习类似题型"]
                }
            }

            if error_type in error_advice:
                advice = error_advice[error_type]
                recommendations.append({
                    "type": "method",
                    "priority": "medium",
                    "title": advice["title"],
                    "content": advice["content"],
                    "actions": advice["actions"]
                })

        return recommendations

class ScoreCalculator:
    """分数计算器"""

    @staticmethod
    def calculate_weighted_score(questions: List[Dict[str, Any]], weights: Dict[str, float] = None) -> float:
        """计算加权分数"""
        if not questions:
            return 0.0

        if not weights:
            weights = {"easy": 1.0, "medium": 1.2, "hard": 1.5}

        total_weighted_score = 0
        total_weight = 0

        for question in questions:
            difficulty = question.get("difficulty", "medium")
            weight = weights.get(difficulty, 1.0)
            score = question.get("score", 0)

            total_weighted_score += score * weight
            total_weight += weight

        return round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0

    @staticmethod
    def calculate_improvement_score(current_questions: List[Dict[str, Any]],
                                    previous_questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算进步分数"""
        if not current_questions or not previous_questions:
            return {"improvement": 0, "trend": "unknown"}

        current_accuracy = sum(1 for q in current_questions if q.get("is_correct", False)) / len(current_questions)
        previous_accuracy = sum(1 for q in previous_questions if q.get("is_correct", False)) / len(previous_questions)

        improvement = (current_accuracy - previous_accuracy) * 100

        if improvement > 5:
            trend = "improving"
        elif improvement < -5:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "improvement": round(improvement, 2),
            "trend": trend,
            "current_accuracy": round(current_accuracy * 100, 2),
            "previous_accuracy": round(previous_accuracy * 100, 2)
        }

class ReportGenerator:
    """报告生成器"""

    def __init__(self, result_processor: ResultProcessor):
        self.result_processor = result_processor
        self.logger = logging.getLogger(__name__)

    def generate_detailed_report(self, processed_results: Dict[str, Any]) -> str:
        """生成详细报告"""
        try:
            questions = processed_results.get("questions", [])
            statistics = processed_results.get("statistics", {})
            recommendations = processed_results.get("recommendations", [])

            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("数学作业批改详细报告")
            report_lines.append("=" * 60)
            report_lines.append("")

            # 基本信息
            report_lines.append("📊 基本统计")
            report_lines.append("-" * 30)
            report_lines.append(f"总题数: {statistics.get('total_questions', 0)}")
            report_lines.append(f"正确题数: {statistics.get('correct_questions', 0)}")
            report_lines.append(f"错误题数: {statistics.get('wrong_questions', 0)}")
            report_lines.append(f"正确率: {statistics.get('accuracy_rate', 0):.1f}%")
            report_lines.append(f"总分: {statistics.get('total_score', 0):.1f}/{statistics.get('max_total_score', 0):.1f}")
            report_lines.append(f"得分率: {statistics.get('score_rate', 0):.1f}%")
            report_lines.append("")

            # 知识点分析
            topic_breakdown = statistics.get("topic_breakdown", {})
            if topic_breakdown:
                report_lines.append("📚 知识点分析")
                report_lines.append("-" * 30)
                for topic, stats in topic_breakdown.items():
                    accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
                    report_lines.append(f"{topic}: {stats['correct']}/{stats['total']} ({accuracy:.1f}%)")
                report_lines.append("")

            # 错误分析
            error_distribution = statistics.get("error_type_distribution", {})
            if error_distribution:
                report_lines.append("❌ 错误类型分析")
                report_lines.append("-" * 30)
                for error_type, count in error_distribution.items():
                    report_lines.append(f"{error_type}: {count}次")
                report_lines.append("")

            # 详细题目分析
            report_lines.append("📝 详细题目分析")
            report_lines.append("-" * 30)
            for i, question in enumerate(questions, 1):
                status = "✓" if question["is_correct"] else "✗"
                report_lines.append(f"{i}. [{status}] {question['question_text'][:50]}...")
                report_lines.append(f"   学生答案: {question['student_answer']}")
                report_lines.append(f"   正确答案: {question['correct_answer']}")
                report_lines.append(f"   得分: {question['score']:.1f}/{question['max_score']:.1f}")
                if question.get("enhanced_feedback"):
                    report_lines.append(f"   反馈: {question['enhanced_feedback']}")
                report_lines.append("")

            # 建议
            if recommendations:
                report_lines.append("💡 学习建议")
                report_lines.append("-" * 30)
                for i, rec in enumerate(recommendations, 1):
                    report_lines.append(f"{i}. {rec['title']}")
                    report_lines.append(f"   {rec['content']}")
                    if rec.get("actions"):
                        report_lines.append(f"   建议行动: {', '.join(rec['actions'])}")
                    report_lines.append("")

            report_lines.append("=" * 60)
            report_lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("=" * 60)

            return "\n".join(report_lines)

        except Exception as e:
            self.logger.error(f"生成详细报告失败: {e}")
            return f"报告生成失败: {e}"