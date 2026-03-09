"""
LLM prompts for various tasks.
"""

# Question extraction prompt
EXTRACT_QUESTIONS_PROMPT = """
Extract all questions from the following text. For each question, identify:
1. Question number
2. Full question text
3. Marks (if mentioned)

Text:
{text}

Return the questions in JSON format:
[
  {{"number": "1", "text": "...", "marks": 5}},
  ...
]
"""

# Module classification prompt
CLASSIFY_MODULE_PROMPT = """
You are a question classifier for academic subjects.

Subject: {subject_name}
Available Modules:
{modules}

Question: {question}

Which module does this question belong to? 
Respond with ONLY the module number (1, 2, 3, etc.) or 0 if unsure.
"""

# Topic extraction prompt
EXTRACT_TOPICS_PROMPT = """
Extract the main topics/concepts from this academic question.

Question: {question}

List up to 5 key topics, one per line. Be specific and concise.
"""

# Rule compilation prompt
COMPILE_RULE_PROMPT = """
Convert this natural language classification rule into a Python function.

Rule: {rule_text}

Generate a function with this signature:
def check_rule(question_text: str, keywords: list, marks: int | None) -> bool:
    # Implementation
    return True/False

Return ONLY the Python function code.
"""

# Difficulty estimation prompt
ESTIMATE_DIFFICULTY_PROMPT = """
Estimate the difficulty of this academic question.

Question: {question}
Marks: {marks}

Consider:
- Cognitive demand (recall, application, analysis, synthesis)
- Number of steps required
- Complexity of concepts

Respond with ONLY one word: easy, medium, or hard
"""

# Bloom's taxonomy prompt
CLASSIFY_BLOOM_PROMPT = """
Classify this question according to Bloom's Taxonomy:
- Remember: Recall facts and basic concepts
- Understand: Explain ideas or concepts
- Apply: Use information in new situations
- Analyze: Draw connections among ideas
- Evaluate: Justify a decision
- Create: Produce new or original work

Question: {question}

Respond with ONLY one word: remember, understand, apply, analyze, evaluate, or create
"""
