# Odoo Claude Integration - MCP Server

Production-ready MCP server for integrating Claude AI with Odoo ERP systems via XML-RPC API.

## 🚀 Features

- **Health Monitoring**: Built-in health check endpoint for system monitoring
- **Model Discovery**: Explore available Odoo models and their fields
- **Generic Operations**: Execute any Odoo method with safety controls
- **Advanced Search**: Powerful search capabilities with filtering and pagination
- **Security First**: Environment variable configuration and operation blacklisting
- **Production Ready**: Logging, error handling, and timeout management

## 📋 Prerequisites

- Python 3.8+
- Access to an Odoo instance with XML-RPC API enabled
- Claude Desktop or Claude Web configured for MCP

## 🛠️ Installation

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/odoo-claude-integration.git
cd odoo-claude-integration
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the template:
```bash
cp .env.example .env
```

4. Edit `.env` with your Odoo credentials:
```
ODOO_URL=https://your-instance.odoo.com
ODOO_DB=your-database-name
ODOO_USER=claude_bot
ODOO_PASSWORD=your-secure-password
```

5. Run the server:
```bash
python odoo_mcp_server.py
```

## 🚀 Railway Deployment

1. Fork this repository on GitHub

2. Go to [railway.app](https://railway.app) and create a new project

3. Connect your GitHub repository

4. Set environment variables in Railway:
   - `ODOO_URL`
   - `ODOO_DB`
   - `ODOO_USER`
   - `ODOO_PASSWORD`

5. Deploy! Railway will automatically detect the Procfile and start your server

## 🔧 Claude Configuration

### Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": ["/path/to/odoo_mcp_server.py"]
    }
  }
}
```

### Claude Web (with Railway URL)

```json
{
  "mcpServers": {
    "odoo": {
      "url": "https://your-project.railway.app"
    }
  }
}
```

## 📚 Available Tools

### `odoo_health_check`
Check system health and connectivity:
```
odoo_health_check()
```

### `odoo_discover_models`
Find available models:
```
odoo_discover_models("partner")
```

### `odoo_get_model_fields`
Get model field details:
```
odoo_get_model_fields("res.partner")
```

### `odoo_search`
Search records with filters:
```
odoo_search("res.partner", [["is_company", "=", True]], ["name", "email"], limit=10)
```

### `odoo_execute`
Execute any model method:
```
odoo_execute("res.partner", "create", [{"name": "New Partner"}])
```

## 🔐 Security

- Credentials stored in environment variables
- Operation blacklisting for dangerous actions
- Comprehensive logging for audit trails
- Input validation and sanitization
- HTTPS enforced on Railway

## 📊 Monitoring

The server includes:
- Health check endpoint at `/health`
- Structured logging with timestamps
- Error tracking and reporting
- Performance monitoring

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Create an issue on GitHub
- Check the [deployment guide](docs/DEPLOYMENT.md)
- Review [security best practices](docs/SECURITY.md)