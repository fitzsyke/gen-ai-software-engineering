# Banking Transaction Parser - AI Agent Guidelines

## Project Overview
Banking transaction processing system that parses multiple file formats (CSV, JSON, XML) and detects fraud patterns. This is a financial application requiring strict data handling, audit trails, and security compliance.

## Tech Stack
- **Python**: 3.12+ with type hints
- **Data Validation**: Pydantic v2 for models
- **Testing**: pytest with >90% coverage
- **Logging**: Python logging module for audit trails
- **File Processing**: csv, json, xml.etree.ElementTree
- **Monetary Calculations**: decimal.Decimal (never float)

## Banking Domain Standards

### Monetary Precision
- **ALWAYS** use `decimal.Decimal` for amounts, never `float`
- Support ISO 4217 currency codes (USD, EUR, GBP, etc.)
- Handle currency conversion with proper precision
- Validate positive amounts for transactions

### Data Privacy & Security
- Treat account numbers, names, and transaction details as PII
- Implement proper data sanitization in logs
- Use secure file handling practices
- Add input validation for all external data

### Audit Requirements
- Log all parsing operations with timestamps
- Include transaction counts and processing status
- Log fraud detection events with confidence levels
- Maintain audit trail for compliance

### Fraud Detection Patterns
- High-value transactions (>$10,000 USD)
- Velocity checks (rapid successive transactions)
- Unusual timing patterns
- Cross-border transaction monitoring
- Currency conversion anomalies

## Code Style & Standards

### Python Best Practices
- Follow PEP 8 coding standards
- Use type hints for all function signatures
- Write comprehensive docstrings
- Use meaningful variable and function names
- Implement proper exception handling

### File Structure
```
src/
├── models.py          # Pydantic data models
├── transaction_parser.py  # Main parsing logic
└── fraud_detector.py  # Fraud detection algorithms

tests/
├── test_transaction_parser.py
└── conftest.py        # pytest fixtures

sample-data/
├── transactions.csv
├── transactions.json
└── transactions.xml
```

### Error Handling
- Use specific exception types
- Provide meaningful error messages
- Log errors with context
- Gracefully handle malformed data
- Never expose sensitive information in errors

## Testing Requirements

### Test Coverage
- Achieve >90% code coverage
- Test all file formats (CSV, JSON, XML)
- Include edge cases and error conditions
- Test fraud detection scenarios
- Validate currency conversion accuracy

### Test Structure
- Use pytest fixtures for sample data
- Mock external dependencies
- Test both valid and invalid inputs
- Include performance tests for large files
- Add security tests for input validation

### Commands
```bash
# Run all tests
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/test_transaction_parser.py -v

# Run with coverage report
pytest --cov=src --cov-report=term-missing
```

## Security Considerations

### Input Validation
- Validate all file formats before parsing
- Check file size limits
- Sanitize file paths to prevent directory traversal
- Validate currency codes against ISO 4217
- Check timestamp formats and ranges

### Data Handling
- Never log sensitive transaction details
- Use secure file reading practices
- Implement proper resource cleanup
- Handle large files efficiently
- Add rate limiting for processing operations

## Performance Guidelines

### File Processing
- Use streaming for large files
- Implement progress indicators
- Add memory usage monitoring
- Handle concurrent file processing
- Optimize for batch operations

### Memory Management
- Use generators for large datasets
- Implement proper resource cleanup
- Monitor memory usage in tests
- Handle out-of-memory scenarios
- Use efficient data structures

## Documentation Standards

### Code Documentation
- Write clear docstrings for all functions
- Include parameter and return type information
- Add usage examples in docstrings
- Document error conditions
- Include performance characteristics

### README Requirements
- Installation instructions
- Usage examples with sample data
- API documentation
- Troubleshooting guide
- Security considerations
- Performance benchmarks

## Quality Gates

### Before Committing
- All tests must pass
- Code coverage >90%
- No linting errors
- Type checking passes
- Security scan clean
- Performance benchmarks met

### Code Review Checklist
- Proper error handling implemented
- Audit logging added
- Security considerations addressed
- Performance optimizations applied
- Documentation updated
- Tests cover new functionality
