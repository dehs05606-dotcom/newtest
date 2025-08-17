const winston = require('winston');
const chalk = require('chalk');
const fs = require('fs');
const path = require('path');

class Logger {
  constructor() {
    // Ensure logs directory exists
    const logsDir = path.join(process.cwd(), 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }

    // Custom format for console output
    const consoleFormat = winston.format.combine(
      winston.format.timestamp({ format: 'HH:mm:ss' }),
      winston.format.printf(({ timestamp, level, message, ...meta }) => {
        const colorMap = {
          error: chalk.red,
          warn: chalk.yellow,
          info: chalk.blue,
          debug: chalk.gray,
          success: chalk.green,
          vulnerability: chalk.magenta,
          critical: chalk.red.bold
        };

        const colorFn = colorMap[level] || chalk.white;
        const metaStr = Object.keys(meta).length ? JSON.stringify(meta, null, 2) : '';
        
        return `${chalk.gray(timestamp)} ${colorFn(`[${level.toUpperCase()}]`)} ${message} ${metaStr}`;
      })
    );

    // File format
    const fileFormat = winston.format.combine(
      winston.format.timestamp(),
      winston.format.json()
    );

    this.logger = winston.createLogger({
      level: 'debug',
      levels: {
        error: 0,
        warn: 1,
        info: 2,
        success: 3,
        vulnerability: 4,
        critical: 5,
        debug: 6
      },
      transports: [
        // Console transport
        new winston.transports.Console({
          format: consoleFormat
        }),
        // File transport for general logs
        new winston.transports.File({
          filename: path.join(logsDir, 'aegis.log'),
          format: fileFormat,
          maxsize: 5242880, // 5MB
          maxFiles: 5
        }),
        // Separate file for vulnerabilities
        new winston.transports.File({
          filename: path.join(logsDir, 'vulnerabilities.log'),
          level: 'vulnerability',
          format: fileFormat,
          maxsize: 5242880,
          maxFiles: 10
        }),
        // Critical security events
        new winston.transports.File({
          filename: path.join(logsDir, 'critical.log'),
          level: 'critical',
          format: fileFormat,
          maxsize: 5242880,
          maxFiles: 10
        })
      ]
    });

    // Add custom levels to winston
    winston.addColors({
      error: 'red',
      warn: 'yellow',
      info: 'blue',
      success: 'green',
      vulnerability: 'magenta',
      critical: 'red',
      debug: 'gray'
    });
  }

  info(message, meta = {}) {
    this.logger.info(message, meta);
  }

  error(message, meta = {}) {
    this.logger.error(message, meta);
  }

  warn(message, meta = {}) {
    this.logger.warn(message, meta);
  }

  debug(message, meta = {}) {
    this.logger.debug(message, meta);
  }

  success(message, meta = {}) {
    this.logger.log('success', message, meta);
  }

  vulnerability(message, meta = {}) {
    this.logger.log('vulnerability', message, meta);
  }

  critical(message, meta = {}) {
    this.logger.log('critical', message, meta);
  }

  // Security-specific logging methods
  logVulnerability(vuln) {
    const vulnData = {
      type: vuln.type,
      severity: vuln.severity,
      url: vuln.url,
      parameter: vuln.parameter,
      payload: vuln.payload,
      response: vuln.response?.substring(0, 500), // Limit response size
      timestamp: new Date().toISOString(),
      confidence: vuln.confidence
    };

    this.vulnerability(`🚨 Vulnerability Found: ${vuln.type}`, vulnData);
  }

  logScanStart(target, scanType) {
    this.info(`🔍 Starting ${scanType} scan`, { target, scanType, timestamp: new Date().toISOString() });
  }

  logScanComplete(target, scanType, results) {
    const summary = {
      target,
      scanType,
      vulnerabilitiesFound: results.vulnerabilities?.length || 0,
      duration: results.duration,
      timestamp: new Date().toISOString()
    };

    this.success(`✅ ${scanType} scan completed`, summary);
  }

  logAuthBypass(attempt) {
    this.critical(`🔓 Authentication Bypass Attempt`, {
      url: attempt.url,
      method: attempt.method,
      payload: attempt.payload,
      success: attempt.success,
      timestamp: new Date().toISOString()
    });
  }

  logCachePoisoning(attempt) {
    this.vulnerability(`💀 Cache Poisoning Detected`, {
      url: attempt.url,
      headers: attempt.headers,
      payload: attempt.payload,
      cached: attempt.cached,
      timestamp: new Date().toISOString()
    });
  }

  logSQLInjection(attempt) {
    this.vulnerability(`💉 SQL Injection Detected`, {
      url: attempt.url,
      parameter: attempt.parameter,
      payload: attempt.payload,
      evidence: attempt.evidence,
      dbType: attempt.dbType,
      timestamp: new Date().toISOString()
    });
  }

  // Progress logging
  progress(current, total, operation) {
    const percentage = Math.round((current / total) * 100);
    const progressBar = '█'.repeat(Math.floor(percentage / 5)) + '░'.repeat(20 - Math.floor(percentage / 5));
    
    process.stdout.write(`\r${chalk.blue('[PROGRESS]')} ${operation}: [${progressBar}] ${percentage}% (${current}/${total})`);
    
    if (current === total) {
      console.log(); // New line when complete
    }
  }

  // Banner for different scan types
  scanBanner(scanType, target) {
    const banner = `
╔══════════════════════════════════════════════════════════════╗
║                    PROJECT AEGIS                             ║
║              ${scanType.toUpperCase().padEnd(20)} SCAN                    ║
║                                                              ║
║  Target: ${target.padEnd(48)} ║
║  Time: ${new Date().toISOString().padEnd(50)} ║
║  Status: AUTHORIZED TESTING ONLY                             ║
╚══════════════════════════════════════════════════════════════╝
    `;
    
    console.log(chalk.cyan(banner));
  }

  // Summary report
  generateSummary(results) {
    const summary = `
╔══════════════════════════════════════════════════════════════╗
║                      SCAN SUMMARY                            ║
╠══════════════════════════════════════════════════════════════╣
║  Total Vulnerabilities: ${String(results.total || 0).padStart(31)} ║
║  Critical: ${String(results.critical || 0).padStart(43)} ║
║  High: ${String(results.high || 0).padStart(47)} ║
║  Medium: ${String(results.medium || 0).padStart(45)} ║
║  Low: ${String(results.low || 0).padStart(48)} ║
║  Info: ${String(results.info || 0).padStart(47)} ║
║                                                              ║
║  Scan Duration: ${String(results.duration || 'N/A').padStart(38)} ║
║  URLs Tested: ${String(results.urlsTested || 0).padStart(40)} ║
║  Parameters Tested: ${String(results.paramsTested || 0).padStart(34)} ║
╚══════════════════════════════════════════════════════════════╝
    `;

    console.log(chalk.green(summary));
    this.info('Scan Summary Generated', results);
  }
}

module.exports = Logger;