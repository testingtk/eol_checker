#!/usr/bin/env python3
import argparse
import os
from datetime import datetime
from src.file_handlers import load_tools_from_json, save_results_html, save_results_json
from src.eol_checker import EOLChecker


def ensure_directory(dir_path):
    """Ensure directory exists"""
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description='EOL Tool Checker - endoflife.date API')
    parser.add_argument('--input', '-i', required=True, help='Input JSON file path')
    parser.add_argument('--output', '-o', help='Output file name (optional)')
    parser.add_argument('--output-dir', '-od', default='data/output/reports', help='Output directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output with EOL dates')

    args = parser.parse_args()

    # Ensure output directory exists
    ensure_directory(args.output_dir)
    ensure_directory('data/input')

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"❌ Input file {args.input} does not exist")
        return

    if not args.input.lower().endswith('.json'):
        print("❌ Only JSON files are supported")
        return

    # Load tools data
    tools_data = load_tools_from_json(args.input)

    if not tools_data:
        print("❌ No tools data loaded")
        return

    print(f"📋 Loaded {len(tools_data)} tools")

    # Initialize EOL checker
    checker = EOLChecker()

    # Check EOL status
    print("🔍 Checking EOL status via endoflife.date API...")
    results = checker.check_multiple_tools(tools_data)

    # Display results with enhanced format
    print("\n" + "=" * 100)

    if args.verbose:
        # Detailed view with EOL dates
        print(f"{'Status':<8} {'Tool':<18} {'Version':<10} {'Latest':<10} {'EOL Date':<12} {'Criticality':<10}")
        print("-" * 100)
        for result in results:
            if result['eol_status'] == 'EOL':
                status_icon = "🔴 EOL"
            elif result['eol_status'] == 'Supported':
                status_icon = "🟢 OK"
            else:
                status_icon = "🟡 ???"

            criticality = result.get('criticality', 'medium').upper()
            print(
                f"{status_icon:<8} {result['tool_name']:<18} {result['current_version']:<10} {result.get('latest_version', 'Unknown'):<10} {result['eol_date']:<12} {criticality:<10}")
    else:
        # Enhanced summary view
        for result in results:
            if result['eol_status'] == 'EOL':
                status_icon = "🔴"
                eol_info = f" (EOL: {result['eol_date']}, Latest: {result.get('latest_version', 'Unknown')})"
            elif result['eol_status'] == 'Supported':
                status_icon = "🟢"
                days_until = result.get('days_until_eol', 'N/A')
                if days_until != 'N/A' and isinstance(days_until, int):
                    if days_until <= 30:  # Critical
                        eol_info = f" (🚨 EOL in {days_until} days: {result['eol_date']}, Latest: {result.get('latest_version', 'Unknown')})"
                    elif days_until <= 90:  # Warning
                        eol_info = f" (⚠️ EOL in {days_until} days: {result['eol_date']}, Latest: {result.get('latest_version', 'Unknown')})"
                    else:
                        eol_info = f" (EOL: {result['eol_date']}, Latest: {result.get('latest_version', 'Unknown')})"
                else:
                    # Check if it's the latest version with no EOL date
                    if (result['eol_date'] == 'Not specified (latest version)' and
                        result.get('latest_version', 'Unknown') != 'Unknown'):
                        eol_info = f" (✅ Latest version: {result.get('latest_version', 'Unknown')})"
                    else:
                        eol_info = f" (Latest: {result.get('latest_version', 'Unknown')})"
            else:
                status_icon = "🟡"
                eol_info = f" ({result['eol_date']}, Latest: {result.get('latest_version', 'Unknown')})"

            print(
                f"{status_icon} {result['tool_name']:<15} {result['current_version']:<8} : {result['eol_status']:<10}{eol_info}")

    print("=" * 100)

    # Save HTML and JSON reports
    output_filename = args.output or f"eol_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    saved_html_file = save_results_html(results, output_filename, args.output_dir)
    saved_json_file = save_results_json(results, output_filename, args.output_dir)

    if saved_html_file:
        print(f"\n📁 HTML report saved to: {saved_html_file}")
    else:
        print("\n❌ Failed to save HTML report")

    if saved_json_file:
        print(f"📁 JSON report saved to: {saved_json_file}")
    else:
        print("❌ Failed to save JSON report")

    # Show critical items with details
    critical_items = [r for r in results if r.get('criticality') == 'high']
    if critical_items:
        print(f"\n🚨 CRITICAL ITEMS ({len(critical_items)}):")
        for tool in critical_items:
            if tool['eol_status'] == 'EOL':
                status = "EOL"
            else:
                days = tool.get('days_until_eol', 'N/A')
                status = f"EOL in {days} days" if days != 'N/A' else "Approaching EOL"
            print(f"   • {tool['tool_name']} {tool['current_version']} ({status}: {tool['eol_date']}, Latest: {tool.get('latest_version', 'Unknown')})")

    # Show warning items
    warning_items = [r for r in results if r.get('criticality') == 'medium']
    if warning_items:
        print(f"\n⚠️  WARNING ITEMS ({len(warning_items)}):")
        for tool in warning_items:
            if tool['eol_status'] == 'Supported':
                days = tool.get('days_until_eol', 'N/A')
                if days != 'N/A':
                    status = f"EOL in {days} days"
                elif tool['eol_date'] == 'Not specified (latest version)':
                    status = "Latest version"
                else:
                    status = "Supported (no EOL date)"
            else:
                status = tool['eol_status']
            print(f"   • {tool['tool_name']} {tool['current_version']} ({status}: {tool['eol_date']}, Latest: {tool.get('latest_version', 'Unknown')})")

    # Show low priority items
    low_items = [r for r in results if r.get('criticality') == 'low']
    if low_items:
        print(f"\n✅  Info ({len(low_items)}):")
        for tool in low_items:
            if tool['eol_status'] == 'Supported' and tool['eol_date'] == 'Not specified (latest version)':
                status = "Latest version"
            else:
                days = tool.get('days_until_eol', 'N/A')
                status = f"EOL in {days} days" if days != 'N/A' else "Supported"
            print(f"   • {tool['tool_name']} {tool['current_version']} ({status}: {tool['eol_date']}, Latest: {tool.get('latest_version', 'Unknown')})")

    # Enhanced summary
    eol_count = sum(1 for r in results if r['eol_status'] == 'EOL')
    supported_count = sum(1 for r in results if r['eol_status'] == 'Supported')
    unknown_count = sum(1 for r in results if r['eol_status'] == 'Unknown')

    critical_count = len(critical_items)
    warning_count = len(warning_items)
    low_count = len(low_items)

    print(f"\n📈 Summary:")
    print(f"   • Total Tools: {len(results)}")
    print(f"   • 🔴 EOL (End-of-Life): {eol_count}")
    print(f"   • 🟢 Supported: {supported_count}")
    if unknown_count > 0:
        print(f"   • 🟡 Unknown: {unknown_count}")
    print(f"   • 🚨 Critical: {critical_count}")
    print(f"   • ⚠️ Warnings: {warning_count}")
    if low_count > 0:
        print(f"   • ✅  info: {low_count}")

    print(f"\n💡 Tips:")
    print(f"   • Use --verbose (-v) for detailed table view with all EOL dates")
    print(f"   • Open the HTML report in your browser for complete details")
    if critical_count > 0:
        print(f"   • Prioritize updating critical items (EOL or EOL within 30 days)")


if __name__ == "__main__":
    main()