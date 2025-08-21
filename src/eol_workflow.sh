#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_existing_issues() {
    log_info "Checking for existing EOL issues..."

    # Check if there are any open issues with the EOL label
    existing_issues=$(gh issue list --label eol --state open --json number,title --jq 'length' 2>/dev/null || echo "0")
    echo "existing_issues=$existing_issues" >> $GITHUB_OUTPUT

    # Get all open EOL issue numbers
    gh issue list --label eol --state open --json number --jq '.[].number' > open_issue_numbers.txt 2>/dev/null || true
    log_info "Open EOL issues: $(cat open_issue_numbers.txt 2>/dev/null || echo 'None')"
}

compare_with_existing_issues() {
    log_info "Comparing with existing issues..."

    if [ ! -f "eol_issue.md" ] || [ ! -f "open_issue_numbers.txt" ]; then
        log_error "Required files not found for comparison"
        echo "duplicate_found=false" >> $GITHUB_OUTPUT
        return
    fi

    local current_issue_content=$(cat eol_issue.md)
    local current_hash=$(echo "$current_issue_content" | sha256sum | cut -d' ' -f1)
    log_info "Current issue hash: $current_hash"

    local duplicate_found=false
    local similar_issue_number=""

    # Read all open issue numbers
    while read -r issue_number; do
        if [ -n "$issue_number" ]; then
            log_info "Checking issue #$issue_number..."

            # Get issue content
            local issue_content=$(gh issue view "$issue_number" --json body --jq '.body' 2>/dev/null || echo "")
            local issue_hash=$(echo "$issue_content" | sha256sum | cut -d' ' -f1 2>/dev/null || echo "")

            log_info "Issue #$issue_number hash: $issue_hash"

            # Compare hashes
            if [ "$current_hash" = "$issue_hash" ]; then
                log_info "Duplicate found in issue #$issue_number"
                duplicate_found=true
                similar_issue_number=$issue_number
                break
            fi

            # Check if the issue has similar content (same critical/warning items)
            local current_critical_count=$(grep -c "Critical items:" eol_issue.md || true)
            local current_warning_count=$(grep -c "Warning items:" eol_issue.md || true)

            local issue_critical_count=$(echo "$issue_content" | grep -c "Critical items:" || true)
            local issue_warning_count=$(echo "$issue_content" | grep -c "Warning items:" || true)

            if [ "$current_critical_count" = "$issue_critical_count" ] && [ "$current_warning_count" = "$issue_warning_count" ]; then
                log_info "Similar issue found #$issue_number with same item counts"

                # Check if the actual tool lists are similar
                local current_tools=$(grep -oE "\*\*[^*]+\*\*" eol_issue.md | sort)
                local issue_tools=$(echo "$issue_content" | grep -oE "\*\*[^*]+\*\*" | sort)

                if [ "$current_tools" = "$issue_tools" ]; then
                    log_info "Exact same tools found in issue #$issue_number"
                    duplicate_found=true
                    similar_issue_number=$issue_number
                    break
                fi
            fi
        fi
    done < open_issue_numbers.txt

    echo "duplicate_found=$duplicate_found" >> $GITHUB_OUTPUT
    echo "similar_issue_number=$similar_issue_number" >> $GITHUB_OUTPUT

    if [ "$duplicate_found" = "true" ]; then
        log_info "Duplicate issue found, skipping creation"
        rm -f should_create_issue
    else
        log_info "No duplicates found, proceeding with issue creation"
    fi
}

update_existing_issue() {
    local issue_number=$1
    log_info "Updating existing issue #$issue_number with new check timestamp"

    gh issue comment "$issue_number" --body "✅ EOL status re-checked on $(date -u +'%Y-%m-%d %H:%M:%S UTC'). Status remains unchanged. [View latest run](https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID)"
}

close_existing_issues() {
    log_info "Closing existing EOL issues since everything is now supported"

    while read -r issue_number; do
        if [ -n "$issue_number" ]; then
            log_info "Closing issue #$issue_number"
            gh issue close "$issue_number" --comment "All tools are now supported! No critical or warning EOL tools detected. Closing this issue."
        fi
    done < open_issue_numbers.txt
}

main() {
    case "${1:-}" in
        "check-existing")
            check_existing_issues
            ;;
        "compare-issues")
            compare_with_existing_issues
            ;;
        "update-issue")
            update_existing_issue "$2"
            ;;
        "close-issues")
            close_existing_issues
            ;;
        *)
            log_error "Unknown command: $1"
            log_info "Available commands: check-existing, compare-issues, update-issue, close-issues"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"