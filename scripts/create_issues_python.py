#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from datetime import datetime

def run_gh_command(args, capture_output=True):
    """Run GitHub CLI command with error handling"""
    try:
        result = subprocess.run(['gh'] + args, capture_output=capture_output, text=True, check=False)
        return result
    except FileNotFoundError:
        print("GitHub CLI (gh) not found")
        return None

def get_existing_issues():
    """Get list of existing EOL issues with details"""
    result = run_gh_command(['issue', 'list', '--search', 'in:title "EOL Alert:"', '--json', 'number,title,state,labels'])
    if result and result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
    return []

def get_issue_details(issue_number):
    """Get detailed information about a specific issue"""
    result = run_gh_command(['issue', 'view', str(issue_number), '--json', 'title,body,state,labels,number'])
    if result and result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
    return None

def close_issue(issue_number, tool_name, current_version, resolution):
    """Close an issue with a resolution comment"""
    comment = f"""✅ **EOL Issue Resolved**

**Tool:** {tool_name}
**Version:** {current_version}
**Resolution:** {resolution}
**Resolved on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This issue has been automatically closed because the EOL status has been resolved."""

    # Add resolution comment
    run_gh_command(['issue', 'comment', str(issue_number), '--body', comment])

    # Close the issue
    result = run_gh_command(['issue', 'close', str(issue_number)])

    if result and result.returncode == 0:
        print(f"Closed issue #{issue_number} for {tool_name} {current_version}")
        return True
    else:
        print(f"Failed to close issue #{issue_number} for {tool_name}")
        return False

def update_issue_status(issue_number, tool_name, current_version, new_status, new_criticality, new_eol_date, new_latest_version):
    """Update an existing issue with new status information"""
    comment = f"""📊 **Status Update**

**Tool:** {tool_name}
**Version:** {current_version}
**New Status:** {new_status}
**New Criticality:** {new_criticality}
**EOL Date:** {new_eol_date}
**Latest Version:** {new_latest_version}
**Updated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The status of this EOL issue has changed. Please review the updated information."""

    # Add update comment
    run_gh_command(['issue', 'comment', str(issue_number), '--body', comment])

    # Update labels - remove old criticality, add new one
    issue_details = get_issue_details(issue_number)
    if issue_details and 'labels' in issue_details:
        current_labels = [label['name'] for label in issue_details['labels']]

        # Remove old criticality labels
        labels_to_remove = [label for label in current_labels if label in ['critical', 'warning', 'low']]

        # Add new criticality label
        labels_to_add = [new_criticality]

        # Update labels
        if labels_to_remove:
            run_gh_command(['issue', 'edit', str(issue_number), '--remove-label', ','.join(labels_to_remove)])
        if labels_to_add:
            run_gh_command(['issue', 'edit', str(issue_number), '--add-label', ','.join(labels_to_add)])

    print(f"Updated issue #{issue_number} for {tool_name} {current_version}")

def parse_issue_title(title):
    """Parse issue title to extract tool information"""
    # Pattern: "EOL Alert: Tool Name Version - Status"
    pattern = r"EOL Alert: (.+?) (.+?) - (.+)"
    match = re.match(pattern, title)
    if match:
        return {
            'tool_name': match.group(1),
            'current_version': match.group(2),
            'old_status': match.group(3)
        }
    return None

def should_close_issue(current_tool, old_status):
    """Determine if an issue should be closed based on current status"""
    # Conditions for closing:
    # 1. Status improved from EOL to Supported
    if old_status == 'EOL' and current_tool['eol_status'] == 'Supported':
        return True

    # 2. Criticality improved significantly
    if old_status == 'EOL' and current_tool.get('criticality') in ['low', None]:
        return True

    # 3. Tool is no longer in the report (probably upgraded)
    # This is handled by the caller

    return False

def should_update_issue(current_tool, old_status):
    """Determine if an issue should be updated (but not closed)"""
    # Conditions for updating:
    # 1. Status changed but still problematic
    if current_tool['eol_status'] != old_status:
        return True

    # 2. Criticality changed
    current_criticality = current_tool.get('criticality', 'medium')
    old_criticality = 'critical' if old_status == 'EOL' else 'warning'
    if current_criticality != old_criticality:
        return True

    return False

def check_and_manage_existing_issues(current_tools):
    """Check all existing issues and close/update them as needed"""
    existing_issues = get_existing_issues()
    closed_count = 0
    updated_count = 0

    # Create a lookup dictionary for current tools
    current_tools_dict = {}
    for tool in current_tools:
        key = f"{tool['tool_name']}_{tool['current_version']}"
        current_tools_dict[key] = tool

    for issue in existing_issues:
        if issue['state'] == 'OPEN' and 'EOL Alert:' in issue['title']:
            # Parse the issue title to get tool info
            tool_info = parse_issue_title(issue['title'])
            if not tool_info:
                continue

            tool_name = tool_info['tool_name']
            tool_version = tool_info['current_version']
            old_status = tool_info['old_status']

            key = f"{tool_name}_{tool_version}"
            current_tool = current_tools_dict.get(key)

            if current_tool:
                # Tool still exists in current report
                if should_close_issue(current_tool, old_status):
                    resolution = f"Status improved from {old_status} to {current_tool['eol_status']}"
                    if close_issue(issue['number'], tool_name, tool_version, resolution):
                        closed_count += 1
                elif should_update_issue(current_tool, old_status):
                    # Update the issue with new status
                    new_criticality = current_tool.get('criticality', 'medium')
                    update_issue_status(
                        issue['number'],
                        tool_name,
                        tool_version,
                        current_tool['eol_status'],
                        new_criticality,
                        current_tool['eol_date'],
                        current_tool.get('latest_version', 'Unknown')
                    )
                    updated_count += 1
            else:
                # Tool not found in current report - probably upgraded or removed
                resolution = "Tool version no longer found in current report (likely upgraded or removed)"
                if close_issue(issue['number'], tool_name, tool_version, resolution):
                    closed_count += 1

    return closed_count, updated_count

def create_github_issue(tool_name, current_version, eol_status, eol_date, latest_version, criticality):
    """Create a GitHub issue for a tool"""
    issue_title = f"EOL Alert: {tool_name} {current_version} - {eol_status}"

    # Check if issue already exists (open or closed)
    existing_issues = get_existing_issues()
    for issue in existing_issues:
        if issue_title == issue['title']:
            if issue['state'] == 'OPEN':
                print(f"Issue already exists for: {tool_name} {current_version} (#{issue['number']})")
                return True
            else:
                # Reopen closed issue if it becomes problematic again
                print(f"Reopening closed issue for: {tool_name} {current_version} (#{issue['number']})")
                run_gh_command(['issue', 'reopen', str(issue['number'])])
                return True

    # Create issue body
    issue_body = f"""## EOL Status Alert

**Tool:** {tool_name}
**Current Version:** {current_version}
**Latest Version:** {latest_version}
**Status:** {eol_status}
**EOL Date:** {eol_date}
**Criticality:** {criticality}
**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### Recommended Actions:
- [ ] Upgrade to latest version ({latest_version})
- [ ] Review dependency compatibility
- [ ] Update documentation
- [ ] Test new version in staging environment

### Additional Context:
This alert was automatically generated by the EOL Check workflow."""

    # Create issue
    print(f"Creating issue for: {tool_name} {current_version}")

    # Use --body-file to avoid shell quoting issues
    temp_file = '/tmp/issue_body.md'
    with open(temp_file, 'w') as f:
        f.write(issue_body)

    result = run_gh_command([
        'issue', 'create',
        '--title', issue_title,
        '--body-file', temp_file,
        '--label', f'eol-alert,{criticality}'
    ])

    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)

    if result and result.returncode == 0:
        print(f"Successfully created issue for {tool_name}")
        return True
    else:
        print(f"Failed to create issue for {tool_name}")
        return False

def main():
    # Find the latest JSON report
    reports_dir = 'data/output/reports'
    if not os.path.exists(reports_dir):
        print(f"Reports directory not found: {reports_dir}")
        return

    json_files = [f for f in os.listdir(reports_dir) if f.endswith('.json')]
    if not json_files:
        print("No JSON reports found")
        return

    # Get the most recent report
    latest_report = max(json_files, key=lambda f: os.path.getmtime(os.path.join(reports_dir, f)))
    report_path = os.path.join(reports_dir, latest_report)

    print(f"Processing report: {latest_report}")

    # Load the report
    try:
        with open(report_path, 'r') as f:
            report_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON report: {e}")
        return

    current_tools = report_data['tools']

    # First, check and manage existing issues (close or update)
    print("Checking and managing existing issues...")
    closed_count, updated_count = check_and_manage_existing_issues(current_tools)
    print(f"Closed {closed_count} resolved issues, updated {updated_count} issues")

    # Filter critical and warning tools
    critical_tools = [tool for tool in current_tools if tool.get('criticality') == 'high']
    warning_tools = [tool for tool in current_tools if tool.get('criticality') == 'medium']

    print(f"Found {len(critical_tools)} critical tools and {len(warning_tools)} warning tools")

    # Create issues for critical tools
    critical_created = 0
    for tool in critical_tools:
        if create_github_issue(
            tool['tool_name'],
            tool['current_version'],
            tool['eol_status'],
            tool['eol_date'],
            tool.get('latest_version', 'Unknown'),
            'critical'
        ):
            critical_created += 1

    # Create issues for warning tools
    warning_created = 0
    for tool in warning_tools:
        if create_github_issue(
            tool['tool_name'],
            tool['current_version'],
            tool['eol_status'],
            tool['eol_date'],
            tool.get('latest_version', 'Unknown'),
            'warning'
        ):
            warning_created += 1

    print(f"\nSummary:")
    print(f"Closed issues: {closed_count}")
    print(f"Updated issues: {updated_count}")
    print(f"Critical issues created: {critical_created}/{len(critical_tools)}")
    print(f"Warning issues created: {warning_created}/{len(warning_tools)}")

if __name__ == "__main__":
    main()