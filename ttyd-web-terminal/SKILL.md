---
name: ttyd-web-terminal
description: >
  When users need to access the terminal through a browser, please use this skill
---
# ttyd Web Terminal Deployment Skill

This skill deploys and manages a web-based terminal service using ttyd on port 5222.

## Usage

To deploy the ttyd web terminal service:

1. Run the deployment script:
   ```bash
   sh /var/minis/skills/ttyd-web-terminal/scripts/deploy.sh
   ```

2. Access the terminal in your browser at `http://[device-ip]:5222`

3. Manage the service using scripts in the skill directory:
   - Start: `sh /var/minis/skills/ttyd-web-terminal/scripts/start`
   - Stop: `sh /var/minis/skills/ttyd-web-terminal/scripts/stop` 
   - Status: `sh /var/minis/skills/ttyd-web-terminal/scripts/status`

## Technical Details

- Port: 5222
- Process: ttyd with improved configuration parameters
- Log file: /root/ttyd.log
- PID file: /root/ttyd.pid

## Management Scripts

All management scripts are located in the skill directory:
- `start` - Smart startup script (checks if ttyd is installed and running)
- `stop` - Clean service shutdown
- `status` - Service status monitoring with detailed informationy
