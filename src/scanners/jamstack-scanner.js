const axios = require('axios');
const { URL } = require('url');
const Logger = require('../utils/logger');
const cheerio = require('cheerio');
const fs = require('fs').promises;

class JamstackScanner {
  constructor() {
    this.logger = new Logger();
    this.vulnerabilities = [];
    this.startTime = null;
    this.detectedFrameworks = new Set();
    this.discoveredEndpoints = new Set();
    this.buildArtifacts = new Map();
  }

  async scan(options) {
    this.startTime = Date.now();
    const { url, framework } = options;
    
    this.logger.scanBanner('JAMSTACK SECURITY', url);
    this.logger.logScanStart(url, 'Jamstack/SSG Security Assessment');

    try {
      // Phase 1: Framework Detection and Fingerprinting
      this.logger.info('🔍 Phase 1: Framework Detection and Fingerprinting');
      const frameworkInfo = await this.detectFramework(url, framework);
      
      // Phase 2: Build Artifact Discovery
      this.logger.info('📦 Phase 2: Build Artifact Discovery');
      const artifacts = await this.discoverBuildArtifacts(url, frameworkInfo);
      
      // Phase 3: API and Serverless Function Analysis
      this.logger.info('⚡ Phase 3: API and Serverless Function Analysis');
      await this.analyzeServerlessFunctions(url, frameworkInfo);
      
      // Phase 4: Static Asset Security Analysis
      this.logger.info('🗂️ Phase 4: Static Asset Security Analysis');
      await this.analyzeStaticAssets(url, frameworkInfo);
      
      // Phase 5: Client-Side Security Testing
      this.logger.info('🌐 Phase 5: Client-Side Security Testing');
      await this.analyzeClientSideSecurity(url, frameworkInfo);
      
      // Phase 6: Build Process and CI/CD Security
      this.logger.info('🔧 Phase 6: Build Process and CI/CD Security');
      await this.analyzeBuildSecurity(url, frameworkInfo, artifacts);
      
      // Phase 7: Configuration and Environment Analysis
      this.logger.info('⚙️ Phase 7: Configuration and Environment Analysis');
      await this.analyzeConfiguration(url, frameworkInfo);
      
      // Phase 8: Third-Party Integration Security
      this.logger.info('🔗 Phase 8: Third-Party Integration Security');
      await this.analyzeThirdPartyIntegrations(url, frameworkInfo);
      
      // Generate results
      const results = await this.generateResults(url, frameworkInfo, artifacts);
      
      this.logger.logScanComplete(url, 'Jamstack/SSG Security Assessment', results);
      this.logger.generateSummary(results);
      
      return results;
      
    } catch (error) {
      this.logger.error('Jamstack security scan failed', { error: error.message, stack: error.stack });
      throw error;
    }
  }

  async detectFramework(url, providedFramework) {
    this.logger.info('🔍 Detecting Jamstack framework...');
    
    const frameworkInfo = {
      type: providedFramework || 'unknown',
      version: 'unknown',
      buildSystem: 'unknown',
      hosting: 'unknown',
      features: [],
      endpoints: []
    };

    try {
      const response = await axios.get(url, {
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      const headers = response.headers;
      const htmlContent = response.data;
      const $ = cheerio.load(htmlContent);

      // Detect framework from headers
      this.detectFrameworkFromHeaders(headers, frameworkInfo);
      
      // Detect framework from HTML content
      this.detectFrameworkFromHTML($, htmlContent, frameworkInfo);
      
      // Detect hosting platform
      this.detectHostingPlatform(headers, frameworkInfo);
      
      // Detect build system
      await this.detectBuildSystem(url, frameworkInfo);
      
      // Framework-specific feature detection
      await this.detectFrameworkFeatures(url, frameworkInfo);

      this.logger.info(`✅ Framework detection complete. Detected: ${frameworkInfo.type} ${frameworkInfo.version} on ${frameworkInfo.hosting}`);

    } catch (error) {
      this.logger.warn(`Failed to detect framework: ${error.message}`);
    }

    return frameworkInfo;
  }

  detectFrameworkFromHeaders(headers, frameworkInfo) {
    // Check server headers for framework indicators
    const serverHeader = headers.server || '';
    const poweredBy = headers['x-powered-by'] || '';
    
    // Vercel detection
    if (headers['x-vercel-cache'] || headers['x-vercel-id']) {
      frameworkInfo.hosting = 'Vercel';
      frameworkInfo.type = frameworkInfo.type === 'unknown' ? 'Next.js' : frameworkInfo.type;
    }
    
    // Netlify detection
    if (headers['x-nf-request-id'] || headers['server']?.includes('Netlify')) {
      frameworkInfo.hosting = 'Netlify';
    }
    
    // GitHub Pages detection
    if (serverHeader.includes('GitHub.com')) {
      frameworkInfo.hosting = 'GitHub Pages';
      frameworkInfo.type = frameworkInfo.type === 'unknown' ? 'Jekyll' : frameworkInfo.type;
    }
    
    // Cloudflare Pages detection
    if (headers['cf-ray']) {
      frameworkInfo.hosting = 'Cloudflare Pages';
    }
    
    // Next.js detection
    if (poweredBy.includes('Next.js')) {
      frameworkInfo.type = 'Next.js';
      const versionMatch = poweredBy.match(/Next\.js (\d+\.\d+\.\d+)/);
      if (versionMatch) {
        frameworkInfo.version = versionMatch[1];
      }
    }
  }

  detectFrameworkFromHTML($, htmlContent, frameworkInfo) {
    // Next.js detection
    if ($('script[src*="_next/static"]').length > 0 || htmlContent.includes('__NEXT_DATA__')) {
      frameworkInfo.type = 'Next.js';
      frameworkInfo.features.push('Static Generation', 'Server-Side Rendering');
      
      // Extract Next.js version from build ID
      const buildIdMatch = htmlContent.match(/"buildId":"([^"]+)"/);
      if (buildIdMatch) {
        frameworkInfo.buildId = buildIdMatch[1];
      }
    }
    
    // Gatsby detection
    if ($('script[src*="webpack-runtime"]').length > 0 || htmlContent.includes('___gatsby')) {
      frameworkInfo.type = 'Gatsby';
      frameworkInfo.features.push('Static Site Generation', 'GraphQL');
    }
    
    // Nuxt.js detection
    if (htmlContent.includes('__NUXT__') || $('script[src*="_nuxt/"]').length > 0) {
      frameworkInfo.type = 'Nuxt.js';
      frameworkInfo.features.push('Vue.js', 'Universal Application');
    }
    
    // Hugo detection
    if ($('meta[name="generator"][content*="Hugo"]').length > 0) {
      frameworkInfo.type = 'Hugo';
      const versionMatch = $('meta[name="generator"]').attr('content')?.match(/Hugo (\d+\.\d+\.\d+)/);
      if (versionMatch) {
        frameworkInfo.version = versionMatch[1];
      }
    }
    
    // Jekyll detection
    if ($('meta[name="generator"][content*="Jekyll"]').length > 0) {
      frameworkInfo.type = 'Jekyll';
      const versionMatch = $('meta[name="generator"]').attr('content')?.match(/Jekyll v(\d+\.\d+\.\d+)/);
      if (versionMatch) {
        frameworkInfo.version = versionMatch[1];
      }
    }
    
    // Gridsome detection
    if (htmlContent.includes('__GRIDSOME__')) {
      frameworkInfo.type = 'Gridsome';
      frameworkInfo.features.push('Vue.js', 'GraphQL');
    }
    
    // 11ty detection
    if ($('meta[name="generator"][content*="Eleventy"]').length > 0) {
      frameworkInfo.type = '11ty';
    }
    
    // SvelteKit detection
    if (htmlContent.includes('__SVELTEKIT__') || $('script[src*="_app/"]').length > 0) {
      frameworkInfo.type = 'SvelteKit';
      frameworkInfo.features.push('Svelte', 'Server-Side Rendering');
    }
  }

  detectHostingPlatform(headers, frameworkInfo) {
    // Additional hosting platform detection
    if (headers['x-amz-cf-id']) {
      frameworkInfo.hosting = 'AWS CloudFront';
    } else if (headers['x-served-by']?.includes('cache')) {
      frameworkInfo.hosting = 'Fastly';
    } else if (headers['x-cache']) {
      frameworkInfo.hosting = 'CDN';
    }
  }

  async detectBuildSystem(url, frameworkInfo) {
    // Try to detect build system from common paths
    const buildIndicators = [
      { path: '/package.json', system: 'npm/yarn' },
      { path: '/.github/workflows', system: 'GitHub Actions' },
      { path: '/netlify.toml', system: 'Netlify Build' },
      { path: '/vercel.json', system: 'Vercel Build' },
      { path: '/Dockerfile', system: 'Docker' }
    ];

    for (const indicator of buildIndicators) {
      try {
        const testUrl = new URL(indicator.path, url).href;
        const response = await axios.get(testUrl, {
          timeout: 5000,
          validateStatus: () => true
        });

        if (response.status === 200) {
          frameworkInfo.buildSystem = indicator.system;
          break;
        }
      } catch (error) {
        // Continue checking
      }
    }
  }

  async detectFrameworkFeatures(url, frameworkInfo) {
    // Test for common Jamstack features
    const featureTests = [
      { path: '/api/', feature: 'API Routes' },
      { path: '/.netlify/functions/', feature: 'Netlify Functions' },
      { path: '/.vercel/functions/', feature: 'Vercel Functions' },
      { path: '/sitemap.xml', feature: 'SEO Sitemap' },
      { path: '/robots.txt', feature: 'SEO Robots' },
      { path: '/sw.js', feature: 'Service Worker' },
      { path: '/manifest.json', feature: 'PWA Manifest' }
    ];

    for (const test of featureTests) {
      try {
        const testUrl = new URL(test.path, url).href;
        const response = await axios.get(testUrl, {
          timeout: 5000,
          validateStatus: () => true
        });

        if (response.status === 200) {
          frameworkInfo.features.push(test.feature);
          if (test.path.includes('api') || test.path.includes('functions')) {
            frameworkInfo.endpoints.push(testUrl);
            this.discoveredEndpoints.add(testUrl);
          }
        }
      } catch (error) {
        // Continue checking
      }
    }
  }

  async discoverBuildArtifacts(url, frameworkInfo) {
    this.logger.info('📦 Discovering build artifacts and exposed files...');
    
    const artifacts = {
      sourceFiles: [],
      configFiles: [],
      buildFiles: [],
      sensitiveFiles: []
    };

    // Common build artifacts and sensitive files to check
    const artifactPaths = {
      sourceFiles: [
        '/.next/static/chunks/',
        '/_next/static/',
        '/static/js/',
        '/static/css/',
        '/.nuxt/',
        '/dist/',
        '/build/',
        '/_app/',
        '/assets/'
      ],
      configFiles: [
        '/package.json',
        '/package-lock.json',
        '/yarn.lock',
        '/next.config.js',
        '/nuxt.config.js',
        '/gatsby-config.js',
        '/webpack.config.js',
        '/tsconfig.json',
        '/.env',
        '/.env.local',
        '/.env.production',
        '/vercel.json',
        '/netlify.toml'
      ],
      buildFiles: [
        '/.next/BUILD_ID',
        '/.next/build-manifest.json',
        '/build-manifest.json',
        '/_buildManifest.js',
        '/webpack-runtime.js',
        '/chunk-map.json'
      ],
      sensitiveFiles: [
        '/.git/config',
        '/.github/workflows/',
        '/docker-compose.yml',
        '/Dockerfile',
        '/.dockerignore',
        '/.gitignore',
        '/README.md',
        '/CHANGELOG.md',
        '/.vscode/',
        '/.idea/',
        '/node_modules/',
        '/.DS_Store'
      ]
    };

    for (const [category, paths] of Object.entries(artifactPaths)) {
      for (let i = 0; i < paths.length; i++) {
        const path = paths[i];
        this.logger.progress(i + 1, paths.length, `Checking ${category}`);
        
        try {
          const testUrl = new URL(path, url).href;
          const response = await axios.get(testUrl, {
            timeout: 5000,
            validateStatus: () => true
          });

          if (response.status === 200) {
            const artifactInfo = {
              path: path,
              url: testUrl,
              size: response.data.length,
              contentType: response.headers['content-type'] || 'unknown',
              lastModified: response.headers['last-modified'],
              content: response.data.substring(0, 1000) // First 1KB for analysis
            };

            artifacts[category].push(artifactInfo);
            this.buildArtifacts.set(path, artifactInfo);

            // Analyze sensitive information in artifacts
            await this.analyzeSensitiveContent(artifactInfo, frameworkInfo);
          }

        } catch (error) {
          // Continue checking
        }
      }
    }

    this.logger.info(`✅ Build artifact discovery complete. Found ${Object.values(artifacts).flat().length} artifacts`);
    return artifacts;
  }

  async analyzeSensitiveContent(artifact, frameworkInfo) {
    const content = artifact.content.toLowerCase();
    
    // Check for sensitive information patterns
    const sensitivePatterns = [
      { pattern: /api[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'API Key' },
      { pattern: /secret["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'Secret' },
      { pattern: /password["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'Password' },
      { pattern: /token["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'Token' },
      { pattern: /database[_-]?url["\s]*[:=]["\s]*([^\s"]+)/gi, type: 'Database URL' },
      { pattern: /mongodb[_-]?uri["\s]*[:=]["\s]*([^\s"]+)/gi, type: 'MongoDB URI' },
      { pattern: /postgres[_-]?url["\s]*[:=]["\s]*([^\s"]+)/gi, type: 'PostgreSQL URL' },
      { pattern: /redis[_-]?url["\s]*[:=]["\s]*([^\s"]+)/gi, type: 'Redis URL' },
      { pattern: /aws[_-]?access[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'AWS Access Key' },
      { pattern: /aws[_-]?secret[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'AWS Secret Key' },
      { pattern: /stripe[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'Stripe Key' },
      { pattern: /github[_-]?token["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'GitHub Token' }
    ];

    for (const { pattern, type } of sensitivePatterns) {
      const matches = [...content.matchAll(pattern)];
      
      for (const match of matches) {
        const vulnerability = {
          type: 'Sensitive Information Exposure',
          severity: 'High',
          url: artifact.url,
          parameter: 'Build Artifact',
          payload: type,
          evidence: `${type} found in build artifact: ${match[1]?.substring(0, 20)}...`,
          response: artifact.content.substring(0, 500),
          confidence: 'High',
          sensitiveType: type,
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }

    // Check for source map exposure
    if (artifact.path.endsWith('.map') || content.includes('sourceMappingURL')) {
      const vulnerability = {
        type: 'Source Map Exposure',
        severity: 'Medium',
        url: artifact.url,
        parameter: 'Source Map',
        payload: 'Source map file accessible',
        evidence: 'Source maps expose original source code structure',
        response: artifact.content.substring(0, 500),
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logVulnerability(vulnerability);
    }
  }

  async analyzeServerlessFunctions(url, frameworkInfo) {
    this.logger.info('⚡ Analyzing serverless functions and API routes...');

    // Common serverless function patterns
    const functionPatterns = [
      '/api/',
      '/.netlify/functions/',
      '/.vercel/functions/',
      '/functions/',
      '/_functions/',
      '/lambda/',
      '/edge-functions/'
    ];

    for (const pattern of functionPatterns) {
      await this.discoverFunctionEndpoints(url, pattern);
    }

    // Test discovered endpoints
    for (const endpoint of this.discoveredEndpoints) {
      await this.testServerlessFunction(endpoint, frameworkInfo);
    }
  }

  async discoverFunctionEndpoints(baseUrl, pattern) {
    try {
      const testUrl = new URL(pattern, baseUrl).href;
      const response = await axios.get(testUrl, {
        timeout: 5000,
        validateStatus: () => true
      });

      if (response.status === 200 || response.status === 404) {
        // Try common function names
        const commonFunctions = [
          'hello',
          'test',
          'auth',
          'login',
          'user',
          'users',
          'api',
          'webhook',
          'contact',
          'submit',
          'upload',
          'download',
          'search',
          'health',
          'status'
        ];

        for (const funcName of commonFunctions) {
          try {
            const funcUrl = new URL(pattern + funcName, baseUrl).href;
            const funcResponse = await axios.get(funcUrl, {
              timeout: 5000,
              validateStatus: () => true
            });

            if (funcResponse.status !== 404) {
              this.discoveredEndpoints.add(funcUrl);
            }
          } catch (error) {
            // Continue
          }
        }
      }
    } catch (error) {
      // Continue
    }
  }

  async testServerlessFunction(endpoint, frameworkInfo) {
    const testCases = [
      // HTTP method testing
      { method: 'GET', description: 'GET request' },
      { method: 'POST', description: 'POST request', data: {} },
      { method: 'PUT', description: 'PUT request', data: {} },
      { method: 'DELETE', description: 'DELETE request' },
      { method: 'PATCH', description: 'PATCH request', data: {} },
      
      // Parameter injection testing
      { method: 'GET', params: { test: '"><script>alert("XSS")</script>' }, description: 'XSS in parameters' },
      { method: 'POST', data: { test: '"><script>alert("XSS")</script>' }, description: 'XSS in POST data' },
      { method: 'GET', params: { test: "' OR 1=1--" }, description: 'SQL injection in parameters' },
      { method: 'POST', data: { test: "' OR 1=1--" }, description: 'SQL injection in POST data' },
      
      // Command injection testing
      { method: 'GET', params: { cmd: '; ls -la' }, description: 'Command injection' },
      { method: 'POST', data: { command: '| whoami' }, description: 'Command injection in POST' },
      
      // SSRF testing
      { method: 'GET', params: { url: 'http://169.254.169.254/latest/meta-data/' }, description: 'SSRF attempt' },
      { method: 'POST', data: { callback: 'http://attacker.com' }, description: 'SSRF in callback' }
    ];

    for (const testCase of testCases) {
      try {
        let response;
        const config = {
          timeout: 10000,
          validateStatus: () => true,
          headers: {
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)',
            'Content-Type': 'application/json'
          }
        };

        if (testCase.params) {
          const testUrl = new URL(endpoint);
          Object.entries(testCase.params).forEach(([key, value]) => {
            testUrl.searchParams.set(key, value);
          });
          response = await axios.get(testUrl.href, config);
        } else if (testCase.data) {
          response = await axios[testCase.method.toLowerCase()](endpoint, testCase.data, config);
        } else {
          response = await axios[testCase.method.toLowerCase()](endpoint, config);
        }

        // Analyze response for vulnerabilities
        await this.analyzeServerlessResponse(response, testCase, endpoint);

      } catch (error) {
        // Analyze error responses too
        if (error.response) {
          await this.analyzeServerlessResponse(error.response, testCase, endpoint);
        }
      }
    }
  }

  async analyzeServerlessResponse(response, testCase, endpoint) {
    const vulnerabilities = [];
    
    // Check for XSS reflection
    if (testCase.description.includes('XSS') && 
        response.data && 
        response.data.includes('<script>alert("XSS")</script>')) {
      
      vulnerabilities.push({
        type: 'Cross-Site Scripting (XSS) in Serverless Function',
        severity: 'High',
        url: endpoint,
        parameter: 'Function Parameter',
        payload: testCase.params?.test || testCase.data?.test || 'XSS payload',
        evidence: 'XSS payload reflected in serverless function response',
        response: response.data.substring(0, 500),
        confidence: 'High'
      });
    }

    // Check for SQL injection indicators
    if (testCase.description.includes('SQL injection') && response.data) {
      const sqlErrorPatterns = [
        /sql.*error/i,
        /mysql.*error/i,
        /postgresql.*error/i,
        /sqlite.*error/i,
        /oracle.*error/i
      ];

      if (sqlErrorPatterns.some(pattern => pattern.test(response.data))) {
        vulnerabilities.push({
          type: 'SQL Injection in Serverless Function',
          severity: 'Critical',
          url: endpoint,
          parameter: 'Function Parameter',
          payload: testCase.params?.test || testCase.data?.test || 'SQL injection payload',
          evidence: 'SQL error message in serverless function response',
          response: response.data.substring(0, 500),
          confidence: 'High'
        });
      }
    }

    // Check for command injection indicators
    if (testCase.description.includes('Command injection') && response.data) {
      const commandIndicators = [
        /uid=\d+.*gid=\d+/i,
        /root:.*:0:0:/i,
        /total \d+/i,
        /directory of/i,
        /volume.*serial number/i
      ];

      if (commandIndicators.some(pattern => pattern.test(response.data))) {
        vulnerabilities.push({
          type: 'Command Injection in Serverless Function',
          severity: 'Critical',
          url: endpoint,
          parameter: 'Function Parameter',
          payload: testCase.params?.cmd || testCase.data?.command || 'Command injection payload',
          evidence: 'Command execution output in serverless function response',
          response: response.data.substring(0, 500),
          confidence: 'High'
        });
      }
    }

    // Check for SSRF indicators
    if (testCase.description.includes('SSRF') && response.data) {
      const ssrfIndicators = [
        /ami-id/i,
        /instance-id/i,
        /metadata/i,
        /169\.254\.169\.254/i
      ];

      if (ssrfIndicators.some(pattern => pattern.test(response.data))) {
        vulnerabilities.push({
          type: 'Server-Side Request Forgery (SSRF) in Serverless Function',
          severity: 'High',
          url: endpoint,
          parameter: 'Function Parameter',
          payload: testCase.params?.url || testCase.data?.callback || 'SSRF payload',
          evidence: 'SSRF indicators in serverless function response',
          response: response.data.substring(0, 500),
          confidence: 'Medium'
        });
      }
    }

    // Check for information disclosure
    if (response.data && (
      response.data.includes('Error:') ||
      response.data.includes('Exception:') ||
      response.data.includes('Stack trace:') ||
      response.data.includes('at ') && response.data.includes('.js:')
    )) {
      vulnerabilities.push({
        type: 'Information Disclosure in Serverless Function',
        severity: 'Medium',
        url: endpoint,
        parameter: 'Error Response',
        payload: testCase.description,
        evidence: 'Detailed error information exposed in serverless function',
        response: response.data.substring(0, 500),
        confidence: 'High'
      });
    }

    // Add all found vulnerabilities
    vulnerabilities.forEach(vuln => {
      vuln.timestamp = new Date().toISOString();
      this.vulnerabilities.push(vuln);
      this.logger.logVulnerability(vuln);
    });
  }

  async analyzeStaticAssets(url, frameworkInfo) {
    this.logger.info('🗂️ Analyzing static assets and file exposure...');

    // Common static asset paths to check
    const assetPaths = [
      '/static/',
      '/assets/',
      '/public/',
      '/uploads/',
      '/media/',
      '/images/',
      '/css/',
      '/js/',
      '/fonts/',
      '/_next/static/',
      '/.next/static/',
      '/dist/',
      '/build/'
    ];

    for (const assetPath of assetPaths) {
      await this.checkDirectoryListing(url, assetPath);
      await this.checkCommonFiles(url, assetPath);
    }
  }

  async checkDirectoryListing(baseUrl, path) {
    try {
      const testUrl = new URL(path, baseUrl).href;
      const response = await axios.get(testUrl, {
        timeout: 5000,
        validateStatus: () => true
      });

      if (response.status === 200 && (
        response.data.includes('Index of') ||
        response.data.includes('Directory listing') ||
        response.data.includes('<a href=')
      )) {
        const vulnerability = {
          type: 'Directory Listing Enabled',
          severity: 'Medium',
          url: testUrl,
          parameter: 'Directory Path',
          payload: path,
          evidence: 'Directory listing is enabled, exposing file structure',
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

  async checkCommonFiles(baseUrl, basePath) {
    const commonFiles = [
      '.env',
      '.env.local',
      '.env.production',
      'config.json',
      'package.json',
      'database.json',
      'backup.sql',
      'dump.sql',
      'users.json',
      'admin.json',
      'test.txt',
      'debug.log',
      'error.log',
      'access.log'
    ];

    for (const file of commonFiles) {
      try {
        const testUrl = new URL(basePath + file, baseUrl).href;
        const response = await axios.get(testUrl, {
          timeout: 5000,
          validateStatus: () => true
        });

        if (response.status === 200) {
          const severity = file.includes('.env') || file.includes('config') ? 'High' : 'Medium';
          
          const vulnerability = {
            type: 'Sensitive File Exposure',
            severity: severity,
            url: testUrl,
            parameter: 'File Path',
            payload: file,
            evidence: `Sensitive file accessible: ${file}`,
            response: response.data.substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);

          // Analyze file content for sensitive information
          await this.analyzeSensitiveContent({
            path: basePath + file,
            url: testUrl,
            content: response.data,
            contentType: response.headers['content-type'] || 'unknown'
          }, frameworkInfo);
        }
      } catch (error) {
        // Continue
      }
    }
  }

  async analyzeClientSideSecurity(url, frameworkInfo) {
    this.logger.info('🌐 Analyzing client-side security...');

    try {
      const response = await axios.get(url, {
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      const $ = cheerio.load(response.data);
      const htmlContent = response.data;

      // Check for CSP
      await this.analyzeCSP(response.headers, $);
      
      // Check for XSS vulnerabilities
      await this.analyzeClientSideXSS($, htmlContent, url);
      
      // Check for insecure dependencies
      await this.analyzeClientDependencies($, htmlContent);
      
      // Check for data exposure in client-side code
      await this.analyzeClientDataExposure(htmlContent);

    } catch (error) {
      this.logger.debug(`Client-side analysis failed: ${error.message}`);
    }
  }

  async analyzeCSP(headers, $) {
    const csp = headers['content-security-policy'] || 
                $('meta[http-equiv="Content-Security-Policy"]').attr('content');

    if (!csp) {
      const vulnerability = {
        type: 'Missing Content Security Policy',
        severity: 'Medium',
        url: 'Headers/Meta tags',
        parameter: 'CSP',
        payload: 'No CSP found',
        evidence: 'Content Security Policy is not implemented',
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logVulnerability(vulnerability);
    } else {
      // Analyze CSP for weaknesses
      const weaknesses = [];
      
      if (csp.includes("'unsafe-inline'")) {
        weaknesses.push("'unsafe-inline' directive allows inline scripts/styles");
      }
      
      if (csp.includes("'unsafe-eval'")) {
        weaknesses.push("'unsafe-eval' directive allows eval() function");
      }
      
      if (csp.includes('*')) {
        weaknesses.push("Wildcard (*) in CSP allows any source");
      }
      
      if (csp.includes('data:')) {
        weaknesses.push("data: scheme allowed in CSP");
      }

      if (weaknesses.length > 0) {
        const vulnerability = {
          type: 'Weak Content Security Policy',
          severity: 'Medium',
          url: 'CSP Header/Meta',
          parameter: 'CSP Configuration',
          payload: csp,
          evidence: weaknesses.join(', '),
          confidence: 'High',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }
  }

  async analyzeClientSideXSS($, htmlContent, baseUrl) {
    // Check for potential DOM XSS sinks
    const dangerousPatterns = [
      /innerHTML\s*=\s*.*location/gi,
      /document\.write\s*\(.*location/gi,
      /eval\s*\(.*location/gi,
      /setTimeout\s*\(.*location/gi,
      /setInterval\s*\(.*location/gi
    ];

    for (const pattern of dangerousPatterns) {
      if (pattern.test(htmlContent)) {
        const vulnerability = {
          type: 'Potential DOM-based XSS',
          severity: 'High',
          url: baseUrl,
          parameter: 'Client-side JavaScript',
          payload: 'DOM manipulation with user input',
          evidence: 'Dangerous JavaScript pattern detected that could lead to DOM XSS',
          confidence: 'Medium',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }

    // Check for reflected XSS in URL parameters
    const urlParams = new URL(baseUrl).searchParams;
    for (const [key, value] of urlParams) {
      if (htmlContent.includes(value) && value.length > 3) {
        const vulnerability = {
          type: 'Potential Reflected XSS',
          severity: 'High',
          url: baseUrl,
          parameter: key,
          payload: value,
          evidence: 'URL parameter value reflected in HTML without encoding',
          confidence: 'Medium',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }
  }

  async analyzeClientDependencies($, htmlContent) {
    // Extract script sources
    const scriptSources = [];
    $('script[src]').each((_, script) => {
      scriptSources.push($(script).attr('src'));
    });

    // Check for known vulnerable libraries
    const vulnerablePatterns = [
      { pattern: /jquery.*1\.[0-6]/i, library: 'jQuery', issue: 'Known XSS vulnerabilities' },
      { pattern: /angular.*1\.[0-5]/i, library: 'AngularJS', issue: 'Known security vulnerabilities' },
      { pattern: /lodash.*[0-3]\./i, library: 'Lodash', issue: 'Prototype pollution vulnerabilities' },
      { pattern: /moment.*2\.[0-9]\./i, library: 'Moment.js', issue: 'Regular expression DoS' }
    ];

    for (const src of scriptSources) {
      for (const { pattern, library, issue } of vulnerablePatterns) {
        if (pattern.test(src)) {
          const vulnerability = {
            type: 'Vulnerable JavaScript Library',
            severity: 'Medium',
            url: src,
            parameter: 'Script Source',
            payload: library,
            evidence: `${library}: ${issue}`,
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }
      }
    }

    // Check for CDN integrity
    $('script[src*="cdn"], link[href*="cdn"]').each((_, element) => {
      const integrity = $(element).attr('integrity');
      const crossorigin = $(element).attr('crossorigin');
      
      if (!integrity) {
        const src = $(element).attr('src') || $(element).attr('href');
        const vulnerability = {
          type: 'Missing Subresource Integrity',
          severity: 'Low',
          url: src,
          parameter: 'CDN Resource',
          payload: 'Missing SRI hash',
          evidence: 'CDN resource loaded without integrity check',
          confidence: 'High',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    });
  }

  async analyzeClientDataExposure(htmlContent) {
    // Check for exposed sensitive data in client-side code
    const sensitivePatterns = [
      { pattern: /api[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})/gi, type: 'API Key' },
      { pattern: /secret["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})/gi, type: 'Secret' },
      { pattern: /token["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})/gi, type: 'Token' },
      { pattern: /password["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)/gi, type: 'Password' },
      { pattern: /database[_-]?url["\s]*[:=]["\s]*([^\s"]+)/gi, type: 'Database URL' }
    ];

    for (const { pattern, type } of sensitivePatterns) {
      const matches = [...htmlContent.matchAll(pattern)];
      
      for (const match of matches) {
        const vulnerability = {
          type: 'Sensitive Data Exposure in Client-Side Code',
          severity: 'High',
          url: 'Client-side JavaScript',
          parameter: 'Embedded Data',
          payload: type,
          evidence: `${type} exposed in client-side code: ${match[1]?.substring(0, 20)}...`,
          confidence: 'High',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }
  }

  async analyzeBuildSecurity(url, frameworkInfo, artifacts) {
    this.logger.info('🔧 Analyzing build process and CI/CD security...');

    // Check for exposed build information
    await this.checkBuildInformation(artifacts);
    
    // Check for CI/CD configuration exposure
    await this.checkCICDExposure(url);
    
    // Check for dependency vulnerabilities
    await this.checkDependencyVulnerabilities(artifacts);
  }

  async checkBuildInformation(artifacts) {
    // Analyze build artifacts for sensitive information
    for (const [category, artifactList] of Object.entries(artifacts)) {
      for (const artifact of artifactList) {
        if (artifact.path.includes('BUILD_ID') || 
            artifact.path.includes('build-manifest') ||
            artifact.path.includes('webpack-runtime')) {
          
          const vulnerability = {
            type: 'Build Information Exposure',
            severity: 'Low',
            url: artifact.url,
            parameter: 'Build Artifact',
            payload: artifact.path,
            evidence: 'Build process information exposed to public',
            response: artifact.content,
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }
      }
    }
  }

  async checkCICDExposure(baseUrl) {
    const cicdPaths = [
      '/.github/workflows/',
      '/.gitlab-ci.yml',
      '/azure-pipelines.yml',
      '/buildspec.yml',
      '/Jenkinsfile',
      '/.travis.yml',
      '/.circleci/config.yml',
      '/netlify.toml',
      '/vercel.json'
    ];

    for (const path of cicdPaths) {
      try {
        const testUrl = new URL(path, baseUrl).href;
        const response = await axios.get(testUrl, {
          timeout: 5000,
          validateStatus: () => true
        });

        if (response.status === 200) {
          const vulnerability = {
            type: 'CI/CD Configuration Exposure',
            severity: 'Medium',
            url: testUrl,
            parameter: 'Configuration File',
            payload: path,
            evidence: 'CI/CD configuration file accessible to public',
            response: response.data.substring(0, 500),
            confidence: 'High',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);

          // Analyze CI/CD config for secrets
          await this.analyzeCICDSecrets(response.data, testUrl);
        }
      } catch (error) {
        // Continue
      }
    }
  }

  async analyzeCICDSecrets(configContent, configUrl) {
    const secretPatterns = [
      /\$\{\{\s*secrets\.([A-Z_]+)\s*\}\}/gi,
      /\$\{\{\s*env\.([A-Z_]+)\s*\}\}/gi,
      /process\.env\.([A-Z_]+)/gi
    ];

    for (const pattern of secretPatterns) {
      const matches = [...configContent.matchAll(pattern)];
      
      for (const match of matches) {
        if (match[1] && (
          match[1].includes('KEY') ||
          match[1].includes('SECRET') ||
          match[1].includes('TOKEN') ||
          match[1].includes('PASSWORD')
        )) {
          const vulnerability = {
            type: 'Potential Secret Reference in CI/CD',
            severity: 'Low',
            url: configUrl,
            parameter: 'Environment Variable',
            payload: match[1],
            evidence: `Secret reference found in CI/CD configuration: ${match[1]}`,
            confidence: 'Medium',
            timestamp: new Date().toISOString()
          };

          this.vulnerabilities.push(vulnerability);
          this.logger.logVulnerability(vulnerability);
        }
      }
    }
  }

  async checkDependencyVulnerabilities(artifacts) {
    // Look for package.json or yarn.lock files
    const packageFiles = artifacts.configFiles?.filter(artifact => 
      artifact.path.includes('package.json') || 
      artifact.path.includes('yarn.lock') ||
      artifact.path.includes('package-lock.json')
    ) || [];

    for (const packageFile of packageFiles) {
      try {
        const content = packageFile.content;
        
        if (packageFile.path.includes('package.json')) {
          const packageData = JSON.parse(content);
          await this.analyzeDependencies(packageData.dependencies || {}, packageFile.url);
          await this.analyzeDependencies(packageData.devDependencies || {}, packageFile.url);
        }
      } catch (error) {
        this.logger.debug(`Failed to parse package file: ${error.message}`);
      }
    }
  }

  async analyzeDependencies(dependencies, sourceUrl) {
    // Known vulnerable packages (simplified list)
    const knownVulnerable = {
      'lodash': { versions: ['<4.17.21'], issue: 'Prototype pollution' },
      'minimist': { versions: ['<1.2.6'], issue: 'Prototype pollution' },
      'serialize-javascript': { versions: ['<3.1.0'], issue: 'XSS vulnerability' },
      'node-fetch': { versions: ['<2.6.7'], issue: 'Information exposure' }
    };

    for (const [pkg, version] of Object.entries(dependencies)) {
      if (knownVulnerable[pkg]) {
        const vuln = knownVulnerable[pkg];
        const vulnerability = {
          type: 'Vulnerable Dependency',
          severity: 'Medium',
          url: sourceUrl,
          parameter: 'Package Dependency',
          payload: `${pkg}@${version}`,
          evidence: `${pkg}: ${vuln.issue} (vulnerable versions: ${vuln.versions.join(', ')})`,
          confidence: 'Medium',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }
    }
  }

  async analyzeConfiguration(url, frameworkInfo) {
    this.logger.info('⚙️ Analyzing configuration and environment...');

    // Check for exposed configuration files
    const configPaths = [
      '/next.config.js',
      '/nuxt.config.js',
      '/gatsby-config.js',
      '/svelte.config.js',
      '/vite.config.js',
      '/webpack.config.js',
      '/rollup.config.js',
      '/.env',
      '/.env.example',
      '/config.json',
      '/app.json'
    ];

    for (const configPath of configPaths) {
      await this.checkConfigurationFile(url, configPath);
    }

    // Check security headers
    await this.analyzeSecurityHeaders(url);
  }

  async checkConfigurationFile(baseUrl, configPath) {
    try {
      const testUrl = new URL(configPath, baseUrl).href;
      const response = await axios.get(testUrl, {
        timeout: 5000,
        validateStatus: () => true
      });

      if (response.status === 200) {
        const vulnerability = {
          type: 'Configuration File Exposure',
          severity: configPath.includes('.env') ? 'High' : 'Medium',
          url: testUrl,
          parameter: 'Configuration File',
          payload: configPath,
          evidence: 'Application configuration file accessible to public',
          response: response.data.substring(0, 500),
          confidence: 'High',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);

        // Analyze config content for sensitive information
        await this.analyzeSensitiveContent({
          path: configPath,
          url: testUrl,
          content: response.data,
          contentType: response.headers['content-type'] || 'unknown'
        }, {});
      }
    } catch (error) {
      // Continue
    }
  }

  async analyzeSecurityHeaders(url) {
    try {
      const response = await axios.get(url, {
        timeout: 5000
      });

      const headers = response.headers;
      const missingHeaders = [];

      // Check for important security headers
      const securityHeaders = [
        'strict-transport-security',
        'x-frame-options',
        'x-content-type-options',
        'x-xss-protection',
        'referrer-policy',
        'permissions-policy'
      ];

      for (const header of securityHeaders) {
        if (!headers[header]) {
          missingHeaders.push(header);
        }
      }

      if (missingHeaders.length > 0) {
        const vulnerability = {
          type: 'Missing Security Headers',
          severity: 'Medium',
          url: url,
          parameter: 'HTTP Headers',
          payload: missingHeaders.join(', '),
          evidence: `Missing security headers: ${missingHeaders.join(', ')}`,
          confidence: 'High',
          timestamp: new Date().toISOString()
        };

        this.vulnerabilities.push(vulnerability);
        this.logger.logVulnerability(vulnerability);
      }

    } catch (error) {
      this.logger.debug(`Security headers analysis failed: ${error.message}`);
    }
  }

  async analyzeThirdPartyIntegrations(url, frameworkInfo) {
    this.logger.info('🔗 Analyzing third-party integrations...');

    try {
      const response = await axios.get(url, {
        timeout: 10000
      });

      const $ = cheerio.load(response.data);
      const htmlContent = response.data;

      // Check for third-party scripts
      await this.analyzeThirdPartyScripts($);
      
      // Check for analytics and tracking
      await this.analyzeTrackingScripts($, htmlContent);
      
      // Check for payment integrations
      await this.analyzePaymentIntegrations($, htmlContent);
      
      // Check for social media integrations
      await this.analyzeSocialIntegrations($, htmlContent);

    } catch (error) {
      this.logger.debug(`Third-party integration analysis failed: ${error.message}`);
    }
  }

  async analyzeThirdPartyScripts($) {
    const thirdPartyDomains = new Set();
    
    $('script[src]').each((_, script) => {
      const src = $(script).attr('src');
      try {
        const domain = new URL(src, 'https://example.com').hostname;
        if (!domain.includes('localhost') && !domain.includes('127.0.0.1')) {
          thirdPartyDomains.add(domain);
        }
      } catch (error) {
        // Invalid URL
      }
    });

    if (thirdPartyDomains.size > 0) {
      const vulnerability = {
        type: 'Third-Party Script Dependencies',
        severity: 'Low',
        url: 'Third-party scripts',
        parameter: 'Script Sources',
        payload: Array.from(thirdPartyDomains).join(', '),
        evidence: `Application loads scripts from ${thirdPartyDomains.size} third-party domains`,
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logVulnerability(vulnerability);
    }
  }

  async analyzeTrackingScripts($, htmlContent) {
    const trackingPatterns = [
      { pattern: /google-analytics/i, service: 'Google Analytics' },
      { pattern: /googletagmanager/i, service: 'Google Tag Manager' },
      { pattern: /facebook\.net.*tr/i, service: 'Facebook Pixel' },
      { pattern: /hotjar/i, service: 'Hotjar' },
      { pattern: /mixpanel/i, service: 'Mixpanel' },
      { pattern: /segment\.(com|io)/i, service: 'Segment' }
    ];

    const detectedTrackers = [];
    
    for (const { pattern, service } of trackingPatterns) {
      if (pattern.test(htmlContent)) {
        detectedTrackers.push(service);
      }
    }

    if (detectedTrackers.length > 0) {
      const vulnerability = {
        type: 'Privacy Tracking Scripts',
        severity: 'Info',
        url: 'Tracking scripts',
        parameter: 'Analytics Integration',
        payload: detectedTrackers.join(', '),
        evidence: `Application includes tracking scripts: ${detectedTrackers.join(', ')}`,
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logVulnerability(vulnerability);
    }
  }

  async analyzePaymentIntegrations($, htmlContent) {
    const paymentPatterns = [
      { pattern: /stripe/i, service: 'Stripe' },
      { pattern: /paypal/i, service: 'PayPal' },
      { pattern: /square/i, service: 'Square' },
      { pattern: /braintree/i, service: 'Braintree' }
    ];

    const detectedPayments = [];
    
    for (const { pattern, service } of paymentPatterns) {
      if (pattern.test(htmlContent)) {
        detectedPayments.push(service);
      }
    }

    if (detectedPayments.length > 0) {
      const vulnerability = {
        type: 'Payment Integration Detected',
        severity: 'Info',
        url: 'Payment integration',
        parameter: 'Payment Service',
        payload: detectedPayments.join(', '),
        evidence: `Application integrates with payment services: ${detectedPayments.join(', ')}`,
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logVulnerability(vulnerability);
    }
  }

  async analyzeSocialIntegrations($, htmlContent) {
    const socialPatterns = [
      { pattern: /connect\.facebook\.net/i, service: 'Facebook SDK' },
      { pattern: /apis\.google\.com/i, service: 'Google APIs' },
      { pattern: /twitter\.com.*widgets/i, service: 'Twitter Widgets' },
      { pattern: /linkedin\.com.*platform/i, service: 'LinkedIn Platform' }
    ];

    const detectedSocial = [];
    
    for (const { pattern, service } of socialPatterns) {
      if (pattern.test(htmlContent)) {
        detectedSocial.push(service);
      }
    }

    if (detectedSocial.length > 0) {
      const vulnerability = {
        type: 'Social Media Integration',
        severity: 'Info',
        url: 'Social integration',
        parameter: 'Social Service',
        payload: detectedSocial.join(', '),
        evidence: `Application integrates with social platforms: ${detectedSocial.join(', ')}`,
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logVulnerability(vulnerability);
    }
  }

  async generateResults(target, frameworkInfo, artifacts) {
    const duration = Date.now() - this.startTime;
    const results = {
      target,
      timestamp: new Date().toISOString(),
      duration: `${Math.round(duration / 1000)}s`,
      frameworkInfo: frameworkInfo,
      buildArtifacts: {
        total: Object.values(artifacts).flat().length,
        byCategory: Object.fromEntries(
          Object.entries(artifacts).map(([key, value]) => [key, value.length])
        )
      },
      discoveredEndpoints: Array.from(this.discoveredEndpoints),
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

module.exports = JamstackScanner;