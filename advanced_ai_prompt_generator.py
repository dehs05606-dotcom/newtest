#!/usr/bin/env python3
"""
Advanced AI Prompt Generator for Cybersecurity Library Testing
Generates sophisticated prompts for framework development and testing
"""

import requests
import json
import time
import random
import os
from datetime import datetime
from typing import List, Dict, Any
import threading
import signal
import sys

class AdvancedPromptGenerator:
    def __init__(self):
        # API Configuration
        self.API_KEY = "AIzaSyDxzcuwVpOy_2-Ze61AVduJHUVKTJKiaYc"
        self.MODEL = "gemini-2.5-pro"
        self.BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL}:generateContent"
        
        # Configuration
        self.max_tokens = 600000
        self.timeout = 300  # 5 minutes timeout
        self.generation_delay = 2  # seconds between generations
        
        # Control flags
        self.is_running = False
        self.stop_generation = False
        
        # Output directory
        self.output_dir = "generated_prompts"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Cybersecurity library categories
        self.cyber_lib_categories = [
            "Network Security Testing",
            "Web Application Security",
            "Cryptography Libraries",
            "Penetration Testing Frameworks",
            "Vulnerability Assessment Tools",
            "Malware Analysis Frameworks",
            "Incident Response Libraries",
            "Digital Forensics Tools",
            "Authentication & Authorization",
            "Security Monitoring Systems",
            "Threat Intelligence Platforms",
            "API Security Testing",
            "Container Security",
            "Cloud Security Frameworks",
            "IoT Security Testing",
            "Mobile Security Libraries",
            "Database Security Tools",
            "SIEM Integration Libraries",
            "Compliance Testing Frameworks",
            "Zero Trust Architecture"
        ]
        
        # Real-world scenarios
        self.real_world_scenarios = [
            "Enterprise Network Breach Simulation",
            "Advanced Persistent Threat Detection",
            "Zero-Day Exploit Analysis",
            "Multi-Vector Attack Simulation",
            "Supply Chain Security Testing",
            "Insider Threat Detection",
            "Ransomware Response Testing",
            "Cloud Infrastructure Security",
            "Critical Infrastructure Protection",
            "Financial System Security Testing",
            "Healthcare Data Protection",
            "Government Network Security",
            "Industrial Control System Security",
            "Cryptocurrency Exchange Security",
            "E-commerce Platform Protection",
            "Social Engineering Defense",
            "Data Exfiltration Prevention",
            "Identity Theft Protection",
            "Cyber Warfare Simulation",
            "Nation-State Attack Modeling"
        ]
        
        # Advanced prompt templates
        self.prompt_templates = {
            "framework_development": [
                "Develop a comprehensive {category} framework that can handle {scenario} with advanced {technique} capabilities. Include error handling, logging, and real-time monitoring.",
                "Create an enterprise-grade {category} solution for {scenario} that integrates with existing security infrastructure and provides detailed forensic capabilities.",
                "Design a modular {category} framework for {scenario} with machine learning-based threat detection and automated response mechanisms.",
                "Build a scalable {category} system for {scenario} that supports distributed testing environments and provides comprehensive reporting.",
                "Implement an advanced {category} framework for {scenario} with custom rule engines, behavioral analysis, and threat intelligence integration."
            ],
            "testing_methodology": [
                "Design comprehensive test cases for {category} in {scenario} environments, including edge cases, performance testing, and security validation.",
                "Create automated testing protocols for {category} frameworks handling {scenario} with continuous integration and deployment validation.",
                "Develop stress testing methodologies for {category} systems under {scenario} conditions with load balancing and failover testing.",
                "Implement security testing frameworks for {category} applications in {scenario} with penetration testing and vulnerability assessment.",
                "Design compliance testing procedures for {category} solutions in {scenario} with regulatory requirement validation and audit trails."
            ],
            "research_analysis": [
                "Conduct in-depth research analysis of {category} vulnerabilities in {scenario} contexts, including threat modeling and risk assessment.",
                "Perform comparative analysis of existing {category} solutions for {scenario} with performance benchmarking and security evaluation.",
                "Research emerging threats in {category} related to {scenario} and develop countermeasure strategies with predictive analytics.",
                "Analyze the effectiveness of current {category} approaches in {scenario} and propose next-generation solutions with AI integration.",
                "Investigate advanced attack vectors targeting {category} in {scenario} and develop innovative defense mechanisms."
            ],
            "implementation_guide": [
                "Create detailed implementation guide for {category} framework deployment in {scenario} with step-by-step configuration and optimization.",
                "Develop comprehensive documentation for {category} integration in {scenario} with troubleshooting guides and best practices.",
                "Design deployment strategies for {category} solutions in {scenario} with scalability considerations and performance tuning.",
                "Create maintenance and monitoring procedures for {category} systems in {scenario} with automated health checks and alerting.",
                "Develop training materials for {category} implementation in {scenario} with hands-on exercises and certification paths."
            ]
        }
        
        # Advanced techniques
        self.advanced_techniques = [
            "Machine Learning-based Anomaly Detection",
            "Behavioral Analysis and Pattern Recognition",
            "Artificial Intelligence Threat Hunting",
            "Quantum-Resistant Cryptography",
            "Blockchain-based Security Verification",
            "Advanced Persistent Threat Simulation",
            "Zero Trust Architecture Implementation",
            "Deception Technology Integration",
            "Threat Intelligence Automation",
            "Security Orchestration and Response",
            "Advanced Malware Sandboxing",
            "Network Traffic Analysis with AI",
            "Predictive Security Analytics",
            "Automated Incident Response",
            "Dynamic Security Policy Enforcement",
            "Advanced Encryption Key Management",
            "Multi-Factor Authentication Systems",
            "Biometric Security Integration",
            "Cloud-Native Security Solutions",
            "Edge Computing Security Frameworks"
        ]
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum}. Stopping generation...")
        self.stop_generation = True
        self.is_running = False
    
    def _make_api_request(self, prompt: str) -> Dict[Any, Any]:
        """Make API request to Gemini"""
        headers = {
            'Content-Type': 'application/json',
        }
        
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": 0.8,
                "topP": 0.9,
                "topK": 40
            }
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}?key={self.API_KEY}",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ API Request failed: {e}")
            return {}
    
    def _generate_base_prompt(self) -> str:
        """Generate a base prompt for cybersecurity library testing"""
        category = random.choice(self.cyber_lib_categories)
        scenario = random.choice(self.real_world_scenarios)
        technique = random.choice(self.advanced_techniques)
        template_type = random.choice(list(self.prompt_templates.keys()))
        template = random.choice(self.prompt_templates[template_type])
        
        base_prompt = template.format(
            category=category,
            scenario=scenario,
            technique=technique
        )
        
        # Add research enhancement
        research_enhancement = f"""
        
        RESEARCH REQUIREMENTS:
        - Analyze current industry standards and best practices
        - Review latest CVE databases and threat intelligence
        - Study emerging attack patterns and defense strategies
        - Incorporate lessons learned from recent security incidents
        - Reference authoritative sources and security frameworks
        
        ADVANCED REQUIREMENTS:
        - Implement cutting-edge security technologies
        - Ensure compatibility with enterprise environments
        - Include performance optimization strategies
        - Provide detailed documentation and examples
        - Consider scalability and maintainability factors
        
        OUTPUT FORMAT:
        - Provide comprehensive technical specifications
        - Include code examples and implementation details
        - Add testing procedures and validation methods
        - Create deployment and configuration guides
        - Generate troubleshooting and maintenance procedures
        """
        
        return base_prompt + research_enhancement
    
    def _enhance_prompt_with_research(self, base_prompt: str) -> str:
        """Enhance prompt with research-based context"""
        research_context = f"""
        CYBERSECURITY RESEARCH CONTEXT:
        
        Current Threat Landscape Analysis:
        - Analyze the latest threat intelligence reports
        - Study emerging attack vectors and methodologies
        - Review recent security incidents and their impact
        - Examine evolving compliance requirements
        
        Technical Innovation Requirements:
        - Incorporate state-of-the-art security technologies
        - Utilize advanced AI/ML for threat detection
        - Implement next-generation security architectures
        - Ensure quantum-resistant security measures
        
        Real-World Implementation Considerations:
        - Address enterprise-scale deployment challenges
        - Consider multi-cloud and hybrid environments
        - Include legacy system integration requirements
        - Plan for high-availability and disaster recovery
        
        ENHANCED PROMPT:
        {base_prompt}
        
        DELIVERABLE SPECIFICATIONS:
        1. Comprehensive technical architecture document
        2. Detailed implementation code with comments
        3. Testing framework with automated validation
        4. Deployment scripts and configuration files
        5. Monitoring and alerting system integration
        6. Security audit and compliance verification
        7. Performance benchmarking and optimization
        8. Documentation with examples and tutorials
        9. Incident response and recovery procedures
        10. Continuous improvement and update mechanisms
        """
        
        return research_context
    
    def _save_prompt_to_file(self, prompt: str, response: str, metadata: Dict[str, Any]):
        """Save generated prompt and response to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"advanced_prompt_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata,
            "original_prompt": prompt,
            "generated_response": response,
            "token_count": len(response.split()),
            "category": metadata.get("category", "Unknown"),
            "scenario": metadata.get("scenario", "Unknown"),
            "technique": metadata.get("technique", "Unknown")
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Prompt saved: {filename}")
        except Exception as e:
            print(f"❌ Failed to save prompt: {e}")
    
    def generate_advanced_prompt(self) -> Dict[str, Any]:
        """Generate a single advanced prompt"""
        print("🔄 Generating advanced cybersecurity prompt...")
        
        # Generate base prompt
        base_prompt = self._generate_base_prompt()
        
        # Enhance with research context
        enhanced_prompt = self._enhance_prompt_with_research(base_prompt)
        
        # Create metadata
        metadata = {
            "generation_time": datetime.now().isoformat(),
            "category": random.choice(self.cyber_lib_categories),
            "scenario": random.choice(self.real_world_scenarios),
            "technique": random.choice(self.advanced_techniques),
            "prompt_type": "Advanced Cybersecurity Library Testing",
            "complexity_level": "Expert",
            "target_audience": "Security Researchers and Framework Developers"
        }
        
        # Make API request
        response_data = self._make_api_request(enhanced_prompt)
        
        if response_data and 'candidates' in response_data:
            generated_text = response_data['candidates'][0]['content']['parts'][0]['text']
            
            # Save to file
            self._save_prompt_to_file(enhanced_prompt, generated_text, metadata)
            
            return {
                "success": True,
                "prompt": enhanced_prompt,
                "response": generated_text,
                "metadata": metadata
            }
        else:
            return {
                "success": False,
                "error": "Failed to generate response",
                "metadata": metadata
            }
    
    def start_continuous_generation(self):
        """Start continuous prompt generation"""
        print("🚀 Starting Advanced AI Prompt Generator for Cybersecurity Library Testing")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"⚙️  Max tokens: {self.max_tokens}")
        print(f"⏱️  Generation delay: {self.generation_delay} seconds")
        print("🛑 Press Ctrl+C to stop generation\n")
        
        self.is_running = True
        generation_count = 0
        
        while self.is_running and not self.stop_generation:
            try:
                generation_count += 1
                print(f"\n{'='*60}")
                print(f"🎯 Generation #{generation_count}")
                print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                result = self.generate_advanced_prompt()
                
                if result["success"]:
                    print(f"✅ Successfully generated advanced prompt")
                    print(f"📝 Category: {result['metadata']['category']}")
                    print(f"🎭 Scenario: {result['metadata']['scenario']}")
                    print(f"🔧 Technique: {result['metadata']['technique']}")
                    print(f"📊 Response length: {len(result['response'])} characters")
                else:
                    print(f"❌ Failed to generate prompt: {result.get('error', 'Unknown error')}")
                
                if not self.stop_generation:
                    print(f"⏳ Waiting {self.generation_delay} seconds before next generation...")
                    time.sleep(self.generation_delay)
                    
            except KeyboardInterrupt:
                print("\n🛑 Keyboard interrupt received. Stopping generation...")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                print("⏳ Continuing in 5 seconds...")
                time.sleep(5)
        
        self.is_running = False
        print(f"\n🏁 Generation stopped. Total prompts generated: {generation_count}")
        print(f"📁 Check '{self.output_dir}' directory for saved prompts")
    
    def run(self):
        """Main entry point"""
        try:
            self.start_continuous_generation()
        except Exception as e:
            print(f"💥 Fatal error: {e}")
            sys.exit(1)

def main():
    """Main function"""
    print("🔐 Advanced AI Prompt Generator for Cybersecurity Library Testing")
    print("=" * 70)
    
    generator = AdvancedPromptGenerator()
    generator.run()

if __name__ == "__main__":
    main()