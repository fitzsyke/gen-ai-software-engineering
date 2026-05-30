# Agent IDE Rules for Banking Context

## Banking-Specific Coding Standards

### Security and Compliance
- Never hardcode sensitive data (account numbers, amounts, personal info)
- Always validate input data before processing
- Use proper encryption for sensitive operations
- Include audit logging for all financial operations
- Follow PCI DSS standards for payment processing
- Implement proper error handling without exposing internal details

### Data Handling
- Use Decimal for all monetary calculations (never float)
- Validate currency codes against ISO 4217 standard
- Handle timezone-aware timestamps properly
- Implement proper data sanitization
- Use type hints for all financial data structures
- Include data validation at every input boundary

### Banking Domain Knowledge
- Understand transaction types: wire, ACH, card, international
- Know common fraud patterns: velocity, high-value, geographic anomalies
- Implement proper KYC (Know Your Customer) validation
- Follow AML (Anti-Money Laundering) requirements
- Understand regulatory compliance requirements
- Include proper transaction categorization

### Code Quality Standards
- Write comprehensive unit tests for all financial logic
- Include integration tests for end-to-end workflows
- Implement proper logging with structured data
- Use meaningful variable names for financial concepts
- Include proper documentation for business logic
- Follow defensive programming practices

### Performance Considerations
- Optimize for large transaction volumes
- Implement proper caching strategies
- Use efficient data structures for lookups
- Include performance monitoring
- Handle memory efficiently for large datasets
- Implement proper connection pooling

### Error Handling
- Never expose internal system details in error messages
- Log all errors with proper context
- Implement graceful degradation
- Include proper retry mechanisms
- Handle network timeouts appropriately
- Provide meaningful error messages to users

## Code Generation Guidelines

When generating code for banking applications:
1. Always include input validation
2. Use appropriate data types (Decimal for money)
3. Include comprehensive error handling
4. Add audit logging
5. Follow security best practices
6. Include unit tests
7. Use type hints
8. Follow naming conventions
9. Include proper documentation
10. Consider regulatory compliance

## Prohibited Patterns
- Hardcoded account numbers or amounts
- Using float for monetary calculations
- Exposing internal system details
- Missing input validation
- Inadequate error handling
- Poor logging practices
- Security vulnerabilities
- Performance bottlenecks
- Missing tests
- Poor documentation
