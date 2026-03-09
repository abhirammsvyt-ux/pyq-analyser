"""
Rule compiler - Converts natural language rules to Python code using LLM.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RuleCompiler:
    """Compiles natural language rules to executable Python code."""
    
    COMPILE_PROMPT = """
You are a Python code generator. Convert the following natural language classification rule 
into a Python function that returns True if a question matches the rule.

Rule Type: {rule_type}
Natural Language Rule: {natural_language}

Available context variables:
- question_text: str - The full question text
- keywords: list[str] - List of keywords extracted from the question
- marks: int | None - Marks allocated to the question

Generate ONLY a Python function with this signature:
def check_rule(question_text: str, keywords: list, marks: int | None) -> bool:
    # Your implementation
    return True/False

Return ONLY the function code, no explanations.
"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def compile(self, rule) -> Tuple[bool, str, Optional[str]]:
        """
        Compile a natural language rule to Python code.
        
        Returns:
            (success, compiled_code, error_message)
        """
        try:
            prompt = self.COMPILE_PROMPT.format(
                rule_type=rule.get_rule_type_display(),
                natural_language=rule.natural_language
            )
            
            response = self.llm_client.generate(prompt)
            code = self._extract_code(response)
            
            # Validate the generated code
            is_valid, error = self._validate_code(code)
            if not is_valid:
                return False, '', error
            
            return True, code, None
            
        except Exception as e:
            logger.error(f"Rule compilation failed: {e}")
            return False, '', str(e)
    
    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Remove markdown code blocks if present
        code = response.strip()
        if code.startswith('```python'):
            code = code[9:]
        elif code.startswith('```'):
            code = code[3:]
        if code.endswith('```'):
            code = code[:-3]
        return code.strip()
    
    def _validate_code(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate that the generated code is safe and well-formed."""
        # Check for dangerous patterns
        dangerous_patterns = [
            'import os', 'import sys', 'import subprocess',
            '__import__', 'eval(', 'exec(', 'open(',
            'file(', 'input(', 'raw_input('
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                return False, f"Unsafe pattern detected: {pattern}"
        
        # Try to compile the code
        try:
            compile(code, '<rule>', 'exec')
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        # Check that the function signature is correct
        if 'def check_rule(' not in code:
            return False, "Missing check_rule function"
        
        return True, None
