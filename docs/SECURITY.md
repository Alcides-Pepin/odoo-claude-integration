# Security Guide

This document outlines security best practices for the Odoo MCP Server.

## 🔐 Authentication & Authorization

### Odoo User Setup

1. **Create Dedicated User**:
   - Create a dedicated user for Claude (`claude_bot`)
   - Never use admin or personal accounts
   - Set strong, unique password

2. **Minimal Permissions**:
   - Grant only necessary access rights
   - Review and limit group memberships
   - Use principle of least privilege

3. **User Configuration**:
   ```python
   # Recommended user groups
   - base.group_user (basic access)
   - base.group_partner_manager (if partner access needed)
   # Avoid admin groups unless absolutely necessary
   ```

### XML-RPC Security

1. **Enable XML-RPC Access**:
   - Ensure XML-RPC is enabled in Odoo
   - Use HTTPS for all communications
   - Consider IP whitelisting if possible

2. **Connection Security**:
   - Always use HTTPS/SSL
   - Verify SSL certificates
   - Use strong TLS versions (1.2+)

## 🛡️ Environment Security

### Environment Variables

1. **Never Commit Secrets**:
   ```bash
   # ❌ NEVER DO THIS
   ODOO_PASSWORD="password123"  # in code
   
   # ✅ DO THIS
   ODOO_PASSWORD=os.getenv('ODOO_PASSWORD')  # from env
   ```

2. **Secure Storage**:
   - Use platform-specific secret management
   - Railway: Environment variables
   - AWS: Parameter Store/Secrets Manager
   - GCP: Secret Manager
   - Azure: Key Vault

3. **Access Control**:
   - Limit who can view/modify environment variables
   - Use IAM policies where available
   - Audit access regularly

### File Permissions

```bash
# Secure file permissions
chmod 600 .env          # Owner read/write only
chmod 755 *.py          # Standard script permissions
chmod 644 *.md          # Documentation read-only
```

## 🚫 Operation Security

### Built-in Blacklist

The server includes a security blacklist for dangerous operations:

```python
SECURITY_BLACKLIST = {
    ('res.users', 'unlink'),           # Never delete users
    ('ir.model', 'unlink'),            # Never delete models
    ('ir.model.fields', 'unlink'),     # Never delete fields
    ('ir.module.module', 'button_immediate_uninstall'),  # Never uninstall modules
}
```

### Additional Restrictions

1. **Delete Operations**:
   - Limited to specific models
   - Require explicit approval
   - Log all delete operations

2. **Model Access**:
   - Whitelist approach for sensitive models
   - Validate model existence before operations
   - Check user permissions

3. **Input Validation**:
   - Sanitize all user inputs
   - Validate domain filters
   - Limit query complexity

## 📊 Monitoring & Auditing

### Security Logging

1. **Operation Logging**:
   ```python
   logger.info(f"User {user} executed {method} on {model}")
   logger.warning(f"Blocked operation: {operation}")
   logger.error(f"Authentication failed for {user}")
   ```

2. **Audit Trail**:
   - Log all API calls
   - Track user operations
   - Monitor failed attempts
   - Alert on suspicious activity

### Security Metrics

Track these security metrics:
- Authentication success/failure rates
- Blocked operations
- Unusual query patterns
- Connection anomalies

## 🔍 Vulnerability Management

### Regular Updates

1. **Dependencies**:
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   ```

2. **Security Scanning**:
   ```bash
   pip audit                    # Check for vulnerabilities
   safety check                 # Alternative security scanner
   ```

### Code Security

1. **Static Analysis**:
   ```bash
   bandit -r .                 # Security linter
   pylint --load-plugins=pylint_security
   ```

2. **Security Review**:
   - Regular code reviews
   - Penetration testing
   - Vulnerability assessments

## 🌐 Network Security

### HTTPS Configuration

1. **Railway (Automatic)**:
   - HTTPS enforced by default
   - Valid SSL certificates
   - HTTP redirects to HTTPS

2. **Custom Deployment**:
   ```nginx
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/private.key;
       ssl_protocols TLSv1.2 TLSv1.3;
   }
   ```

### Firewall Rules

```bash
# Allow only necessary ports
ufw allow 22/tcp          # SSH
ufw allow 443/tcp         # HTTPS
ufw deny 8080/tcp         # Block HTTP
ufw enable
```

## 🔒 Data Protection

### Data Minimization

1. **Limit Data Access**:
   - Only request necessary fields
   - Implement data retention policies
   - Regularly audit data usage

2. **Sensitive Data**:
   - Never log passwords
   - Mask sensitive information
   - Use encryption for data at rest

### GDPR Compliance

1. **Data Processing**:
   - Document data processing activities
   - Implement data subject rights
   - Ensure lawful basis for processing

2. **Privacy by Design**:
   - Minimize data collection
   - Implement access controls
   - Use pseudonymization where possible

## 🚨 Incident Response

### Security Incident Plan

1. **Detection**:
   - Monitor security logs
   - Set up alerts for anomalies
   - Regular security reviews

2. **Response**:
   - Isolate affected systems
   - Assess impact and scope
   - Notify relevant parties
   - Document incident

3. **Recovery**:
   - Restore from clean backups
   - Apply security patches
   - Update security measures

### Emergency Procedures

```bash
# Emergency shutdown
pkill -f mcp_server.py

# Revoke access
# 1. Change Odoo password
# 2. Remove user permissions
# 3. Update environment variables
```

## 📋 Security Checklist

### Pre-Deployment

- [ ] Dedicated Odoo user created
- [ ] Minimal permissions assigned
- [ ] Strong passwords set
- [ ] Environment variables configured
- [ ] Security blacklist reviewed
- [ ] Logging configured
- [ ] HTTPS enabled
- [ ] Dependencies updated
- [ ] Security scan passed

### Post-Deployment

- [ ] Health check accessible
- [ ] Logs monitored
- [ ] Metrics tracked
- [ ] Security alerts configured
- [ ] Incident response plan tested
- [ ] Regular security reviews scheduled

### Ongoing

- [ ] Monthly security reviews
- [ ] Quarterly penetration testing
- [ ] Annual security audit
- [ ] Continuous monitoring
- [ ] Regular updates applied

## 🆘 Security Contacts

- **Security Team**: security@company.com
- **Incident Response**: incident@company.com
- **Technical Support**: support@company.com

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Guide](https://python-security.readthedocs.io/)
- [Railway Security](https://docs.railway.app/reference/security)
- [Odoo Security](https://www.odoo.com/documentation/16.0/administration/security.html)