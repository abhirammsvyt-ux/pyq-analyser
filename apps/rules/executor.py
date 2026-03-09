"""
Safe rule executor - Executes compiled rules in a sandboxed environment.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RuleExecutor:
    """Safely executes compiled classification rules."""
    
    # Allowed built-in functions
    SAFE_BUILTINS = {
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'any': any,
        'all': all,
        'min': min,
        'max': max,
        'sum': sum,
        'sorted': sorted,
        'reversed': reversed,
        'True': True,
        'False': False,
        'None': None,
    }
    
    def execute(self, rule, context: Dict[str, Any]) -> Optional[bool]:
        """
        Execute a compiled rule with the given context.
        
        Args:
            rule: ClassificationRule instance with compiled_code
            context: Dictionary with question_text, keywords, marks
            
        Returns:
            True/False if rule matches, None if execution failed
        """
        if not rule.compiled_code:
            logger.warning(f"Rule {rule.name} has no compiled code")
            return None
        
        try:
            # Create restricted global namespace
            restricted_globals = {
                '__builtins__': self.SAFE_BUILTINS,
            }
            
            # Execute the function definition
            exec(rule.compiled_code, restricted_globals)
            
            # Get the check_rule function
            check_rule = restricted_globals.get('check_rule')
            if not callable(check_rule):
                logger.error(f"Rule {rule.name}: check_rule is not callable")
                return None
            
            # Execute with context
            result = check_rule(
                context.get('question_text', ''),
                context.get('keywords', []),
                context.get('marks')
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Rule execution failed for {rule.name}: {e}")
            return None
    
    def execute_all(self, rules, context: Dict[str, Any]) -> Dict[str, bool]:
        """
        Execute multiple rules and return results.
        
        Returns:
            Dictionary mapping rule IDs to results
        """
        results = {}
        for rule in rules:
            if rule.is_active and rule.is_validated:
                result = self.execute(rule, context)
                if result is not None:
                    results[str(rule.id)] = result
        return results
