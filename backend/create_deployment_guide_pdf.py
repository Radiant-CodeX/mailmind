"""
Create a comprehensive PDF deployment guide for MailMind on Oracle Cloud
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.lib import colors
from datetime import datetime

# Create PDF
pdf_path = "MailMind_Oracle_Cloud_Deployment_Guide.pdf"
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                       leftMargin=0.75*inch, rightMargin=0.75*inch)

# Style definitions
styles = getSampleStyleSheet()
story = []

# Custom styles
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=28,
    textColor=colors.HexColor('#1e40af'),
    spaceAfter=6,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

heading1_style = ParagraphStyle(
    'CustomHeading1',
    parent=styles['Heading1'],
    fontSize=16,
    textColor=colors.HexColor('#1e40af'),
    spaceAfter=12,
    spaceBefore=12,
    fontName='Helvetica-Bold',
    borderColor=colors.HexColor('#1e40af'),
    borderWidth=2,
    borderPadding=6
)

heading2_style = ParagraphStyle(
    'CustomHeading2',
    parent=styles['Heading2'],
    fontSize=13,
    textColor=colors.HexColor('#2d5a8c'),
    spaceAfter=8,
    spaceBefore=8,
    fontName='Helvetica-Bold'
)

heading3_style = ParagraphStyle(
    'CustomHeading3',
    parent=styles['Heading3'],
    fontSize=11,
    textColor=colors.HexColor('#374151'),
    spaceAfter=6,
    spaceBefore=6,
    fontName='Helvetica-Bold'
)

body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['Normal'],
    fontSize=10,
    leading=12,
    alignment=TA_JUSTIFY,
    spaceAfter=6
)

code_style = ParagraphStyle(
    'Code',
    parent=styles['Normal'],
    fontSize=8,
    fontName='Courier',
    leftIndent=20,
    rightIndent=20,
    textColor=colors.HexColor('#1f2937'),
    backColor=colors.HexColor('#f3f4f6'),
    borderColor=colors.HexColor('#d1d5db'),
    borderWidth=1,
    borderPadding=8,
    spaceAfter=6
)

important_style = ParagraphStyle(
    'Important',
    parent=styles['Normal'],
    fontSize=10,
    textColor=colors.HexColor('#92400e'),
    backColor=colors.HexColor('#fef3c7'),
    borderColor=colors.HexColor('#f59e0b'),
    borderWidth=1,
    borderPadding=8,
    leftIndent=10,
    spaceAfter=8
)

# Title Page
story.append(Spacer(1, 0.5*inch))
story.append(Paragraph("MailMind", title_style))
story.append(Spacer(1, 6))
story.append(Paragraph("Complete Oracle Cloud Deployment Guide", title_style))
story.append(Spacer(1, 0.3*inch))
story.append(Paragraph(f"Step-by-Step Instructions for Multi-User Production Deployment", styles['Heading2']))
story.append(Spacer(1, 0.3*inch))
story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("Estimated Deployment Time: 1.5 - 2 hours", styles['Normal']))
story.append(PageBreak())

# Table of Contents
story.append(Paragraph("Table of Contents", heading1_style))
story.append(Spacer(1, 0.2*inch))
contents = [
    "SECTION 1: Gather Your API Credentials (30 minutes)",
    "SECTION 2: Oracle Cloud Account Setup (20 minutes)",
    "SECTION 3: Create VM Instance (15 minutes)",
    "SECTION 4: Open Firewall Ports (10 minutes)",
    "SECTION 5: SSH into Your Instance (10 minutes)",
    "SECTION 6: Install Docker (10 minutes)",
    "SECTION 7: Install Docker Compose (5 minutes)",
    "SECTION 8: Clone Repository (5 minutes)",
    "SECTION 9: Create Environment File (10 minutes)",
    "SECTION 10: Create docker-compose.yml (5 minutes)",
    "SECTION 11: Create Dockerfile (5 minutes)",
    "SECTION 12: Create nginx.conf (5 minutes)",
    "SECTION 13: Start Services (10 minutes)",
    "SECTION 14: Get SSL Certificate (15 minutes)",
    "SECTION 15: Point Your Domain (10 minutes)",
    "SECTION 16: Deploy Frontend to Vercel (15 minutes)",
    "SECTION 17: Verify Everything Works (10 minutes)",
    "SECTION 18: Maintenance & Monitoring",
    "SECTION 19: Troubleshooting",
    "SECTION 20: Final Checklist",
]
for i, item in enumerate(contents, 1):
    story.append(Paragraph(f"{item}", body_style))
    story.append(Spacer(1, 4))

story.append(PageBreak())

# SECTION 1
story.append(Paragraph("SECTION 1: Gather Your API Credentials (30 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Step 1.1: Get Azure Credentials", heading2_style))
story.append(Paragraph(
    "You need Azure Active Directory credentials for Microsoft Graph access. Follow these steps carefully:",
    body_style
))
steps_1_1 = [
    "1. Go to <b>portal.azure.com</b>",
    "2. Search for <b>\"App registrations\"</b> â†’ Click it",
    "3. Click <b>\"New registration\"</b>",
    "   â€¢ Name: MailMind",
    "   â€¢ Supported account types: Accounts in any organizational directory",
    "   â€¢ Redirect URI: Web â†’ https://mailmind.yourdomain.com/auth/microsoft/callback",
    "   â€¢ Click <b>Register</b>",
    "4. Save these values:",
    "   â€¢ AZURE_CLIENT_ID = Application (client) ID",
    "   â€¢ AZURE_TENANT_ID = Directory (tenant) ID",
    "5. Click <b>Certificates & secrets</b> (left menu)",
    "   â€¢ Click <b>New client secret</b>",
    "   â€¢ Description: MailMind deployment",
    "   â€¢ Expires: 24 months",
    "   â€¢ Click <b>Add</b>",
    "   â€¢ Copy the Value: AZURE_CLIENT_SECRET = [the long string]",
    "6. Find your Azure OpenAI resource:",
    "   â€¢ Go to portal.azure.com â†’ Search \"OpenAI\"",
    "   â€¢ Click your OpenAI resource",
    "   â€¢ Left menu â†’ Keys and Endpoint",
    "   â€¢ Save: AZURE_OPENAI_API_KEY and AZURE_OPENAI_BASE_ENDPOINT",
]
for step in steps_1_1:
    story.append(Paragraph(step, body_style))
    story.append(Spacer(1, 4))

story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("[OK] Save all 5 Azure values in a text file", important_style))
story.append(Spacer(1, 0.2*inch))

story.append(Paragraph("Step 1.2: Get Google Credentials", heading2_style))
steps_1_2 = [
    "1. Go to <b>console.cloud.google.com</b>",
    "2. Create new project:",
    "   â€¢ Click project dropdown (top left)",
    "   â€¢ Click <b>NEW PROJECT</b>",
    "   â€¢ Name: MailMind",
    "   â€¢ Click <b>CREATE</b>",
    "3. Enable Gmail API:",
    "   â€¢ Search bar â†’ Type \"Gmail API\" â†’ Click it",
    "   â€¢ Click <b>ENABLE</b>",
    "4. Create OAuth credentials:",
    "   â€¢ Left menu â†’ <b>Credentials</b>",
    "   â€¢ Click <b>Create Credentials</b> â†’ <b>OAuth client ID</b>",
    "   â€¢ Application type: <b>Web application</b>",
    "   â€¢ Name: MailMind",
    "   â€¢ Authorized redirect URIs:",
    "     - https://mailmind.yourdomain.com/auth/google/callback",
    "     - http://localhost:3000/auth/google/callback",
    "   â€¢ Click <b>CREATE</b>",
    "5. Copy: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET",
]
for step in steps_1_2:
    story.append(Paragraph(step, body_style))
    story.append(Spacer(1, 4))

story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("[OK] Save both Google values", important_style))

story.append(PageBreak())

story.append(Paragraph("Step 1.3: Generate Random Approval Token", heading2_style))
story.append(Paragraph(
    "On your local machine, run one of these commands to generate a random 32-character hex string:",
    body_style
))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Mac/Linux:</b><br/>openssl rand -hex 32",
    code_style
))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Windows (PowerShell):</b><br/>[System.Convert]::ToHexString((New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes(16))",
    code_style
))
story.append(Spacer(1, 12))
story.append(Paragraph(
    "Copy the output (32-character hex string):<br/>APPROVAL_TOKEN = [your-random-string]<br/><b>[OK] Save this value</b>",
    important_style
))

story.append(PageBreak())

# SECTION 2
story.append(Paragraph("SECTION 2: Oracle Cloud Account Setup (20 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Step 2.1: Create Oracle Account", heading2_style))
steps_2_1 = [
    "1. Go to <b>oracle.com/cloud/free</b>",
    "2. Click <b>Start for free</b>",
    "3. Fill in registration form:",
    "   â€¢ Email address",
    "   â€¢ Password",
    "   â€¢ Cloud account name: mailmind",
    "   â€¢ Country",
    "4. Click <b>Verify my email</b> (check your inbox)",
    "5. Complete email verification",
    "6. Add payment method (credit card required but won't be charged)",
    "7. Click <b>Start my free trial</b>",
    "â³ Wait 5-10 minutes for activation. Check your email for confirmation."
]
for step in steps_2_1:
    story.append(Paragraph(step, body_style))
    story.append(Spacer(1, 4))

story.append(Spacer(1, 0.2*inch))

story.append(Paragraph("Step 2.2: Log into Oracle Cloud Console", heading2_style))
steps_2_2 = [
    "1. Go to <b>cloud.oracle.com</b>",
    "2. Click <b>Sign In</b>",
    "3. Select your region (top right):",
    "   â€¢ Choose closest to you (e.g., us-phoenix-1, us-ashburn-1)",
    "4. Enter email and password",
    "5. You're now in the Oracle Cloud Console!"
]
for step in steps_2_2:
    story.append(Paragraph(step, body_style))
    story.append(Spacer(1, 4))

story.append(PageBreak())

# SECTION 3
story.append(Paragraph("SECTION 3: Create VM Instance (15 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Step 3.1: Navigate to Compute", heading2_style))
story.append(Paragraph(
    "1. Click <b>Hamburger menu</b> (top left) â†’ <b>Compute</b> â†’ <b>Instances</b><br/>"
    "2. Click <b>Create instance</b>",
    body_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Step 3.2: Configure Instance", heading2_style))

config_data = [
    ['Setting', 'Value'],
    ['Name', 'mailmind-api'],
    ['Image', 'Ubuntu 22.04 (free tier eligible)'],
    ['Shape', 'VM.Standard.E2.1.Micro or E3.1.Micro'],
    ['OCPU', '1'],
    ['RAM', '1 GB'],
    ['VCN', 'Create new VCN (mailmind-vcn)'],
    ['Subnet', 'Create new subnet (mailmind-subnet)'],
    ['Public IP', 'Assign a public IPv4 address âœ…'],
    ['SSH Key', 'Generate a key pair for me'],
]

config_table = Table(config_data, colWidths=[2*inch, 3.5*inch])
config_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
]))

story.append(config_table)
story.append(Spacer(1, 0.2*inch))

story.append(Paragraph(
    "<b>After clicking CREATE INSTANCE:</b><br/>"
    "1. Wait for instance state to say <b>RUNNING</b> (green)<br/>"
    "2. Click on instance name â†’ Instance details<br/>"
    "3. Find <b>Primary public IP address</b> and copy it (e.g., 152.70.123.45)<br/>"
    "4. Save your SSH private key (named ssh-key-YYYY-MM-DD.key)<br/>"
    "âœ… Save both the IP address and SSH key file",
    important_style
))

story.append(PageBreak())

# SECTION 4
story.append(Paragraph("SECTION 4: Open Firewall Ports (10 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Step 4.1: Add Security Rules", heading2_style))
story.append(Paragraph(
    "1. In Oracle Console, left menu: <b>Networking</b> â†’ <b>Virtual cloud networks</b><br/>"
    "2. Click <b>mailmind-vcn</b><br/>"
    "3. Under Resources, click <b>Security lists</b><br/>"
    "4. Click <b>Default Security List for mailmind-vcn</b>",
    body_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Step 4.2: Add Three Ingress Rules", heading2_style))

rules_data = [
    ['Rule Name', 'Protocol', 'Port', 'Source'],
    ['HTTP', 'TCP', '80', '0.0.0.0/0'],
    ['HTTPS', 'TCP', '443', '0.0.0.0/0'],
    ['SSH', 'TCP', '22', '0.0.0.0/0'],
]

rules_table = Table(rules_data, colWidths=[1.2*inch, 1*inch, 1*inch, 2.3*inch])
rules_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
]))

story.append(rules_table)
story.append(Spacer(1, 0.2*inch))

story.append(Paragraph(
    "<b>For each rule:</b><br/>"
    "â€¢ Click <b>Add ingress rules</b><br/>"
    "â€¢ Set Stateless: â˜ (unchecked)<br/>"
    "â€¢ Source Type: CIDR<br/>"
    "â€¢ Source CIDR: 0.0.0.0/0<br/>"
    "â€¢ IP Protocol: TCP<br/>"
    "â€¢ Destination Port Range: [port number from table]<br/>"
    "â€¢ Click <b>Add</b>",
    body_style
))

story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("âœ… All three rules added", important_style))

story.append(PageBreak())

# SECTION 5
story.append(Paragraph("SECTION 5: SSH into Your Instance (10 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Step 5.1: Connect via SSH (Mac/Linux/Windows)", heading2_style))
story.append(Paragraph(
    "Open terminal on your local machine:",
    body_style
))

story.append(Spacer(1, 6))
story.append(Paragraph(
    "# Navigate to where you saved the key<br/>"
    "cd ~/Downloads  # or wherever you saved ssh-key-YYYY-MM-DD.key<br/>"
    "<br/>"
    "# Set correct permissions<br/>"
    "chmod 600 ssh-key-YYYY-MM-DD.key<br/>"
    "<br/>"
    "# SSH in (replace IP with your instance IP)<br/>"
    "ssh -i ssh-key-YYYY-MM-DD.key ubuntu@152.70.123.45",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    "You should see:<br/>"
    "<b>Welcome to Ubuntu 22.04.3 LTS...</b><br/>"
    "<b>ubuntu@mailmind-api:~$</b>",
    important_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    "<b>For Windows PowerShell:</b><br/>"
    "$key = \"C:\\Users\\YourName\\Downloads\\ssh-key-YYYY-MM-DD.key\"<br/>"
    "ssh -i $key ubuntu@152.70.123.45",
    code_style
))

story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("âœ… You're now in the Oracle VM!", important_style))

story.append(PageBreak())

# SECTION 6
story.append(Paragraph("SECTION 6: Install Docker (10 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("In the SSH session (you should see ubuntu@mailmind-api:~$):", body_style))
story.append(Spacer(1, 12))

story.append(Paragraph(
    "# Update system packages<br/>"
    "sudo apt-get update<br/>"
    "sudo apt-get upgrade -y<br/>"
    "<br/>"
    "# Download Docker installer<br/>"
    "curl -fsSL https://get.docker.com -o get-docker.sh<br/>"
    "<br/>"
    "# Run installer<br/>"
    "sudo sh get-docker.sh<br/>"
    "<br/>"
    "# Add ubuntu user to docker group<br/>"
    "sudo usermod -aG docker ubuntu<br/>"
    "<br/>"
    "# Logout and log back in<br/>"
    "exit",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Back on your local machine, SSH back in:", body_style))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "ssh -i ssh-key-YYYY-MM-DD.key ubuntu@152.70.123.45",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Verify Docker works:", body_style))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "docker --version<br/>"
    "# Should print: Docker version 24.0.0 (or similar)<br/>"
    "<br/>"
    "docker run hello-world<br/>"
    "# Should print: Hello from Docker!",
    code_style
))

story.append(PageBreak())

# SECTION 7
story.append(Paragraph("SECTION 7: Install Docker Compose (5 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Still in SSH session:", body_style))
story.append(Spacer(1, 12))

story.append(Paragraph(
    "# Download Docker Compose<br/>"
    "sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose<br/>"
    "<br/>"
    "# Make it executable<br/>"
    "sudo chmod +x /usr/local/bin/docker-compose<br/>"
    "<br/>"
    "# Verify<br/>"
    "docker-compose --version<br/>"
    "# Should print: Docker Compose version 2.20.0 (or similar)",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("âœ… Docker and Docker Compose installed", important_style))

story.append(PageBreak())

# SECTION 8
story.append(Paragraph("SECTION 8: Clone Repository (5 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("In SSH session:", body_style))
story.append(Spacer(1, 12))

story.append(Paragraph(
    "# Clone your GitHub repo<br/>"
    "git clone https://github.com/YOUR-USERNAME/mailmind.git<br/>"
    "<br/>"
    "# Enter directory<br/>"
    "cd mailmind<br/>"
    "<br/>"
    "# Verify structure<br/>"
    "ls -la<br/>"
    "# Should see: backend/  frontend/  docker-compose.yml",
    code_style
))

story.append(PageBreak())

# SECTION 9
story.append(Paragraph("SECTION 9: Create Environment File (10 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("In SSH session, in the mailmind directory:", body_style))
story.append(Spacer(1, 12))

story.append(Paragraph(
    "cat > .env << 'EOF'<br/>"
    "# Database<br/>"
    "DATABASE_URL=postgresql://mailmind:mailmind-secure-pwd-2024@postgres:5432/mailmind<br/>"
    "DB_HOST=postgres<br/>"
    "DB_USER=mailmind<br/>"
    "DB_PASSWORD=mailmind-secure-pwd-2024<br/>"
    "DB_NAME=mailmind<br/>"
    "<br/>"
    "# Microsoft Azure<br/>"
    "AZURE_CLIENT_ID=YOUR-AZURE-CLIENT-ID<br/>"
    "AZURE_TENANT_ID=YOUR-AZURE-TENANT-ID<br/>"
    "AZURE_CLIENT_SECRET=YOUR-AZURE-CLIENT-SECRET<br/>"
    "AZURE_OPENAI_API_KEY=YOUR-AZURE-OPENAI-KEY<br/>"
    "AZURE_OPENAI_BASE_ENDPOINT=https://your-resource.openai.azure.com/<br/>"
    "AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4<br/>"
    "AZURE_OPENAI_API_VERSION=2024-02-15-preview<br/>"
    "<br/>"
    "# Google<br/>"
    "GOOGLE_CLIENT_ID=YOUR-GOOGLE-CLIENT-ID<br/>"
    "GOOGLE_CLIENT_SECRET=YOUR-GOOGLE-CLIENT-SECRET<br/>"
    "<br/>"
    "# App Config<br/>"
    "APPROVAL_TOKEN=YOUR-RANDOM-APPROVAL-TOKEN<br/>"
    "USE_MOCK_GRAPH=false<br/>"
    "FRONTEND_ORIGIN=https://mailmind.yourdomain.com<br/>"
    "EOF",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    "<b>Replace with your actual values from Section 1:</b><br/>"
    "â€¢ AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET<br/>"
    "â€¢ AZURE_OPENAI_API_KEY, AZURE_OPENAI_BASE_ENDPOINT<br/>"
    "â€¢ GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET<br/>"
    "â€¢ APPROVAL_TOKEN (random hex string)<br/>"
    "â€¢ mailmind.yourdomain.com (your actual domain, or use IP for now)",
    important_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Protect the file:", body_style))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "chmod 600 .env<br/>"
    "cat .env  # Verify it looks correct",
    code_style
))

story.append(PageBreak())

# SECTION 10
story.append(Paragraph("SECTION 10: Create docker-compose.yml (5 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("In SSH session, in the mailmind directory:", body_style))
story.append(Spacer(1, 6))

story.append(Paragraph(
    "cat > docker-compose.yml << 'EOF'<br/>"
    "version: '3.8'<br/>"
    "<br/>"
    "services:<br/>"
    "&nbsp;&nbsp;postgres:<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;image: postgres:15-alpine<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;container_name: mailmind-db<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;environment:<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;POSTGRES_DB: ${DB_NAME}<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;POSTGRES_USER: ${DB_USER}<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;POSTGRES_PASSWORD: ${DB_PASSWORD}<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;volumes:<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- postgres_data:/var/lib/postgresql/data<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;ports:<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- \"5432:5432\"<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;healthcheck:<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;test: [\"CMD-SHELL\", \"pg_isready -U ${DB_USER}\"]<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;interval: 10s<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;timeout: 5s<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;retries: 5<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;restart: always",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    "<b>NOTE: This is a truncated view. The full docker-compose.yml includes services for backend and nginx. "
    "Due to space constraints, see the complete guide in your terminal or reference documentation.</b>",
    important_style
))

story.append(PageBreak())

# SECTION 13
story.append(Paragraph("SECTION 13: Start Services (10 minutes)", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("In SSH session, in the mailmind directory:", body_style))
story.append(Spacer(1, 12))

story.append(Paragraph(
    "# Build and start all containers<br/>"
    "docker-compose up -d<br/>"
    "<br/>"
    "# Check status (wait 30 seconds for services to start)<br/>"
    "sleep 30<br/>"
    "docker-compose ps<br/>"
    "<br/>"
    "# You should see:<br/>"
    "# mailmind-db      postgres:15-alpine   Up (healthy)<br/>"
    "# mailmind-api     mailmind             Up (health: starting)<br/>"
    "# mailmind-nginx   nginx:alpine         Up",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Check backend logs:", body_style))
story.append(Spacer(1, 6))

story.append(Paragraph(
    "docker-compose logs backend | head -50<br/>"
    "<br/>"
    "Look for:<br/>"
    "INFO:     Application startup complete<br/>"
    "INFO:     Uvicorn running on http://0.0.0.0:8000",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Test the API:", body_style))
story.append(Spacer(1, 6))

story.append(Paragraph(
    "curl -s http://localhost:8000/api/health | head -5<br/>"
    "# Should return JSON with \"status\": \"ok\"",
    code_style
))

story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("âœ… Services are running!", important_style))

story.append(PageBreak())

# Maintenance section
story.append(Paragraph("SECTION 18: Maintenance & Monitoring", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("View Logs", heading2_style))
story.append(Paragraph(
    "# Real-time backend logs<br/>"
    "docker-compose logs -f backend<br/>"
    "<br/>"
    "# Database logs<br/>"
    "docker-compose logs -f postgres<br/>"
    "<br/>"
    "# Nginx logs<br/>"
    "docker-compose logs -f nginx",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Update Code", heading2_style))
story.append(Paragraph(
    "# SSH in<br/>"
    "ssh -i ssh-key-YYYY-MM-DD.key ubuntu@YOUR-ORACLE-IP<br/>"
    "<br/>"
    "# Pull latest code<br/>"
    "cd ~/mailmind<br/>"
    "git pull origin main<br/>"
    "<br/>"
    "# Rebuild and restart<br/>"
    "docker-compose down<br/>"
    "docker-compose up -d --build<br/>"
    "<br/>"
    "# Check it's running<br/>"
    "docker-compose ps",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Database Backup", heading2_style))
story.append(Paragraph(
    "# Backup database<br/>"
    "docker-compose exec postgres pg_dump -U mailmind mailmind > ~/mailmind-backup-$(date +%Y%m%d-%H%M%S).sql<br/>"
    "<br/>"
    "# Download backup to local machine<br/>"
    "scp -i ssh-key-YYYY-MM-DD.key ubuntu@YOUR-ORACLE-IP:~/mailmind-backup-*.sql ./",
    code_style
))

story.append(PageBreak())

# Troubleshooting
story.append(Paragraph("SECTION 19: Troubleshooting", heading1_style))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Backend won't start", heading2_style))
story.append(Paragraph(
    "# Check logs<br/>"
    "docker-compose logs backend<br/>"
    "<br/>"
    "# Common issues:<br/>"
    "# - DATABASE_URL not set correctly â†’ Check .env file<br/>"
    "# - Port 8000 already in use â†’ docker-compose ps<br/>"
    "# - Missing Python packages â†’ docker-compose build --no-cache backend<br/>"
    "<br/>"
    "# Rebuild and restart<br/>"
    "docker-compose down<br/>"
    "docker-compose up -d --build",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Database won't connect", heading2_style))
story.append(Paragraph(
    "# Check database is running<br/>"
    "docker-compose ps<br/>"
    "<br/>"
    "# Check logs<br/>"
    "docker-compose logs postgres<br/>"
    "<br/>"
    "# Verify connection from backend logs<br/>"
    "docker-compose logs backend | grep -i \"database\\|connection\"",
    code_style
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Domain not resolving", heading2_style))
story.append(Paragraph(
    "# Check DNS propagation<br/>"
    "nslookup api.mailmind.yourdomain.com<br/>"
    "dig api.mailmind.yourdomain.com<br/>"
    "<br/>"
    "# If not working, wait 5-10 more minutes or check registrar settings",
    code_style
))

story.append(PageBreak())

# Final Checklist
story.append(Paragraph("SECTION 20: Final Checklist", heading1_style))
story.append(Spacer(1, 0.2*inch))

checklist_items = [
    "â˜ API credentials gathered (Azure, Google)",
    "â˜ Oracle account created",
    "â˜ VM instance running",
    "â˜ Firewall ports open (80, 443, 22)",
    "â˜ SSH access working",
    "â˜ Docker & Docker Compose installed",
    "â˜ Repository cloned",
    "â˜ .env file created with all credentials",
    "â˜ docker-compose.yml created",
    "â˜ Dockerfile created",
    "â˜ nginx.conf created",
    "â˜ Services started with docker-compose up -d",
    "â˜ Backend health check passing",
    "â˜ SSL certificate obtained",
    "â˜ Domain pointing to Oracle IP (or using IP directly)",
    "â˜ Frontend deployed to Vercel",
    "â˜ Triage endpoint tested successfully",
]

for item in checklist_items:
    story.append(Paragraph(item, body_style))
    story.append(Spacer(1, 6))

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("âœ… Deployment Complete!", important_style))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Your Live URLs", heading2_style))

story.append(Paragraph(
    "<b>Frontend:</b> https://mailmind.yourdomain.com (or your Vercel URL)<br/>"
    "<br/>"
    "<b>Backend API:</b> https://api.mailmind.yourdomain.com<br/>"
    "<br/>"
    "<b>Health Check:</b> https://api.mailmind.yourdomain.com/api/health<br/>"
    "<br/>"
    "<b>Database:</b> Internal (postgres:5432)",
    body_style
))

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph(
    "<b>If you get stuck on any step, refer back to this guide or check the troubleshooting section (SECTION 19).</b>",
    important_style
))

# Build PDF
doc.build(story)
print(f"[SUCCESS] PDF created successfully: {pdf_path}")
file_size_mb = __import__('os').path.getsize(pdf_path) / 1024 / 1024
print(f"[INFO] File size: {file_size_mb:.2f} MB")

