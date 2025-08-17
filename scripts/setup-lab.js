#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');
const chalk = require('chalk');

class LabSetup {
  constructor() {
    this.labDir = path.join(process.cwd(), 'lab');
    this.appsDir = path.join(this.labDir, 'apps');
  }

  async setup() {
    console.log(chalk.cyan('🧪 Setting up Project AEGIS Security Testing Lab\n'));
    
    try {
      await this.createDirectoryStructure();
      await this.createDockerCompose();
      await this.createVulnerableApps();
      await this.createTestScripts();
      await this.displayInstructions();
    } catch (error) {
      console.error(chalk.red('❌ Lab setup failed:'), error.message);
      process.exit(1);
    }
  }

  async createDirectoryStructure() {
    console.log(chalk.blue('📁 Creating lab directory structure...'));
    
    const directories = [
      this.labDir,
      this.appsDir,
      path.join(this.appsDir, 'dvwa'),
      path.join(this.appsDir, 'vulnerable-jamstack'),
      path.join(this.appsDir, 'cache-lab'),
      path.join(this.labDir, 'configs'),
      path.join(this.labDir, 'data'),
      path.join(this.labDir, 'scripts')
    ];

    for (const dir of directories) {
      await fs.mkdir(dir, { recursive: true });
    }
    
    console.log(chalk.green('✅ Directory structure created'));
  }

  async createDockerCompose() {
    console.log(chalk.blue('🐳 Creating Docker Compose configuration...'));
    
    const dockerCompose = `version: '3.8'

services:
  # DVWA - Damn Vulnerable Web Application
  dvwa:
    image: vulnerables/web-dvwa:latest
    container_name: aegis-dvwa
    ports:
      - "8080:80"
    environment:
      - MYSQL_ROOT_PASSWORD=password
      - MYSQL_DATABASE=dvwa
      - MYSQL_USER=dvwa
      - MYSQL_PASSWORD=password
    volumes:
      - ./data/dvwa:/var/lib/mysql
    networks:
      - aegis-lab
    restart: unless-stopped

  # Vulnerable Jamstack Application
  vulnerable-jamstack:
    build: 
      context: ./apps/vulnerable-jamstack
      dockerfile: Dockerfile
    container_name: aegis-jamstack
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - API_KEY=sk-test-vulnerable-key-12345
      - DATABASE_URL=mongodb://mongo:27017/vulnerable-app
    networks:
      - aegis-lab
    depends_on:
      - mongo
    restart: unless-stopped

  # MongoDB for Jamstack app
  mongo:
    image: mongo:5
    container_name: aegis-mongo
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=password
    volumes:
      - ./data/mongo:/data/db
    networks:
      - aegis-lab
    restart: unless-stopped

  # Varnish Cache for cache poisoning testing
  varnish:
    image: varnish:7
    container_name: aegis-varnish
    ports:
      - "8081:80"
    volumes:
      - ./configs/varnish/default.vcl:/etc/varnish/default.vcl:ro
    command: ["varnishd", "-F", "-f", "/etc/varnish/default.vcl", "-s", "malloc,256m", "-a", "0.0.0.0:80"]
    networks:
      - aegis-lab
    depends_on:
      - cache-backend
    restart: unless-stopped

  # Backend for cache testing
  cache-backend:
    build:
      context: ./apps/cache-lab
      dockerfile: Dockerfile
    container_name: aegis-cache-backend
    ports:
      - "8082:3000"
    networks:
      - aegis-lab
    restart: unless-stopped

  # PostgreSQL for SQL injection testing
  postgres:
    image: postgres:13
    container_name: aegis-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=testdb
      - POSTGRES_USER=testuser
      - POSTGRES_PASSWORD=testpass
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./configs/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - aegis-lab
    restart: unless-stopped

  # Redis for NoSQL testing
  redis:
    image: redis:7-alpine
    container_name: aegis-redis
    ports:
      - "6379:6379"
    command: redis-server --requirepass testpass
    volumes:
      - ./data/redis:/data
    networks:
      - aegis-lab
    restart: unless-stopped

networks:
  aegis-lab:
    driver: bridge

volumes:
  dvwa-data:
  mongo-data:
  postgres-data:
  redis-data:
`;

    await fs.writeFile(path.join(this.labDir, 'docker-compose.yml'), dockerCompose);
    console.log(chalk.green('✅ Docker Compose configuration created'));
  }

  async createVulnerableApps() {
    await this.createVulnerableJamstackApp();
    await this.createCacheLabApp();
    await this.createVarnishConfig();
    await this.createPostgresInit();
  }

  async createVulnerableJamstackApp() {
    console.log(chalk.blue('⚡ Creating vulnerable Jamstack application...'));
    
    const jamstackDir = path.join(this.appsDir, 'vulnerable-jamstack');
    
    // package.json
    const packageJson = {
      "name": "vulnerable-jamstack-app",
      "version": "1.0.0",
      "description": "Intentionally vulnerable Jamstack application for security testing",
      "main": "server.js",
      "scripts": {
        "start": "node server.js",
        "dev": "node server.js",
        "build": "next build"
      },
      "dependencies": {
        "next": "12.0.0",
        "react": "17.0.2",
        "react-dom": "17.0.2",
        "express": "4.17.1",
        "mongodb": "4.1.0",
        "jsonwebtoken": "8.5.1",
        "bcrypt": "5.0.1",
        "lodash": "4.17.20"
      }
    };

    await fs.writeFile(
      path.join(jamstackDir, 'package.json'), 
      JSON.stringify(packageJson, null, 2)
    );

    // Dockerfile
    const dockerfile = `FROM node:16-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
`;

    await fs.writeFile(path.join(jamstackDir, 'Dockerfile'), dockerfile);

    // Vulnerable server.js
    const serverJs = `const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const { MongoClient } = require('mongodb');
const _ = require('lodash');

const app = express();
const PORT = 3000;

// Intentionally vulnerable: weak JWT secret
const JWT_SECRET = 'secret';

app.use(express.json());
app.use(express.static('public'));

// Vulnerable endpoint: SQL injection simulation
app.get('/api/users', async (req, res) => {
  const { id } = req.query;
  
  // Intentionally vulnerable: direct query construction
  const query = \`SELECT * FROM users WHERE id = '\${id}'\`;
  console.log('Executing query:', query);
  
  // Simulate SQL injection vulnerability
  if (id && id.includes("'")) {
    return res.json({ 
      error: "SQL syntax error near '" + id + "'",
      query: query 
    });
  }
  
  res.json({ users: [{ id: 1, name: 'admin', role: 'administrator' }] });
});

// Vulnerable endpoint: XSS
app.get('/api/search', (req, res) => {
  const { q } = req.query;
  
  // Intentionally vulnerable: no input sanitization
  res.send(\`<h1>Search results for: \${q}</h1>\`);
});

// Vulnerable endpoint: Command injection
app.post('/api/ping', (req, res) => {
  const { host } = req.body;
  const { exec } = require('child_process');
  
  // Intentionally vulnerable: command injection
  exec(\`ping -c 1 \${host}\`, (error, stdout, stderr) => {
    if (error) {
      return res.json({ error: error.message, stdout, stderr });
    }
    res.json({ result: stdout });
  });
});

// Vulnerable endpoint: JWT bypass
app.post('/api/auth', (req, res) => {
  const { username, password } = req.body;
  
  // Intentionally weak authentication
  if (username && password) {
    const token = jwt.sign({ username, role: 'user' }, JWT_SECRET);
    res.json({ token });
  } else {
    res.status(401).json({ error: 'Authentication failed' });
  }
});

// Vulnerable endpoint: Parameter pollution
app.post('/api/update-profile', (req, res) => {
  const data = req.body;
  
  // Intentionally vulnerable: parameter pollution
  const profile = {};
  
  // This allows overriding values through parameter pollution
  Object.assign(profile, data);
  
  res.json({ profile, message: 'Profile updated' });
});

// Vulnerable: Exposed environment variables
app.get('/api/config', (req, res) => {
  res.json({
    apiKey: process.env.API_KEY,
    databaseUrl: process.env.DATABASE_URL,
    jwtSecret: JWT_SECRET
  });
});

// Serve vulnerable static files
app.get('/.env', (req, res) => {
  res.send(\`API_KEY=sk-test-vulnerable-key-12345
DATABASE_URL=mongodb://mongo:27017/vulnerable-app
JWT_SECRET=secret
ADMIN_PASSWORD=admin123\`);
});

app.listen(PORT, () => {
  console.log(\`Vulnerable Jamstack app running on port \${PORT}\`);
});
`;

    await fs.writeFile(path.join(jamstackDir, 'server.js'), serverJs);

    // Create public directory with vulnerable client-side code
    const publicDir = path.join(jamstackDir, 'public');
    await fs.mkdir(publicDir, { recursive: true });

    const indexHtml = `<!DOCTYPE html>
<html>
<head>
    <title>Vulnerable Jamstack App</title>
    <script src="https://code.jquery.com/jquery-1.6.0.min.js"></script>
</head>
<body>
    <h1>Vulnerable Jamstack Application</h1>
    <div id="content"></div>
    
    <script>
        // Vulnerable: DOM XSS
        function search() {
            const query = new URLSearchParams(window.location.search).get('q');
            if (query) {
                document.getElementById('content').innerHTML = 'Search: ' + query;
            }
        }
        
        // Vulnerable: Exposed API key
        const API_KEY = 'sk-test-vulnerable-key-12345';
        
        // Vulnerable: eval() usage
        function processData(data) {
            eval('var result = ' + data);
            return result;
        }
        
        search();
    </script>
</body>
</html>`;

    await fs.writeFile(path.join(publicDir, 'index.html'), indexHtml);

    console.log(chalk.green('✅ Vulnerable Jamstack application created'));
  }

  async createCacheLabApp() {
    console.log(chalk.blue('🗄️ Creating cache poisoning lab application...'));
    
    const cacheLabDir = path.join(this.appsDir, 'cache-lab');
    
    const packageJson = {
      "name": "cache-poisoning-lab",
      "version": "1.0.0",
      "description": "Cache poisoning testing application",
      "main": "server.js",
      "dependencies": {
        "express": "4.17.1",
        "uuid": "8.3.2"
      }
    };

    await fs.writeFile(
      path.join(cacheLabDir, 'package.json'), 
      JSON.stringify(packageJson, null, 2)
    );

    const dockerfile = `FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
`;

    await fs.writeFile(path.join(cacheLabDir, 'Dockerfile'), dockerfile);

    const serverJs = `const express = require('express');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = 3000;

app.use(express.json());

// Vulnerable to cache poisoning via X-Forwarded-Host
app.get('/api/data', (req, res) => {
  const host = req.headers['x-forwarded-host'] || req.headers.host;
  
  res.json({
    id: uuidv4(),
    host: host,
    timestamp: new Date().toISOString(),
    data: 'This response can be poisoned via X-Forwarded-Host header'
  });
});

// Vulnerable to cache poisoning via unkeyed parameters
app.get('/content', (req, res) => {
  const { callback, format } = req.query;
  
  let response = '<h1>Content Page</h1>';
  
  if (callback) {
    response += \`<script>\${callback}()</script>\`;
  }
  
  if (format === 'json') {
    res.json({ content: response });
  } else {
    res.send(response);
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(\`Cache lab application running on port \${PORT}\`);
});
`;

    await fs.writeFile(path.join(cacheLabDir, 'server.js'), serverJs);

    console.log(chalk.green('✅ Cache poisoning lab application created'));
  }

  async createVarnishConfig() {
    console.log(chalk.blue('🏗️ Creating Varnish configuration...'));
    
    const configsDir = path.join(this.labDir, 'configs', 'varnish');
    await fs.mkdir(configsDir, { recursive: true });

    const vclConfig = `vcl 4.0;

backend default {
    .host = "cache-backend";
    .port = "3000";
}

sub vcl_recv {
    # Remove some headers that might be used for cache poisoning
    unset req.http.X-Forwarded-For;
    
    # But keep X-Forwarded-Host for testing purposes (vulnerable)
    # unset req.http.X-Forwarded-Host;
    
    # Remove other potentially dangerous headers
    unset req.http.X-Real-IP;
    unset req.http.X-Original-URL;
    
    return (hash);
}

sub vcl_hash {
    hash_data(req.url);
    hash_data(req.http.host);
    
    # Intentionally NOT hashing X-Forwarded-Host (vulnerable)
    # This makes X-Forwarded-Host an unkeyed input
    
    return (lookup);
}

sub vcl_deliver {
    # Add cache status header
    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
    } else {
        set resp.http.X-Cache = "MISS";
    }
    
    # Add cache key for debugging
    set resp.http.X-Cache-Key = req.url + req.http.host;
    
    return (deliver);
}
`;

    await fs.writeFile(path.join(configsDir, 'default.vcl'), vclConfig);
    console.log(chalk.green('✅ Varnish configuration created'));
  }

  async createPostgresInit() {
    console.log(chalk.blue('🐘 Creating PostgreSQL initialization script...'));
    
    const configsDir = path.join(this.labDir, 'configs', 'postgres');
    await fs.mkdir(configsDir, { recursive: true });

    const initSql = `-- Initialize vulnerable database for SQL injection testing

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2),
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER DEFAULT 1,
    total DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert test data
INSERT INTO users (username, password, email, role) VALUES
('admin', 'admin123', 'admin@test.com', 'administrator'),
('user1', 'password123', 'user1@test.com', 'user'),
('user2', 'password456', 'user2@test.com', 'user'),
('testuser', 'test123', 'test@test.com', 'user');

INSERT INTO products (name, description, price, category) VALUES
('Laptop', 'High-performance laptop', 999.99, 'electronics'),
('Phone', 'Smartphone with camera', 599.99, 'electronics'),
('Book', 'Programming guide', 39.99, 'books'),
('Headphones', 'Wireless headphones', 199.99, 'electronics');

INSERT INTO orders (user_id, product_id, quantity, total) VALUES
(2, 1, 1, 999.99),
(3, 2, 1, 599.99),
(2, 4, 2, 399.98);

-- Create a view for testing
CREATE VIEW user_orders AS
SELECT u.username, p.name as product_name, o.quantity, o.total, o.created_at
FROM orders o
JOIN users u ON o.user_id = u.id
JOIN products p ON o.product_id = p.id;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO testuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO testuser;
`;

    await fs.writeFile(path.join(configsDir, 'init.sql'), initSql);
    console.log(chalk.green('✅ PostgreSQL initialization script created'));
  }

  async createTestScripts() {
    console.log(chalk.blue('📝 Creating test scripts...'));
    
    const scriptsDir = path.join(this.labDir, 'scripts');
    
    // Test runner script
    const testRunner = `#!/bin/bash

echo "🧪 Running Project AEGIS Lab Tests"
echo "================================="

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Test DVWA
echo "🔍 Testing DVWA..."
npm run vulnerability-scan -- --url http://localhost:8080 --depth 2

# Test Vulnerable Jamstack App
echo "⚡ Testing Vulnerable Jamstack App..."
npm run jamstack-scan -- --url http://localhost:3000 --framework next

# Test Cache Poisoning
echo "💀 Testing Cache Poisoning..."
npm run cache-analysis -- --url http://localhost:8081

# Test SQL Injection
echo "💉 Testing SQL Injection..."
npm run sql-analysis -- --url http://localhost:3000/api/users --parameters "id"

# Test Authentication Bypass
echo "🔓 Testing Authentication Bypass..."
npm run auth-test -- --url http://localhost:3000

echo "✅ All tests completed!"
echo "📊 Check the logs/ directory for detailed results"
`;

    await fs.writeFile(path.join(scriptsDir, 'run-tests.sh'), testRunner);
    await fs.chmod(path.join(scriptsDir, 'run-tests.sh'), '755');

    // Health check script
    const healthCheck = `#!/bin/bash

echo "🏥 Checking Lab Service Health"
echo "============================="

services=(
  "http://localhost:8080|DVWA"
  "http://localhost:3000|Jamstack App"
  "http://localhost:8081|Varnish Cache"
  "http://localhost:8082|Cache Backend"
)

for service in "\${services[@]}"; do
  IFS='|' read -r url name <<< "$service"
  
  if curl -f -s "$url" > /dev/null; then
    echo "✅ $name is healthy"
  else
    echo "❌ $name is not responding"
  fi
done

echo ""
echo "🐳 Docker Container Status:"
docker-compose ps
`;

    await fs.writeFile(path.join(scriptsDir, 'health-check.sh'), healthCheck);
    await fs.chmod(path.join(scriptsDir, 'health-check.sh'), '755');

    console.log(chalk.green('✅ Test scripts created'));
  }

  async displayInstructions() {
    console.log(chalk.green('\n🎉 Lab setup completed successfully!\n'));
    
    console.log(chalk.yellow('📋 Next Steps:'));
    console.log(chalk.white('1. Start the lab environment:'));
    console.log(chalk.cyan('   cd lab && docker-compose up -d\n'));
    
    console.log(chalk.white('2. Wait for services to start (30-60 seconds), then check health:'));
    console.log(chalk.cyan('   ./lab/scripts/health-check.sh\n'));
    
    console.log(chalk.white('3. Run automated tests:'));
    console.log(chalk.cyan('   ./lab/scripts/run-tests.sh\n'));
    
    console.log(chalk.yellow('🌐 Available Services:'));
    console.log(chalk.white('• DVWA (Damn Vulnerable Web App): http://localhost:8080'));
    console.log(chalk.white('• Vulnerable Jamstack App: http://localhost:3000'));
    console.log(chalk.white('• Varnish Cache (for cache poisoning): http://localhost:8081'));
    console.log(chalk.white('• Cache Backend: http://localhost:8082'));
    console.log(chalk.white('• PostgreSQL: localhost:5432 (testuser/testpass)'));
    console.log(chalk.white('• MongoDB: localhost:27017 (admin/password)'));
    console.log(chalk.white('• Redis: localhost:6379 (password: testpass)\n'));
    
    console.log(chalk.yellow('🔧 Manual Testing Examples:'));
    console.log(chalk.cyan('# Test SQL injection'));
    console.log(chalk.white("curl \"http://localhost:3000/api/users?id=1' OR '1'='1\""));
    console.log(chalk.cyan('\n# Test XSS'));
    console.log(chalk.white('curl "http://localhost:3000/api/search?q=<script>alert(\\'XSS\\')</script>"'));
    console.log(chalk.cyan('\n# Test cache poisoning'));
    console.log(chalk.white('curl -H "X-Forwarded-Host: evil.com" http://localhost:8081/api/data\n'));
    
    console.log(chalk.red('⚠️  Remember: This lab contains intentionally vulnerable applications.'));
    console.log(chalk.red('   Only use in isolated environments for authorized security testing!\n'));
  }
}

// Run setup if called directly
if (require.main === module) {
  const setup = new LabSetup();
  setup.setup().catch(console.error);
}

module.exports = LabSetup;