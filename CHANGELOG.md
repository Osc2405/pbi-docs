# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-XX

### Added
- **Modular project structure**: Complete refactoring of monolithic code into specialized modules
  - `extractor.py`: DataModelSchema extraction from .pbit files with robust validations
  - `processor.py`: Model processing with error handling and validations
  - `formatters.py`: Advanced DAX formatting with regex, tokenization and intelligent indentation
  - `categorizer.py`: Intelligent categorization of tables, columns and measures
  - `documentation.py`: Markdown documentation generation with formatted DAX and complexity
  - `diff.py`: Model comparison and diff generation
  - `cli.py`: Complete CLI with logging, validations and error handling
  - `jsonl_generator.py`: JSONL context generator for LLMs with optimized DAX

- **Advanced hierarchical DAX formatting**: Complete visual indentation system that reflects logical structure
  - Incremental indentation (+4 spaces) for each nesting level
  - Automatic alignment of closing parentheses with the start of their function
  - Arguments on separate lines for maximum readability
  - Recognition of complex functions: `CALCULATE`, `FILTER`, `SUMX`, `AVERAGEX`, `DIVIDE`, `TOTALYTD`, `TOTALQTD`, `TOTALMTD`, `SAMEPERIODLASTYEAR`, `DATESYTD`
  - Intelligent tokenization with recognition of functions, operators and columns
  - Complexity categorization (simple/medium/complex) with automatic scoring
  - Specific formatting for Markdown and JSON with appropriate escaping
  - Visual complexity indicators in documentation (Simple/Medium/Complex)

- **Robust validations and error handling**: Complete validation and logging system
  - Input file validation (valid .pbit files, non-empty, existing)
  - Schema structure validation (required keys, correct types)
  - Specific error handling with custom exceptions
  - Configurable logging system with levels (INFO/DEBUG)
  - Warnings for problematic elements without interrupting processing

- **JSONL generator for LLMs**: Format optimized for embeddings and RAG
  - Context per table with columns and example prompts
  - Context per measure with formatted DAX expressions
  - Context per relationship with cardinality and filtering
  - General model context with executive summary

- **Enhanced CLI with multiple modes**:
  - `--input/-i`: Individual file processing
  - `--output/-o`: Customizable base output directory
  - `--batch`: Batch processing with glob patterns
  - `--diff`: Comparison between two models with JSON diff generation
  - `--lang` / `--language`: Multi-language support (English/Spanish) for documentation generation

- **Professional Python packaging**:
  - `pyproject.toml` with complete project metadata
  - Console entry point: `pbi-docs`
  - Editable installation: `pip install -e .`
  - Package structure: `pbi_extractor/`

- **Cross-platform paths**: Complete migration to `pathlib.Path`
  - Removal of Windows-specific paths (`r"data\..."`)
  - Native support for Windows, Linux and macOS

- **Intelligent measure categorization**:
  - Revenue, Cost, Margin, Percentage, Ratio
  - Temporal, Calendar Intelligence, Aggregation
  - Filtering and Other

- **Multi-language support**: Generate documentation in English (`--lang en`) or Spanish (`--lang es`). English is the default language.
  - New CLI flag `--lang` or `--language` to select documentation language
  - All documentation strings (headers, labels, category names, complexity indicators) are translated
  - `model_documentation.md` and `agent_context.json` are generated in the selected language
  - New `i18n.py` module with translation dictionaries for English and Spanish
  - Complete translation coverage for all user-facing strings

- **Improved automatic documentation**:
  - Structured Markdown with tables and DAX code
  - Measure grouping by category with icons
  - Usage guide for AI agents
  - JSON context for APIs and integrations

- **Robust DataModelSchema parsing**:
  - Automatic fallback to search for "DataModelSchema", "DataModel" or "model.json"
  - Support for different naming conventions in .pbit files
  - Better handling of non-standard schemas

### Changed
- **Project renaming**: Complete migration from "ConectorBI" to "pbi-docs"
  - CLI command changed from `pbi-extractor` to `pbi-docs`
  - All documentation and references updated to reflect new project name
  - GitHub URLs and project metadata updated

- **Complete refactoring of DAX formatter** (`formatters.py`):
  - New `_format_dax_simple()` function with regex-based logic and indentation stack
  - New `_align_closing_parentheses()` function for precise parenthesis alignment
  - Improved `_is_complex_function_line()` to detect more nested functions
  - Clear separation between formatting for documentation and JSON
  - Stack-based indentation tracking for precise level handling
  - Robust regex for function and argument tokenization
  - Special handling of column references with brackets
  - Preservation of comments and string literals

- **File restriction**: Only support for `.pbit` (not `.pbix`)
  - Clear error with instructions to export from Power BI Desktop
  - Better handling of unsupported files

- **Output structure**: Organization by input file
  - `output/[file-name].pbit/metadata.json`
  - `output/[file-name].pbit/model_documentation.md`
  - `output/[file-name].pbit/agent_context.json`
  - `output/[file-name].pbit/model_context.jsonl`

- **Relative imports**: Complete migration to package imports
  - `from .module import function` instead of absolute imports
  - Better encapsulation and code organization

- **Improved generated documentation**:
  - DAX expressions now clearly show the hierarchy of nested functions
  - Each nesting level is visually distinguishable
  - Closing parentheses align with the start of their corresponding function

### Fixed
- **DAX argument preservation**: Critical fix where the first argument of complex functions was omitted during formatting
  - Previously: `CALCULATE( , SAMEPERIODLASTYEAR(...))` (incorrect)
  - Now: `CALCULATE( [YTD Gross Margin], SAMEPERIODLASTYEAR(...))` (correct)
  
- **Flat indentation**: Fixed indentation levels that did not reflect logical hierarchy
  - All internal arguments now increase their indentation according to nesting depth
  - Closing parentheses maintain visual consistency with their opening

- **Encoding handling**: Robust support for UTF-8, UTF-16 and Latin-1
- **JSON parsing**: Automatic cleanup of comments and trailing commas
- **Column categorization**: Better detection of types and categories

### Testing
- **Test suite**: Unit tests for categorizer, processor, and internationalization modules using pytest
  - Tests for technical table detection (`test_categorizer.py`)
  - Tests for schema processing and context generation (`test_processor_and_context.py`)
  - Tests for internationalization module (`test_i18n.py`)
  - Test coverage for measure categorization and column category detection
  - Tests for translation functions (`get_translation`, `get_category_name`, `get_complexity_label`)
  - Tests for translation completeness and non-empty translations
  - Tests for Spanish language support in documentation generation
- **Testing framework**: pytest >= 7.0.0 configured in `requirements-dev.txt`

### Documentation
- **Complete README.md**: Installation, usage and examples guide
  - All content translated to English
  - All emojis replaced with descriptive text
  - Added reference to Microsoft Power BI Desktop Samples repository
  - Updated examples to use "Life expectancy v202009" sample file
  - New "DAX Formatting Example" section with before/after comparison
  - Updated features table with "Advanced DAX Formatting"
  - Improved comparison table with "Advanced DAX formatting" column
  - Updated CLI and usage instructions
  - JSONL output examples for LLM integration
- **Project badges**: Python version, License, Platform
- **Comparison section**: With Tabular Editor, DAX Studio, Power BI Desktop
- **Use cases**: Automatic documentation, onboarding, auditing, AI integration
- **Contribution guide**: Development process and bug reporting
- **MIT License**: LICENSE file with terms of use
- **CHANGELOG.md**: Fully translated to English

### Architecture
- **Separation of concerns**: Each module with specific function
- **Clear interfaces**: Well-documented functions with type hints
- **Extensibility**: Structure prepared for future features
- **Testing ready**: Modular code facilitating unit tests

---

## [Unreleased]

### Planned
- Native `.pbix` file support
- CLI with additional arguments (`--verbose`, `--quiet`, `--format`)
- Expanded test coverage for all modules (extractor, formatters, documentation, i18n)
- PII/sensitive column detection
- Automatic ER diagram generation
- Support for Qlik Sense (.qvf) and Tableau (.twb)
- REST API for web service integration
- Plugin for VS Code and Power BI Desktop
- Export to PDF and interactive HTML
- DAX measure performance analysis
- Detection of duplicate or similar measures
