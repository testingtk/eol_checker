import json
import os
from datetime import datetime


def ensure_output_dir(output_dir):
    """Ensure output directory exists"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        return True
    except Exception:
        return False


def load_tools_from_json(file_path):
    """Load tools data from JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        tools_data = []

        if isinstance(data, list):
            for item in data:
                name = item.get('name', item.get('tool_name', 'Unknown'))
                version = item.get('version', item.get('current_version', 'Unknown'))
                tool_data = {
                    'name': str(name),
                    'version': str(version)
                }

                # Add additional fields
                for key, value in item.items():
                    if key not in ['name', 'tool_name', 'version', 'current_version']:
                        tool_data[key] = value

                tools_data.append(tool_data)

        return tools_data
    except Exception:
        return []


def save_results_json(results, filename='eol_report', output_dir='data/output/reports'):
    """Save results to JSON file"""
    try:
        if not ensure_output_dir(output_dir):
            output_dir = '.'  # Fallback to current directory

        output_file = os.path.join(output_dir, f"{filename}.json")

        # Prepare data for JSON output
        output_data = {
            "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "tools": results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        return output_file
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return None


def save_results_html(results, filename='eol_report', output_dir='data/output/reports'):
    """Save results to HTML file"""
    try:
        if not ensure_output_dir(output_dir):
            output_dir = '.'  # Fallback to current directory

        output_file = os.path.join(output_dir, f"{filename}.html")

        # Calculate statistics
        eol_count = sum(1 for r in results if r['eol_status'] == 'EOL')
        supported_count = sum(1 for r in results if r['eol_status'] == 'Supported')
        unknown_count = sum(1 for r in results if r['eol_status'] == 'Unknown')


        critical_eol = [r for r in results if r['eol_status'] == 'EOL' and r.get('criticality') == 'high']
        warning_eol = [r for r in results if r['eol_status'] == 'EOL' and r.get('criticality') != 'high']
        warning_count = sum(1 for r in results if r.get('criticality') == 'medium')

        # Generate HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>EOL Tool Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 20px; }}
        .summary {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px; }}
        .critical {{ background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 15px 0; }}
        .warning {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin: 15px 0; }}
        .success {{ background: #e8f5e8; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .status-eol {{ color: #d32f2f; font-weight: bold; }}
        .status-supported {{ color: #388e3c; font-weight: bold; }}
        .status-unknown {{ color: #f57c00; font-weight: bold; }}
        .badge {{ padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; color: white; }}
        .badge-critical {{ background: #d32f2f; }}
        .badge-warning {{ background: #f57c00; }}
        .badge-info {{ background: #1976d2; }}
        .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }}
        .latest-version {{ color: #1976d2; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛠️ EOL Tool Status Report</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary">
            <h2>📊 Summary</h2>
            <p><strong>Total Tools:</strong> {len(results)}</p>
            <p><strong>✅ Supported:</strong> {supported_count}</p>
            <p><strong>❌ EOL:</strong> {eol_count}</p>
            <p><strong>❓ Unknown:</strong> {unknown_count}</p>
            <p><strong>⚠️ Warning:</strong> {warning_count}</p>
        </div>
"""

        # Critical EOL section
        if critical_eol:
            html_content += f"""
        <div class="critical">
            <h2>🚨 CRITICAL EOL TOOLS ({len(critical_eol)})</h2>
            <ul>
"""
            for tool in critical_eol:
                html_content += f"                <li><strong>{tool['tool_name']} {tool['current_version']}</strong> - EOL Date: {tool['eol_date']} (Latest: {tool.get('latest_version', 'Unknown')})</li>\n"
            html_content += "            </ul>\n        </div>\n"

        # Warning EOL section
        if warning_eol:
            html_content += f"""
        <div class="warning">
            <h2>⚠️ EOL WARNINGS ({len(warning_eol)})</h2>
            <ul>
"""
            for tool in warning_eol:
                html_content += f"                <li><strong>{tool['tool_name']} {tool['current_version']}</strong> - EOL Date: {tool['eol_date']} (Latest: {tool.get('latest_version', 'Unknown')})</li>\n"
            html_content += "            </ul>\n        </div>\n"

        # Table section
        html_content += """
        <h2>📋 Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Tool</th>
                    <th>Current Version</th>
                    <th>Latest Version</th>
                    <th>Status</th>
                    <th>EOL Date</th>
                    <th>Criticality</th>
                    <th>Last Checked</th>
                </tr>
            </thead>
            <tbody>
"""
        for result in results:
            status_class = f"status-{result['eol_status'].lower()}"
            criticality = result.get('criticality', 'medium')

            if criticality == 'high':
                criticality_badge = '<span class="badge badge-critical">CRITICAL</span>'
            elif criticality == 'medium':
                criticality_badge = '<span class="badge badge-warning">WARNING</span>'
            else:
                criticality_badge = '<span class="badge badge-info">INFO</span>'

            html_content += f"""
                <tr>
                    <td><strong>{result['tool_name']}</strong></td>
                    <td>{result['current_version']}</td>
                    <td class="latest-version">{result.get('latest_version', 'Unknown')}</td>
                    <td class="{status_class}">{result['eol_status']}</td>
                    <td>{result['eol_date']}</td>
                    <td>{criticality_badge}</td>
                    <td>{result['last_checked']}</td>
                </tr>
"""

        html_content += f"""
            </tbody>
        </table>

        <div class="footer">
            <p>Generated by EOL Tool Checker | {datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
    </div>
</body>
</html>"""

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_file
    except Exception:
        return None