# AstraSec Security Copilot 🛡️

Enterprise-grade Security AI for SOC, DFIR, and Threat Hunting

## Mission
**Triage → Hunt → Investigate → Contain (with approval) → Report**

AstraSec Copilot is a defensive, enterprise-grade Security AI designed to accelerate security analysts through intelligent automation while maintaining strict security guardrails and compliance requirements.

## Features

### 🔍 **Multi-Mode Operations**
- **Triage Mode**: Alert clustering, deduplication, priority assessment
- **Hunt Mode**: Hypothesis-driven threat hunting with ATT&CK mapping
- **Investigate Mode**: Deep timeline analysis and root cause investigation
- **Contain Mode**: Safe containment with approval workflows
- **Report Mode**: Executive summaries and detailed analyst reports

### 🛡️ **Security & Compliance**
- **Defensive-only scope**: No offensive capabilities
- **Approval workflows**: High-risk actions require explicit approval
- **Audit logging**: Complete chain-of-custody preservation
- **PII protection**: Automatic data sanitization
- **Least privilege**: Minimal data exposure principles

### 🤖 **AI-Powered Analysis**
- **Real API Integration**: Gemini 2.5 Pro for intelligent analysis
- **MITRE ATT&CK Mapping**: Automatic technique identification
- **IOC Extraction**: Automated indicator collection and correlation
- **Query Generation**: Intelligent SIEM/EDR query suggestions

### 📊 **Enterprise Integration**
- **SIEM Integration**: KQL, SPL, SQL query support
- **EDR Integration**: Process tree and telemetry analysis
- **Threat Intel**: Hash, domain, IP reputation lookups
- **Cloud Logs**: AWS, GCP, Azure, M365 audit analysis

## Installation

### Prerequisites
- Python 3.8+
- Valid Gemini API key
- SQLite (included with Python)

### Quick Start
```bash
# Clone repository
git clone <repository-url>
cd astrasec-copilot

# Install dependencies
pip install -r requirements.txt

# Set API key (replace with your actual key)
export GEMINI_API_KEY="your-api-key-here"

# Run AstraSec Copilot
python astrasec_copilot.py
```

## Usage

### Basic Commands

```bash
# Start AstraSec Copilot
python astrasec_copilot.py

# Available commands in interactive mode:
AstraSec> triage alert: Multiple failed logins detected
AstraSec> hunt hypothesis: Lateral movement via SMB
AstraSec> investigate incident: INCIDENT-001
AstraSec> contain host: WIN-ACME-42
AstraSec> report incident: INCIDENT-001
```

### Example Workflows

#### 1. Alert Triage
```
Input: "Multiple failed logons followed by success on svc-backup in last 2h"
Output: JSON with triage analysis, IOC extraction, and next best actions
```

#### 2. Threat Hunting
```
Input: "Hunt for lateral movement indicators in the last 24 hours"
Output: Generated queries, results analysis, and MITRE ATT&CK mapping
```

#### 3. Incident Investigation
```
Input: "Investigate timeline for suspicious process creation events"
Output: Root cause analysis, containment recommendations, and evidence chain
```

## Security Features

### 🔒 **Approval Workflows**
- **Low Risk**: Automatic execution (queries, analysis)
- **Medium Risk**: Approval required (process termination)
- **High Risk**: Approval required (host isolation, network blocks)

### 📝 **Audit Trail**
- All actions logged with timestamps
- Session tracking for chain-of-custody
- User approval records
- Data access logs

### 🛡️ **Data Protection**
- PII automatic sanitization
- No credential storage
- Encrypted data transmission
- Minimal data retention

## Configuration

### Environment Variables
```bash
GEMINI_API_KEY=your-api-key-here
ASTRASEC_LOG_LEVEL=INFO
ASTRASEC_DB_PATH=./astrasec_data.db
ASTRASEC_TIMEOUT=300
```

### API Configuration
The system uses Google's Gemini 2.5 Pro model for intelligent analysis:
- **Model**: gemini-2.5-pro
- **Max Tokens**: 600,000
- **Timeout**: 300 seconds
- **Temperature**: 0.1 (for consistent security analysis)

## Database Schema

### IOC Database
```sql
CREATE TABLE ioc_database (
    hash TEXT PRIMARY KEY,
    domain TEXT,
    ip TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    reputation TEXT,
    family TEXT,
    sightings INTEGER DEFAULT 0
);
```

### Audit Log
```sql
CREATE TABLE audit_log (
    timestamp TIMESTAMP,
    session_id TEXT,
    action TEXT,
    details TEXT,
    user_approval TEXT
);
```

### Incidents
```sql
CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT,
    severity TEXT,
    created_at TIMESTAMP,
    status TEXT,
    artifacts TEXT
);
```

## Output Format

All responses follow a standardized JSON format:

```json
{
  "mode": "triage|hunt|investigate|contain|report",
  "summary": "Executive summary (<=120 words)",
  "rationale": "Evidence-based reasoning",
  "confidence": 0.0-1.0,
  "mitre_attack": ["T1059", "T1566"],
  "iocs": {
    "hashes": ["..."],
    "domains": ["..."],
    "ips": ["..."],
    "uris": ["..."],
    "emails": ["..."],
    "registry_keys": ["..."],
    "processes": ["..."]
  },
  "queries": [
    {
      "target": "siem",
      "label": "suspicious-logons-24h",
      "language": "KQL",
      "query": "..."
    }
  ],
  "next_best_actions": [
    {
      "action": "RUN_QUERY",
      "tool": "siem.query",
      "args": {"query_ref": "suspicious-logons-24h"},
      "risk": "LOW",
      "approval": "NOT_REQUIRED"
    }
  ],
  "audit": {
    "data_minimization": "PII sanitized in outputs",
    "limitations": "Analysis limitations and gaps",
    "references": ["MITRE ATT&CK", "Internal Runbooks"]
  }
}
```

## Hunting Playbooks

### Suspicious Logons
- Impossible travel detection
- MFA fatigue analysis
- Service principal anomalies

### Process Anomalies
- LOLBins detection (rundll32, regsvr32)
- Encoded PowerShell commands
- Unusual parent-child relationships

### Initial Access
- Phishing attachment analysis
- OAuth consent grant monitoring
- Risky app registration detection

### Lateral Movement
- SMB session anomalies
- Kerberos ticket analysis
- RDP connection spikes

### Exfiltration Indicators
- Unusual egress to new ASNs
- Large data transfers to cloud storage
- DNS tunneling detection

## Detection Engineering

AstraSec Copilot can assist with:
- **Detection Logic**: Generate KQL/SPL/SQL queries
- **False Positive Analysis**: Identify tuning opportunities
- **Test Case Generation**: Create synthetic event generators
- **MITRE Mapping**: Automatically map to ATT&CK techniques

## Compliance & Legal

### Ethical Guardrails
- **Defensive-only scope**: No offensive capabilities
- **No destructive actions**: All containment requires approval
- **No credential guessing**: Uses provided tokens only
- **Transparent reasoning**: All decisions documented

### Data Handling
- **PII Minimization**: Automatic sanitization
- **Data Residency**: Respects tenant constraints
- **Retention Policies**: Configurable data retention
- **Access Controls**: Role-based access management

## Troubleshooting

### Common Issues

1. **API Key Errors**
   ```bash
   Error: API call failed: 401 Unauthorized
   Solution: Verify GEMINI_API_KEY environment variable
   ```

2. **Database Errors**
   ```bash
   Error: database is locked
   Solution: Check file permissions and close other instances
   ```

3. **Timeout Errors**
   ```bash
   Error: API call timeout
   Solution: Increase ASTRASEC_TIMEOUT value
   ```

### Logging
```bash
# Enable debug logging
export ASTRASEC_LOG_LEVEL=DEBUG
python astrasec_copilot.py
```

## Contributing

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd astrasec-copilot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/
```

### Code Standards
- Follow PEP 8 style guidelines
- Include type hints for all functions
- Add comprehensive docstrings
- Write unit tests for new features

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- **Documentation**: See docs/ directory
- **Issues**: Create GitHub issue
- **Security**: Report to security@example.com

## Disclaimer

AstraSec Copilot is designed for defensive security operations only. Users are responsible for ensuring compliance with applicable laws and regulations. The tool does not provide legal advice and should be used in accordance with organizational policies.

---

**AstraSec Copilot** - Accelerating Security Operations with AI 🚀
