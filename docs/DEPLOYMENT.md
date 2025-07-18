# Deployment Guide

This guide covers deploying the Odoo MCP Server to Railway and other platforms.

## 🚀 Railway Deployment

Railway is the recommended platform for production deployment due to its simplicity and built-in features.

### Prerequisites

- GitHub account
- Railway account (free tier available)
- Odoo instance with XML-RPC access

### Step 1: Prepare Repository

1. **Fork the repository** on GitHub or create a new repository with the project files

2. **Ensure all files are committed**:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

3. **Verify local setup** works:
   ```bash
   # Create .env file
   cp .env.example .env
   # Edit .env with your credentials
   # Test locally
   python odoo_mcp_server.py
   ```

### Step 2: Deploy to Railway

1. **Go to Railway**:
   - Visit [railway.app](https://railway.app)
   - Sign in with GitHub

2. **Create new project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Configure environment variables**:
   - Go to your project settings
   - Add these environment variables:
     - `ODOO_URL`: Your Odoo instance URL
     - `ODOO_DB`: Your database name
     - `ODOO_USER`: Odoo username (preferably a bot user)
     - `ODOO_PASSWORD`: Odoo password

4. **Deploy**:
   - Railway will automatically detect the Procfile
   - Deployment should start automatically
   - Wait for deployment to complete

### Step 3: Test Deployment

1. **Get your Railway URL**:
   - Go to your project dashboard
   - Copy the generated URL (e.g., `https://project-name.railway.app`)

2. **Test health check**:
   ```bash
   curl https://your-project.railway.app/health
   ```

3. **Monitor logs**:
   - Check Railway logs for any errors
   - Look for "Server ready!" message

### Step 4: Configure Claude

Update your Claude configuration with the Railway URL:

```json
{
  "mcpServers": {
    "odoo": {
      "url": "https://your-project.railway.app"
    }
  }
}
```

## 🐳 Docker Deployment

For containerized deployment:

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "odoo_mcp_server.py"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  odoo-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ODOO_URL=${ODOO_URL}
      - ODOO_DB=${ODOO_DB}
      - ODOO_USER=${ODOO_USER}
      - ODOO_PASSWORD=${ODOO_PASSWORD}
    env_file:
      - .env
```

## ☁️ Other Platforms

### Heroku

1. Install Heroku CLI
2. Create Heroku app:
   ```bash
   heroku create your-app-name
   ```
3. Set environment variables:
   ```bash
   heroku config:set ODOO_URL=https://your-instance.odoo.com
   heroku config:set ODOO_DB=your-database
   heroku config:set ODOO_USER=claude_bot
   heroku config:set ODOO_PASSWORD=your-password
   ```
4. Deploy:
   ```bash
   git push heroku main
   ```

### AWS/GCP/Azure

Use the Docker image with your preferred container service:
- AWS ECS/EKS
- Google Cloud Run
- Azure Container Instances

## 🔧 Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `ODOO_URL` | Odoo instance URL | `https://company.odoo.com` |
| `ODOO_DB` | Database name | `company-db-main` |
| `ODOO_USER` | Odoo username | `claude_bot` |
| `ODOO_PASSWORD` | Odoo password | `secure-password` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |
| `TIMEOUT` | XML-RPC timeout | `30` |
| `PORT` | Server port | `8000` |

## 📊 Monitoring

### Health Check

The server provides a health check endpoint:
```
GET /health
```

### Logs

Monitor logs for:
- Connection errors
- Authentication failures
- Performance issues
- Security events

### Metrics

Track:
- Response times
- Error rates
- Connection success rate
- Request volume

## 🔒 Security Considerations

1. **Environment Variables**: Never commit secrets to git
2. **User Permissions**: Create dedicated Odoo user with minimal permissions
3. **Network Security**: Use HTTPS in production
4. **Rate Limiting**: Consider implementing rate limiting
5. **Audit Logging**: Monitor all operations for security

## 🆘 Troubleshooting

### Common Issues

1. **Authentication Failures**:
   - Check credentials in environment variables
   - Verify Odoo user has XML-RPC access
   - Test connection manually

2. **Connection Timeouts**:
   - Check network connectivity
   - Verify Odoo instance is accessible
   - Increase timeout if needed

3. **Permission Errors**:
   - Ensure Odoo user has required permissions
   - Check security groups and access rights

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python odoo_mcp_server.py
```

### Support

- Check Railway logs for errors
- Review Odoo server logs
- Test with health check endpoint
- Verify environment variables are set correctly