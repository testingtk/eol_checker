import requests
from datetime import datetime
import logging
import re
import os
import json
from pathlib import Path
from packaging import version

logger = logging.getLogger(__name__)


class EOLChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_eol_data(self, tool_name, current_version):
        """Fetch EOL data from endoflife.date API only"""
        try:
            # Convert tool name to API format
            api_tool_name = tool_name.lower().replace(' ', '').replace('.', '')
            api_url = f"https://endoflife.date/api/{api_tool_name}.json"

            response = self.session.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self._parse_endoflife_data(data, current_version, tool_name)
            else:
                logger.warning(f"API not found for {tool_name}: {api_url}")
                return {'status': 'Unknown', 'eol_date': 'API not available', 'latest_version': 'Unknown'}

        except Exception as e:
            logger.warning(f"Failed to fetch from endoflife.date for {tool_name}: {e}")
            return {'status': 'Unknown', 'eol_date': 'Check failed', 'latest_version': 'Unknown'}

    def _normalize_version(self, version_str):
        """Normalize version string for comparison"""
        if not version_str or version_str == 'Unknown':
            return version_str

        try:
            # Remove any non-digit, non-dot, non-alphabet characters
            version_str = re.sub(r'[^\w.]', '', str(version_str))
            return version.parse(version_str)
        except:
            # Fallback: clean up the version string
            version_str = re.sub(r'[^\d.]', '', str(version_str))
            while version_str.endswith('.0'):
                version_str = version_str[:-2]
            return version_str

    def _compare_versions(self, v1, v2):
        """Compare two version strings"""
        if v1 == 'Unknown' or v2 == 'Unknown':
            return 0  # Can't compare unknown versions

        try:
            v1_parsed = version.parse(str(v1))
            v2_parsed = version.parse(str(v2))

            if v1_parsed == v2_parsed:
                return 0
            elif v1_parsed > v2_parsed:
                return 1
            else:
                return -1
        except:
            # Fallback string comparison
            v1_str = str(v1).lower()
            v2_str = str(v2).lower()

            if v1_str == v2_str:
                return 0
            try:
                # Try numeric comparison for simple versions
                v1_clean = re.sub(r'[^\d.]', '', v1_str)
                v2_clean = re.sub(r'[^\d.]', '', v2_str)

                v1_num = float(v1_clean) if '.' not in v1_clean else float(v1_clean.replace('.', '', 1))
                v2_num = float(v2_clean) if '.' not in v2_clean else float(v2_clean.replace('.', '', 1))

                if v1_num == v2_num:
                    return 0
                elif v1_num > v2_num:
                    return 1
                else:
                    return -1
            except:
                return 0  # Can't compare, assume equal

    def _parse_endoflife_data(self, data, current_version, tool_name):
        """Parse data from endoflife.date API"""
        # Check if data is empty or not a list
        if not data or not isinstance(data, list):
            return {
                'status': 'Unknown',
                'eol_date': 'No data available',
                'latest_version': 'Unknown'
            }

        # Find latest version
        latest_version = "Unknown"
        latest_release_date = None

        for release in data:
            if release.get('latest'):
                latest_version = release.get('cycle', 'Unknown')
                break

        # If no explicit latest flag, find the most recent release by date
        if latest_version == "Unknown":
            for release in data:
                release_date_str = release.get('releaseDate')
                if release_date_str:
                    try:
                        release_date = datetime.strptime(release_date_str, '%Y-%m-%d')
                        if latest_release_date is None or release_date > latest_release_date:
                            latest_release_date = release_date
                            latest_version = release.get('cycle', 'Unknown')
                    except:
                        continue

        # Check if current version is greater than latest version
        if latest_version != "Unknown" and current_version != "Unknown":
            comparison = self._compare_versions(current_version, latest_version)
            if comparison == 1:  # current > latest
                return {
                    'status': 'Unknown',
                    'eol_date': 'Version not found (current > latest)',
                    'latest_version': latest_version
                }

        # If current version equals latest version, it's definitely supported
        if latest_version != "Unknown" and current_version != "Unknown":
            comparison = self._compare_versions(current_version, latest_version)
            if comparison == 0:  # current == latest
                # Find this version in the data to get EOL info
                for release in data:
                    release_cycle = str(release.get('cycle', ''))
                    if self._compare_versions(release_cycle, current_version) == 0:
                        eol_date = release.get('eol')
                        if eol_date:
                            if eol_date in [True, 'true', 'True']:
                                return {
                                    'status': 'EOL',
                                    'eol_date': 'Already EOL',
                                    'latest_version': latest_version
                                }
                            else:
                                try:
                                    eol_dt = datetime.strptime(eol_date, '%Y-%m-%d')
                                    today = datetime.now()
                                    if eol_dt < today:
                                        return {
                                            'status': 'EOL',
                                            'eol_date': eol_date,
                                            'latest_version': latest_version
                                        }
                                    else:
                                        days_until = (eol_dt - today).days
                                        return {
                                            'status': 'Supported',
                                            'eol_date': eol_date,
                                            'days_until_eol': days_until,
                                            'latest_version': latest_version
                                        }
                                except:
                                    return {
                                        'status': 'Supported',
                                        'eol_date': eol_date,
                                        'latest_version': latest_version
                                    }
                        else:
                            # No EOL date specified for current=latest version
                            return {
                                'status': 'Supported',
                                'eol_date': 'Not specified (latest version)',
                                'latest_version': latest_version
                            }

        # Search for the specific version in the data
        for release in data:
            release_cycle = str(release.get('cycle', ''))

            # Try exact match first
            if self._compare_versions(release_cycle, current_version) == 0:
                eol_date = release.get('eol')
                if eol_date:
                    if eol_date in [True, 'true', 'True']:
                        return {
                            'status': 'EOL',
                            'eol_date': 'Already EOL',
                            'latest_version': latest_version
                        }
                    else:
                        try:
                            eol_dt = datetime.strptime(eol_date, '%Y-%m-%d')
                            today = datetime.now()
                            if eol_dt < today:
                                return {
                                    'status': 'EOL',
                                    'eol_date': eol_date,
                                    'latest_version': latest_version
                                }
                            else:
                                days_until = (eol_dt - today).days
                                return {
                                    'status': 'Supported',
                                    'eol_date': eol_date,
                                    'days_until_eol': days_until,
                                    'latest_version': latest_version
                                }
                        except:
                            return {
                                'status': 'Unknown',
                                'eol_date': eol_date,
                                'latest_version': latest_version
                            }
                else:
                    # Version found but no EOL date specified
                    return {
                        'status': 'Supported',
                        'eol_date': 'Not specified',
                        'latest_version': latest_version
                    }

        # Version not found in the data
        return {
            'status': 'Unknown',
            'eol_date': 'Version not found',
            'latest_version': latest_version
        }

    def _calculate_criticality(self, eol_status, eol_date, days_until_eol, latest_version, current_version):
        """Calculate criticality based on EOL status and dates"""
        if eol_status == 'EOL':
            return 'high'
        elif eol_status == 'Supported':
            # If it's the latest version with no EOL date, it's low priority
            if (eol_date == 'Not specified (latest version)' or
                eol_date == 'Not specified') and latest_version != 'Unknown':
                if self._compare_versions(current_version, latest_version) == 0:
                    return 'low'

            if days_until_eol != 'N/A' and isinstance(days_until_eol, int):
                if days_until_eol <= 0:  # Already past but marked as supported
                    return 'high'
                elif days_until_eol <= 30:  # Within 30 days
                    return 'high'
                elif days_until_eol <= 90:  # Within 3 months
                    return 'medium'
                else:
                    return 'low'
            else:
                # No EOL date information, default to medium
                return 'medium'
        else:
            return 'medium'  # Unknown status

    def check_multiple_tools(self, tools_data):
        """Check EOL status for multiple tools"""
        results = []

        for i, tool in enumerate(tools_data):
            logger.info(f"Checking EOL for {tool['name']} {tool['version']} ({i + 1}/{len(tools_data)})")

            eol_info = self.fetch_eol_data(tool['name'], tool['version'])

            # Calculate criticality with more context
            days_until = eol_info.get('days_until_eol', 'N/A')
            criticality = self._calculate_criticality(
                eol_info['status'],
                eol_info.get('eol_date', 'Unknown'),
                days_until if days_until != 'N/A' and isinstance(days_until, int) else 'N/A',
                eol_info.get('latest_version', 'Unknown'),
                tool['version']
            )

            result = {
                'tool_name': tool['name'],
                'current_version': tool['version'],
                'eol_status': eol_info['status'],
                'eol_date': eol_info.get('eol_date', 'Unknown'),
                'days_until_eol': eol_info.get('days_until_eol', 'N/A'),
                'latest_version': eol_info.get('latest_version', 'Unknown'),
                'criticality': criticality,
                'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Add additional fields from input if they exist
            for key, value in tool.items():
                if key not in result:
                    result[key] = value

            results.append(result)

        return results

    def generate_issue_content(self, results, repository=None, run_id=None):
        """Generate markdown content for GitHub issue"""
        critical_items = [r for r in results if r.get('criticality') == 'high']
        warning_items = [r for r in results if r.get('criticality') == 'medium']
        supported_items = [r for r in results if r.get('eol_status') == 'Supported' and r.get('criticality') == 'low']

        content = []

        if critical_items or warning_items:
            content.append('## 🚨 EOL Tools Detected\n\n')

            # Add report link if repository and run_id are provided
            if repository and run_id:
                content.append(f'[📊 Download Full HTML Report](https://github.com/{repository}/actions/runs/{run_id})\n\n')

            if critical_items:
                content.append('### 🔴 Critical Priority\n')
                content.append('These tools are either EOL or will reach EOL within 30 days:\n\n')
                for tool in critical_items:
                    if tool['eol_status'] == 'EOL':
                        status = '🔴 EOL'
                    else:
                        days = tool.get('days_until_eol', 'N/A')
                        status = f'⚠️ EOL in {days} days'
                    content.append(f'- **{tool["tool_name"]} {tool["current_version"]}** - {status} (EOL: {tool["eol_date"]}, Latest: {tool.get("latest_version", "Unknown")})\n')
                content.append('\n')

            if warning_items:
                content.append('### 🟡 Warning Priority\n')
                content.append('These tools have warnings or will reach EOL within 90 days:\n\n')
                for tool in warning_items:
                    if tool['eol_status'] == 'EOL':
                        status = '🔴 EOL'
                    elif tool['eol_status'] == 'Supported':
                        days = tool.get('days_until_eol', 'N/A')
                        if days != 'N/A':
                            status = f'🟡 EOL in {days} days'
                        else:
                            status = '🟡 Supported (no EOL date)'
                    else:
                        status = '🟡 Unknown status'
                    content.append(f'- **{tool["tool_name"]} {tool["current_version"]}** - {status} (EOL: {tool["eol_date"]}, Latest: {tool.get("latest_version", "Unknown")})\n')
                content.append('\n')

            content.append('### 📊 Summary\n')
            content.append(f'- Total tools checked: {len(results)}\n')
            content.append(f'- 🔴 Critical items: {len(critical_items)}\n')
            content.append(f'- 🟡 Warning items: {len(warning_items)}\n')
            content.append(f'- ✅ Supported items: {len(supported_items)}\n')

            content.append('\n### 💡 Recommendations\n')
            content.append('1. Prioritize updating critical items immediately\n')
            content.append('2. Plan updates for warning items in the near future\n')
            content.append('3. Review the full HTML report for complete details\n')

        return ''.join(content), critical_items, warning_items

    def check_and_generate_issue(self, tools_json_path='data/input/tools.json',
                               output_dir='data/output', repository=None, run_id=None):
        """Main method to check EOL status and generate issue content"""
        try:
            # Load tools from JSON
            with open(tools_json_path, 'r') as f:
                tools_data = json.load(f)

            # Check EOL status
            results = self.check_multiple_tools(tools_data)

            # Generate issue content
            issue_content, critical_items, warning_items = self.generate_issue_content(
                results, repository, run_id
            )

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Write issue content if needed
            if critical_items or warning_items:
                issue_file = os.path.join(output_dir, 'eol_issue.md')
                with open(issue_file, 'w') as f:
                    f.write(issue_content)

                # Create flag file for issue creation
                with open(os.path.join(output_dir, 'should_create_issue'), 'w') as f:
                    f.write('true')

                print(f"Generated issue with {len(critical_items)} critical and {len(warning_items)} warning items")
                return True, results
            else:
                # Create close issue message
                close_file = os.path.join(output_dir, 'close_issue.md')
                with open(close_file, 'w') as f:
                    f.write('✅ All tools are supported! No critical or warning EOL tools detected. Closing this issue.\n')
                    f.write(f'Total tools checked: {len(results)}\n')

                print("All tools supported, no issue needed")
                return False, results

        except Exception as e:
            print(f"Error in EOL check: {e}")
            raise


# Command line interface
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Check EOL status for tools')
    parser.add_argument('--tools-json', default='data/input/tools.json', help='Path to tools JSON file')
    parser.add_argument('--output-dir', default='data/output', help='Output directory')
    parser.add_argument('--repository', help='GitHub repository (for report link)')
    parser.add_argument('--run-id', help='GitHub Actions run ID (for report link)')

    args = parser.parse_args()

    checker = EOLChecker()
    checker.check_and_generate_issue(
        args.tools_json,
        args.output_dir,
        args.repository,
        args.run_id
    )