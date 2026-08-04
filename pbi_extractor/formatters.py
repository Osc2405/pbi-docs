"""
Utilities for cleaning and advanced formatting of DAX expressions.
Includes advanced regex, multiline blocks and intelligent indentation.
"""

import re
from typing import Any


def clean_dax_expression(expression: Any) -> str:
    """Cleans DAX expressions for better readability."""
    if not expression:
        return ""
    if isinstance(expression, list):
        expression = " ".join(str(item) for item in expression)
    expression = str(expression)
    lines = expression.split("\n")
    cleaned_lines = []
    for line in lines:
        cleaned_line = line.rstrip()
        if cleaned_line:
            cleaned_lines.append(cleaned_line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def format_dax_expression(expression: str) -> str:
    """Formats DAX expressions with advanced indentation and multiline blocks.
    
    Args:
        expression: DAX expression to format
        
    Returns:
        str: DAX expression formatted with intelligent indentation
    """
    if not expression or not expression.strip():
        return ""
    
    # Clean initial expression
    cleaned = clean_dax_expression(expression)
    
    # Use simpler and more robust formatting
    formatted = _format_dax_simple(cleaned)
    
    return formatted.strip()


def _format_dax_simple(expression: str) -> str:
    """DAX formatting with improved visual indentation and parenthesis alignment."""
    import re
    
    # Patterns for complex functions with visual indentation
    complex_patterns = [
        (r'\b(CALCULATE)\s*\(', r'\1(\n    '),
        (r'\b(IF)\s*\(', r'\1(\n    '),
        (r'\b(SWITCH)\s*\(', r'\1(\n    '),
        (r'\b(FILTER)\s*\(', r'\1(\n    '),
        (r'\b(TOTALYTD)\s*\(', r'\1(\n    '),
        (r'\b(TOTALQTD)\s*\(', r'\1(\n    '),
        (r'\b(TOTALMTD)\s*\(', r'\1(\n    '),
        (r'\b(SAMEPERIODLASTYEAR)\s*\(', r'\1(\n    '),
        (r'\b(DATESYTD)\s*\(', r'\1(\n    '),
        (r'\b(DIVIDE)\s*\(', r'\1(\n    '),
    ]
    
    formatted = expression
    
    # Apply complex function patterns
    for pattern, replacement in complex_patterns:
        formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
    
    # Format commas in complex functions (only if there are multiple arguments)
    formatted = re.sub(r',\s*', ',\n    ', formatted)
    
    # Improve closing parenthesis formatting with visual alignment
    formatted = _align_closing_parentheses(formatted)
    
    # Clean multiple empty lines
    formatted = re.sub(r'\n\s*\n', '\n', formatted)
    
    return formatted


def _align_closing_parentheses(formatted: str) -> str:
    """Aligns closing parentheses with the start of the corresponding function."""
    lines = formatted.split('\n')
    result_lines = []
    indent_stack = []  # Stack to track indentation levels and function names
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        current_indent = len(line) - len(line.lstrip())
        
        # If it's a complex function, add to stack
        if _is_complex_function_line(stripped):
            indent_stack.append({
                'indent': current_indent,
                'function': stripped.split('(')[0],
                'line_num': i
            })
            result_lines.append(line)
        
        # If it's a closing parenthesis, align with the corresponding function
        elif stripped == ')':
            if indent_stack:
                # Get the indentation level of the corresponding function
                function_info = indent_stack.pop()
                function_indent = function_info['indent']
                
                # Align the closing parenthesis with the start of the function
                aligned_line = ' ' * function_indent + ')'
                result_lines.append(aligned_line)
            else:
                result_lines.append(line)
        
        # If it's a normal line, keep it
        else:
            result_lines.append(line)
    
    return '\n'.join(result_lines)


def _is_complex_function_line(line: str) -> bool:
    """Determines if a line is the start of a complex function."""
    stripped = line.strip()
    complex_functions = [
        'CALCULATE(', 'IF(', 'SWITCH(', 'FILTER(', 'TOTALYTD(', 
        'TOTALQTD(', 'TOTALMTD(', 'SAMEPERIODLASTYEAR(', 'DATESYTD(', 'DIVIDE('
    ]
    
    for func in complex_functions:
        if stripped.upper().startswith(func):
            return True
    
    return False


def format_dax_for_documentation(expression: str) -> str:
    """Formats DAX specifically for Markdown documentation.
    
    Args:
        expression: DAX expression to format
        
    Returns:
        str: DAX formatted for Markdown with syntax highlighting
    """
    formatted = format_dax_expression(expression)
    
    # Escape special characters for Markdown
    formatted = formatted.replace('\\', '\\\\')
    formatted = formatted.replace('`', '\\`')
    
    return formatted


def format_dax_for_json(expression: str) -> str:
    """Formats DAX specifically for JSON output.
    
    Args:
        expression: DAX expression to format
        
    Returns:
        str: DAX formatted for JSON (escaped)
    """
    formatted = format_dax_expression(expression)
    
    # Escape special characters for JSON
    formatted = formatted.replace('\\', '\\\\')
    formatted = formatted.replace('"', '\\"')
    formatted = formatted.replace('\n', '\\n')
    formatted = formatted.replace('\t', '\\t')
    
    return formatted


def get_dax_complexity_score(expression: str) -> int:
    """Calculates a complexity score for DAX expressions.
    
    Args:
        expression: DAX expression to analyze
        
    Returns:
        int: Complexity score (higher = more complex)
    """
    if not expression:
        return 0
    
    score = 0
    
    # Complex functions
    complex_functions = ['IF', 'SWITCH', 'CALCULATE', 'FILTER', 'ALL', 'VALUES']
    for func in complex_functions:
        score += expression.upper().count(func) * 3
    
    # Operators
    operators = ['+', '-', '*', '/', '=', '<', '>', '!']
    for op in operators:
        score += expression.count(op)
    
    # Nested parentheses
    max_nesting = 0
    current_nesting = 0
    for char in expression:
        if char == '(':
            current_nesting += 1
            max_nesting = max(max_nesting, current_nesting)
        elif char == ')':
            current_nesting -= 1
    
    score += max_nesting * 2
    
    # Length
    score += len(expression) // 50
    
    return score


def categorize_dax_complexity(expression: str) -> str:
    """Categorizes the complexity of a DAX expression.
    
    Args:
        expression: DAX expression to categorize
        
    Returns:
        str: Complexity category ('simple', 'medium', 'complex')
    """
    score = get_dax_complexity_score(expression)
    
    if score <= 5:
        return 'simple'
    elif score <= 15:
        return 'medium'
    else:
        return 'complex'
