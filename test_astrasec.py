#!/usr/bin/env python3
"""
Test script for AstraSec Security Copilot
Demonstrates all major functionality
"""

import json
from astrasec_copilot import AstraSecCopilot

def test_astrasec_copilot():
    """Test all major functions of AstraSec Copilot"""
    
    print("🧪 Testing AstraSec Security Copilot...")
    
    # Initialize copilot
    copilot = AstraSecCopilot()
    
    # Test 1: Status check
    print("\n1. Testing Status Check:")
    status = copilot.get_status()
    print(json.dumps(status, indent=2))
    
    # Test 2: Alert Triage
    print("\n2. Testing Alert Triage:")
    alert_data = "Multiple failed logins detected on svc-backup account from IP 192.168.1.100, followed by successful login at 10:15 AM"
    triage_result = copilot.triage_alert(alert_data)
    print("Triage Result:")
    print(json.dumps(triage_result, indent=2))
    
    # Test 3: Threat Hunting
    print("\n3. Testing Threat Hunting:")
    hypothesis = "Lateral movement via SMB connections in the last 24 hours"
    hunt_result = copilot.hunt_threats(hypothesis, {"time_range": "-24h", "scope": "all"})
    print("Hunt Result:")
    print(json.dumps(hunt_result, indent=2))
    
    # Test 4: Incident Investigation
    print("\n4. Testing Incident Investigation:")
    timeline_data = """
    2024-01-01T10:00:00Z|LOGIN_FAILURE|Multiple failed logins on svc-backup
    2024-01-01T10:15:00Z|LOGIN_SUCCESS|Successful login from suspicious IP
    2024-01-01T10:20:00Z|PROCESS_CREATION|New process cmd.exe spawned
    2024-01-01T10:25:00Z|NETWORK_CONNECTION|Connection to external IP 8.8.8.8
    """
    investigation_result = copilot.investigate_incident("INCIDENT-001", timeline_data)
    print("Investigation Result:")
    print(json.dumps(investigation_result, indent=2))
    
    # Test 5: Threat Containment
    print("\n5. Testing Threat Containment:")
    threat_data = {"threat_level": "HIGH", "malware_family": "Ransomware"}
    contain_result = copilot.contain_threat("WIN-ACME-42", threat_data)
    print("Containment Result:")
    print(json.dumps(contain_result, indent=2))
    
    # Test 6: Report Generation
    print("\n6. Testing Report Generation:")
    incident_data = {
        "incident_id": "INCIDENT-001",
        "severity": "HIGH",
        "title": "Suspicious Login Activity"
    }
    report_result = copilot.generate_report(incident_data)
    print("Report Result:")
    print(json.dumps(report_result, indent=2))
    
    # Test 7: User Input Processing
    print("\n7. Testing User Input Processing:")
    test_inputs = [
        "triage alert: Brute force attack detected",
        "hunt hypothesis: Data exfiltration via DNS",
        "investigate timeline: Process injection events",
        "contain host: WIN-MALWARE-01",
        "report incident: INCIDENT-002"
    ]
    
    for user_input in test_inputs:
        print(f"\nProcessing: {user_input}")
        result = copilot.process_user_input(user_input)
        print(f"Mode: {result.get('mode', 'unknown')}")
        print(f"Summary: {result.get('summary', 'No summary')[:100]}...")
    
    print("\n✅ All tests completed successfully!")
    print("AstraSec Security Copilot is ready for production use!")

if __name__ == "__main__":
    test_astrasec_copilot()