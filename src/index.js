#!/usr/bin/env node

const { Command } = require('commander');
const chalk = require('chalk');
const figlet = require('figlet');
const inquirer = require('inquirer');
const VulnerabilityScanner = require('./scanners/vulnerability-scanner');
const CacheAnalyzer = require('./analyzers/cache-analyzer');
const AuthTester = require('./testers/auth-tester');
const SQLAnalyzer = require('./analyzers/sql-analyzer');
const JamstackScanner = require('./scanners/jamstack-scanner');
const Logger = require('./utils/logger');

const program = new Command();
const logger = new Logger();

// Display banner
console.log(
  chalk.cyan(
    figlet.textSync('Project AEGIS', {
      font: 'Big',
      horizontalLayout: 'default',
      verticalLayout: 'default'
    })
  )
);

console.log(chalk.yellow('🛡️  Advanced Web Security Research Framework'));
console.log(chalk.red('⚠️  FOR AUTHORIZED TESTING ONLY - ETHICAL USE REQUIRED\n'));

program
  .name('aegis')
  .description('Advanced Web Security Research Framework')
  .version('1.0.0');

program
  .command('scan')
  .description('Run comprehensive vulnerability scan')
  .option('-u, --url <url>', 'Target URL to scan')
  .option('-d, --depth <number>', 'Crawl depth (default: 3)', '3')
  .option('-t, --threads <number>', 'Number of threads (default: 10)', '10')
  .option('-o, --output <file>', 'Output file for results')
  .action(async (options) => {
    if (!options.url) {
      console.log(chalk.red('❌ URL is required'));
      return;
    }
    
    logger.info(`Starting comprehensive scan of: ${options.url}`);
    const scanner = new VulnerabilityScanner();
    await scanner.scan(options);
  });

program
  .command('cache-analysis')
  .description('Analyze cache poisoning vulnerabilities')
  .option('-u, --url <url>', 'Target URL')
  .option('-p, --payloads <file>', 'Custom payloads file')
  .action(async (options) => {
    if (!options.url) {
      console.log(chalk.red('❌ URL is required'));
      return;
    }
    
    logger.info(`Analyzing cache vulnerabilities for: ${options.url}`);
    const analyzer = new CacheAnalyzer();
    await analyzer.analyze(options);
  });

program
  .command('auth-test')
  .description('Test authentication bypass vulnerabilities')
  .option('-u, --url <url>', 'Target URL')
  .option('-c, --credentials <file>', 'Credentials file')
  .action(async (options) => {
    if (!options.url) {
      console.log(chalk.red('❌ URL is required'));
      return;
    }
    
    logger.info(`Testing authentication bypass for: ${options.url}`);
    const tester = new AuthTester();
    await tester.test(options);
  });

program
  .command('sql-analysis')
  .description('Analyze SQL injection vulnerabilities')
  .option('-u, --url <url>', 'Target URL')
  .option('-p, --parameters <params>', 'Parameters to test')
  .action(async (options) => {
    if (!options.url) {
      console.log(chalk.red('❌ URL is required'));
      return;
    }
    
    logger.info(`Analyzing SQL injection vulnerabilities for: ${options.url}`);
    const analyzer = new SQLAnalyzer();
    await analyzer.analyze(options);
  });

program
  .command('jamstack-scan')
  .description('Scan Jamstack/SSG applications')
  .option('-u, --url <url>', 'Target URL')
  .option('-f, --framework <framework>', 'Framework type (next, gatsby, nuxt)')
  .action(async (options) => {
    if (!options.url) {
      console.log(chalk.red('❌ URL is required'));
      return;
    }
    
    logger.info(`Scanning Jamstack application: ${options.url}`);
    const scanner = new JamstackScanner();
    await scanner.scan(options);
  });

program
  .command('interactive')
  .description('Start interactive mode')
  .action(async () => {
    await startInteractiveMode();
  });

async function startInteractiveMode() {
  console.log(chalk.green('\n🔍 Starting Interactive Security Research Mode\n'));
  
  const answers = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: 'What would you like to do?',
      choices: [
        'Comprehensive Vulnerability Scan',
        'Cache Poisoning Analysis',
        'Authentication Bypass Testing',
        'SQL Injection Analysis',
        'Jamstack Security Scan',
        'Exit'
      ]
    }
  ]);

  switch (answers.action) {
    case 'Comprehensive Vulnerability Scan':
      await runVulnerabilityScan();
      break;
    case 'Cache Poisoning Analysis':
      await runCacheAnalysis();
      break;
    case 'Authentication Bypass Testing':
      await runAuthTesting();
      break;
    case 'SQL Injection Analysis':
      await runSQLAnalysis();
      break;
    case 'Jamstack Security Scan':
      await runJamstackScan();
      break;
    case 'Exit':
      console.log(chalk.yellow('👋 Goodbye!'));
      process.exit(0);
      break;
  }
}

async function runVulnerabilityScan() {
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'url',
      message: 'Enter target URL:',
      validate: input => input.length > 0
    },
    {
      type: 'number',
      name: 'depth',
      message: 'Crawl depth (1-10):',
      default: 3
    }
  ]);

  const scanner = new VulnerabilityScanner();
  await scanner.scan(answers);
  
  // Return to interactive mode
  setTimeout(() => startInteractiveMode(), 2000);
}

async function runCacheAnalysis() {
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'url',
      message: 'Enter target URL:',
      validate: input => input.length > 0
    }
  ]);

  const analyzer = new CacheAnalyzer();
  await analyzer.analyze(answers);
  
  setTimeout(() => startInteractiveMode(), 2000);
}

async function runAuthTesting() {
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'url',
      message: 'Enter target URL:',
      validate: input => input.length > 0
    }
  ]);

  const tester = new AuthTester();
  await tester.test(answers);
  
  setTimeout(() => startInteractiveMode(), 2000);
}

async function runSQLAnalysis() {
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'url',
      message: 'Enter target URL:',
      validate: input => input.length > 0
    }
  ]);

  const analyzer = new SQLAnalyzer();
  await analyzer.analyze(answers);
  
  setTimeout(() => startInteractiveMode(), 2000);
}

async function runJamstackScan() {
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'url',
      message: 'Enter target URL:',
      validate: input => input.length > 0
    },
    {
      type: 'list',
      name: 'framework',
      message: 'Select framework type:',
      choices: ['next', 'gatsby', 'nuxt', 'hugo', 'jekyll', 'auto-detect']
    }
  ]);

  const scanner = new JamstackScanner();
  await scanner.scan(answers);
  
  setTimeout(() => startInteractiveMode(), 2000);
}

// Error handling
process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
  process.exit(1);
});

// Parse command line arguments
program.parse();

module.exports = { program };