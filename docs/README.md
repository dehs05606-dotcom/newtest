# Project AEGIS: Advanced Web Security Research Framework

## 📋 Table of Contents

- [Overview](#overview)
- [⚠️ Important Disclaimer](#important-disclaimer)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Modules](#modules)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Security Testing Lab](#security-testing-lab)
- [Contributing](#contributing)
- [Educational Resources](#educational-resources)

## Overview

Project AEGIS is a comprehensive, defensive cybersecurity research framework designed for authorized penetration testing, vulnerability analysis, and security research. The framework provides advanced capabilities for testing web applications, APIs, Jamstack applications, and modern web architectures.

### Key Capabilities

- **Comprehensive Vulnerability Scanning**: Advanced detection of SQL injection, XSS, CSRF, and other web vulnerabilities
- **Cache Poisoning Analysis**: Specialized tools for detecting cache poisoning vulnerabilities in modern web architectures
- **Authentication Bypass Testing**: Advanced parameter pollution and authentication bypass detection
- **Jamstack Security Assessment**: Specialized scanning for Next.js, Gatsby, Nuxt.js, and other static site generators
- **SQL Injection Analysis**: Advanced SQL injection detection including blind, time-based, and second-order attacks
- **Real-time Reporting**: Comprehensive logging and reporting with multiple output formats

## ⚠️ Important Disclaimer

**THIS FRAMEWORK IS FOR AUTHORIZED TESTING ONLY**

Project AEGIS is designed exclusively for:
- ✅ **Authorized penetration testing** in controlled environments
- ✅ **Educational purposes** for cybersecurity professionals
- ✅ **Defensive security research** and vulnerability analysis
- ✅ **Security tool development** for protection purposes

**❌ This framework must NEVER be used for:**
- Unauthorized access to systems
- Malicious activities
- Illegal hacking or exploitation
- Any activities that violate applicable laws

Users must:
- Obtain proper written authorization before testing any systems
- Comply with all applicable laws and regulations
- Use the framework responsibly and ethically
- Respect the privacy and security of others

## Features

### 🛡️ Core Security Modules

1. **Vulnerability Scanner** (`vulnerability-scanner.js`)
   - Multi-threaded web application scanning
   - Browser-based testing with Puppeteer
   - Comprehensive vulnerability detection
   - Automated crawling and parameter discovery

2. **Cache Analyzer** (`cache-analyzer.js`)
   - Cache poisoning detection
   - Unkeyed input discovery
   - Cache key analysis
   - Jamstack-specific cache testing

3. **Authentication Tester** (`auth-tester.js`)
   - Parameter pollution testing
   - Authentication bypass techniques
   - Session management analysis
   - JWT/token security testing

4. **SQL Analyzer** (`sql-analyzer.js`)
   - Advanced SQL injection detection
   - Database fingerprinting
   - Blind SQL injection testing
   - NoSQL injection analysis

5. **Jamstack Scanner** (`jamstack-scanner.js`)
   - Framework detection and analysis
   - Serverless function testing
   - Build artifact analysis
   - Client-side security assessment

### 🔧 Advanced Features

- **Multi-threaded Scanning**: Parallel vulnerability testing for improved performance
- **Intelligent Fingerprinting**: Automatic detection of web technologies and frameworks
- **Advanced Payload Generation**: Dynamic payload creation based on target characteristics
- **Comprehensive Reporting**: Detailed vulnerability reports with evidence and remediation guidance
- **Real-time Logging**: Advanced logging system with multiple severity levels
- **Interactive Mode**: User-friendly command-line interface for guided testing

## Installation

### Prerequisites

- Node.js 16.0.0 or higher
- npm or yarn package manager
- Git

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/your-org/project-aegis.git
cd project-aegis
```

2. **Install dependencies:**
```bash
npm install
```

3. **Verify installation:**
```bash
npm test
```

## Quick Start

### Interactive Mode (Recommended for beginners)

```bash
npm start
```

This launches the interactive interface where you can select scanning options through a menu system.

### Command Line Usage

```bash
# Comprehensive vulnerability scan
npm run vulnerability-scan -- --url https://example.com --depth 3 --output results.json

# Cache poisoning analysis
npm run cache-analysis -- --url https://example.com

# Authentication testing
npm run auth-test -- --url https://example.com

# SQL injection analysis
npm run sql-analysis -- --url https://example.com --parameters "id,name,search"

# Jamstack security scan
npm run jamstack-scan -- --url https://example.com --framework next
```

## Modules

### 1. Vulnerability Scanner

The core vulnerability scanner provides comprehensive web application security testing.

**Features:**
- Automated crawling and link discovery
- Parameter extraction from forms and URLs
- Multi-vulnerability testing (XSS, SQLi, Command Injection, etc.)
- Browser-based testing for DOM vulnerabilities
- Configurable scan depth and threading

**Usage:**
```bash
node src/scanners/vulnerability-scanner.js --url https://target.com --depth 5 --threads 20
```

### 2. Cache Analyzer

Specialized tool for detecting cache poisoning vulnerabilities in modern web applications.

**Features:**
- Cache infrastructure detection (Cloudflare, Fastly, Varnish, etc.)
- Unkeyed input discovery
- Cache key analysis and manipulation
- Advanced cache poisoning techniques
- Jamstack-specific cache testing

**Usage:**
```bash
node src/analyzers/cache-analyzer.js --url https://target.com
```

### 3. Authentication Tester

Advanced authentication security testing with focus on parameter pollution and bypass techniques.

**Features:**
- HTTP Parameter Pollution (HPP) testing
- JSON parameter pollution
- Authentication bypass techniques
- Session management testing
- JWT/token security analysis
- Role-based access control testing

**Usage:**
```bash
node src/testers/auth-tester.js --url https://target.com
```

### 4. SQL Analyzer

Comprehensive SQL injection detection and analysis framework.

**Features:**
- Database fingerprinting
- Error-based SQL injection
- Union-based SQL injection
- Boolean-based blind SQL injection
- Time-based blind SQL injection
- Second-order SQL injection
- NoSQL injection testing

**Usage:**
```bash
node src/analyzers/sql-analyzer.js --url https://target.com --parameters "id,search,filter"
```

### 5. Jamstack Scanner

Specialized security assessment for Jamstack and Static Site Generator applications.

**Features:**
- Framework detection (Next.js, Gatsby, Nuxt.js, Hugo, Jekyll, etc.)
- Build artifact analysis
- Serverless function testing
- Client-side security assessment
- CI/CD configuration analysis
- Third-party integration security

**Usage:**
```bash
node src/scanners/jamstack-scanner.js --url https://target.com --framework next
```

## Usage Examples

### Example 1: Basic Web Application Scan

```bash
# Start with a basic vulnerability scan
npm run vulnerability-scan -- --url https://testapp.com --depth 2 --output basic-scan.json

# Review results
cat basic-scan.json | jq '.vulnerabilities[] | select(.severity == "Critical")'
```

### Example 2: E-commerce Application Testing

```bash
# Comprehensive scan for e-commerce site
npm run vulnerability-scan -- --url https://shop.example.com --depth 4 --threads 15

# Test authentication mechanisms
npm run auth-test -- --url https://shop.example.com/login

# Analyze SQL injection in product search
npm run sql-analysis -- --url https://shop.example.com/search --parameters "q,category,price_min,price_max"

# Check for cache poisoning in product pages
npm run cache-analysis -- --url https://shop.example.com/products/123
```

### Example 3: Jamstack Application Assessment

```bash
# Detect and analyze Jamstack framework
npm run jamstack-scan -- --url https://myapp.netlify.app --framework auto-detect

# Focus on serverless functions
npm run vulnerability-scan -- --url https://myapp.netlify.app/.netlify/functions/

# Check for build artifact exposure
curl https://myapp.netlify.app/.next/BUILD_ID
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Scan Configuration
DEFAULT_TIMEOUT=10000
DEFAULT_THREADS=10
DEFAULT_DEPTH=3

# Logging Configuration
LOG_LEVEL=info
LOG_FILE_MAX_SIZE=5242880
LOG_MAX_FILES=5

# Output Configuration
DEFAULT_OUTPUT_FORMAT=json
REPORTS_DIRECTORY=./reports

# Proxy Configuration (optional)
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
```

### Custom Payloads

You can customize payloads by creating payload files:

```json
// payloads/custom-xss.json
{
  "xss": [
    "<script>alert('Custom XSS')</script>",
    "<img src=x onerror=alert('Custom XSS')>",
    "javascript:alert('Custom XSS')"
  ]
}
```

### Scan Profiles

Create scan profiles for different types of applications:

```json
// profiles/ecommerce.json
{
  "name": "E-commerce Security Profile",
  "depth": 5,
  "threads": 20,
  "modules": [
    "vulnerability-scanner",
    "auth-tester",
    "sql-analyzer",
    "cache-analyzer"
  ],
  "focus_areas": [
    "authentication",
    "payment_processing",
    "user_data",
    "session_management"
  ]
}
```

## Security Testing Lab

### Setting Up a Test Environment

Project AEGIS includes scripts to set up vulnerable applications for testing:

```bash
# Set up vulnerable web applications
npm run setup-lab

# Start test environment
docker-compose -f lab/docker-compose.yml up -d

# Run tests against lab environment
npm run test-lab
```

### Included Vulnerable Applications

1. **DVWA (Damn Vulnerable Web Application)**
   - SQL injection testing
   - XSS vulnerability testing
   - Authentication bypass testing

2. **Vulnerable Jamstack App**
   - Next.js application with intentional vulnerabilities
   - Serverless function vulnerabilities
   - Build artifact exposure

3. **Cache Poisoning Lab**
   - Varnish cache setup
   - Unkeyed input examples
   - Cache key manipulation scenarios

## Advanced Usage

### Custom Modules

Create custom security modules:

```javascript
// src/custom/my-scanner.js
const Logger = require('../utils/logger');

class MyCustomScanner {
  constructor() {
    this.logger = new Logger();
    this.vulnerabilities = [];
  }

  async scan(options) {
    this.logger.info('Starting custom scan...');
    // Your custom scanning logic here
  }
}

module.exports = MyCustomScanner;
```

### Integration with CI/CD

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on: [push, pull_request]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '16'
      - name: Install dependencies
        run: npm install
      - name: Run security scan
        run: npm run vulnerability-scan -- --url ${{ secrets.TEST_URL }} --output security-report.json
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: security-report
          path: security-report.json
```

### API Integration

```javascript
// Example: Using AEGIS in your own application
const { VulnerabilityScanner } = require('project-aegis');

const scanner = new VulnerabilityScanner();
const results = await scanner.scan({
  url: 'https://example.com',
  depth: 3,
  threads: 10
});

console.log(`Found ${results.total} vulnerabilities`);
```

## Contributing

We welcome contributions from the cybersecurity community!

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-scanner`
3. **Make your changes**: Follow our coding standards
4. **Add tests**: Ensure your code is well-tested
5. **Submit a pull request**: Describe your changes clearly

### Contribution Guidelines

- **Code Quality**: Follow ESLint rules and maintain high code quality
- **Documentation**: Update documentation for any new features
- **Testing**: Add comprehensive tests for new functionality
- **Security**: Ensure all contributions maintain the ethical use focus
- **Performance**: Consider performance impact of new features

### Areas for Contribution

- New vulnerability detection techniques
- Additional framework support
- Performance optimizations
- Documentation improvements
- Test coverage expansion

## Educational Resources

### Learning Materials

1. **Web Security Fundamentals**
   - OWASP Top 10 vulnerabilities
   - Common attack vectors
   - Defensive programming techniques

2. **Advanced Topics**
   - Cache poisoning techniques
   - Parameter pollution attacks
   - Jamstack security considerations
   - Modern authentication mechanisms

3. **Hands-on Labs**
   - Guided vulnerability discovery exercises
   - Real-world testing scenarios
   - Defensive strategy development

### Recommended Reading

- [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [PortSwigger Web Security Academy](https://portswigger.net/web-security)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### Training Modules

Project AEGIS includes interactive training modules:

```bash
# Start training mode
npm run training

# Available modules:
# - SQL Injection Fundamentals
# - XSS Attack and Defense
# - Authentication Security
# - Cache Poisoning Techniques
# - Jamstack Security Best Practices
```

## Support and Community

### Getting Help

- **Documentation**: Check this README and the `/docs` directory
- **Issues**: Report bugs and request features on GitHub Issues
- **Discussions**: Join community discussions on GitHub Discussions
- **Security**: Report security issues privately to security@project-aegis.org

### Community Guidelines

- Be respectful and professional
- Focus on educational and defensive use cases
- Share knowledge and help others learn
- Follow responsible disclosure practices
- Respect privacy and legal boundaries

## License

Project AEGIS is released under the MIT License. See [LICENSE](LICENSE) file for details.

## Acknowledgments

- OWASP community for security research and guidelines
- Security researchers who contribute to defensive cybersecurity
- Open source projects that make this framework possible
- Educational institutions promoting ethical security research

---

**Remember: Use this framework responsibly, ethically, and only with proper authorization. The goal is to improve security, not to cause harm.**