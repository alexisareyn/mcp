# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utility functions for AWS Documentation MCP Server."""

import markdownify
from awslabs.aws_documentation_mcp_server.models import RecommendationResult
from typing import Any, Dict, List


def estimate_tokens(text: str) -> int:
    """Estimate token count based on character count.

    Uses the approximation that 3-4 characters equals 1 token.
    We'll use 3.5 characters per token as the conversion factor.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    return int(len(text) / 3.5)


def extract_content_from_html(html: str) -> str:
    """Extract and convert HTML content to Markdown format.

    Args:
        html: Raw HTML content to process

    Returns:
        Simplified markdown version of the content
    """
    if not html:
        return '<e>Empty HTML content</e>'

    try:
        # First use BeautifulSoup to clean up the HTML
        from bs4 import BeautifulSoup

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Try to find the main content area
        main_content = None

        # Common content container selectors for AWS documentation
        content_selectors = [
            'main',
            'article',
            '#main-content',
            '.main-content',
            '#content',
            '.content',
            "div[role='main']",
            '#awsdocs-content',
            '.awsui-article',
        ]

        # Try to find the main content using common selectors
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                main_content = content
                break

        # If no main content found, use the body
        if not main_content:
            main_content = soup.body if soup.body else soup

        # Remove navigation elements that might be in the main content
        nav_selectors = [
            'noscript',
            '.prev-next',
            '#main-col-footer',
            '.awsdocs-page-utilities',
            '#quick-feedback-yes',
            '#quick-feedback-no',
            '.page-loading-indicator',
            '#tools-panel',
            '.doc-cookie-banner',
            'awsdocs-copyright',
            'awsdocs-thumb-feedback',
        ]

        for selector in nav_selectors:
            for element in main_content.select(selector):
                element.decompose()

        # Define tags to strip - these are elements we don't want in the output
        tags_to_strip = [
            'script',
            'style',
            'noscript',
            'meta',
            'link',
            'footer',
            'nav',
            'aside',
            'header',
            # AWS documentation specific elements
            'awsdocs-cookie-consent-container',
            'awsdocs-feedback-container',
            'awsdocs-page-header',
            'awsdocs-page-header-container',
            'awsdocs-filter-selector',
            'awsdocs-breadcrumb-container',
            'awsdocs-page-footer',
            'awsdocs-page-footer-container',
            'awsdocs-footer',
            'awsdocs-cookie-banner',
            # Common unnecessary elements
            'js-show-more-buttons',
            'js-show-more-text',
            'feedback-container',
            'feedback-section',
            'doc-feedback-container',
            'doc-feedback-section',
            'warning-container',
            'warning-section',
            'cookie-banner',
            'cookie-notice',
            'copyright-section',
            'legal-section',
            'terms-section',
        ]

        # Use markdownify on the cleaned HTML content
        content = markdownify.markdownify(
            str(main_content),
            heading_style=markdownify.ATX,
            autolinks=True,
            default_title=True,
            escape_asterisks=True,
            escape_underscores=True,
            newline_style='SPACES',
            strip=tags_to_strip,
        )

        if not content:
            return '<e>Page failed to be simplified from HTML</e>'

        return content
    except Exception as e:
        return f'<e>Error converting HTML to Markdown: {str(e)}</e>'


def is_html_content(page_raw: str, content_type: str) -> bool:
    """Determine if content is HTML.

    Args:
        page_raw: Raw page content
        content_type: Content-Type header

    Returns:
        True if content is HTML, False otherwise
    """
    return '<html' in page_raw[:100] or 'text/html' in content_type or not content_type


def format_documentation_result(url: str, content: str, start_index: int, max_length: int) -> str:
    """Format documentation result with pagination information.

    Args:
        url: Documentation URL
        content: Content to format
        start_index: Start index for pagination
        max_length: Maximum content length

    Returns:
        Formatted documentation result
    """
    original_length = len(content)

    if start_index >= original_length:
        return f'AWS Documentation from {url}:\n\n<e>No more content available.</e>'

    # Calculate the end index, ensuring we don't go beyond the content length
    end_index = min(start_index + max_length, original_length)
    truncated_content = content[start_index:end_index]

    if not truncated_content:
        return f'AWS Documentation from {url}:\n\n<e>No more content available.</e>'

    actual_content_length = len(truncated_content)
    remaining_content = original_length - (start_index + actual_content_length)

    result = f'AWS Documentation from {url}:\n\n{truncated_content}'

    # Only add the prompt to continue fetching if there is still remaining content
    if remaining_content > 0:
        next_start = start_index + actual_content_length
        result += f'\n\n<e>Content truncated. Call the read_documentation tool with start_index={next_start} to get more content.</e>'

    return result


def extract_sections_from_markdown(markdown_content: str, section_titles: List[str]) -> str:
    """Extract specific sections from markdown content based on section titles.

    Args:
        markdown_content: Full markdown content to extract sections from
        section_titles: List of section titles to extract

    Returns:
        Filtered markdown content containing only the requested sections
    """
    if not markdown_content or not section_titles:
        return '<e>No content or section titles provided</e>'

    try:
        lines = markdown_content.split('\n')
        result_lines = []
        found_sections = []
        missing_sections = []
        current_section_level = 0
        capturing = False

        normalized_titles = {title.strip().lower(): title.strip() for title in section_titles}

        for line in lines:
            if line.strip().startswith('#'):
                heading_match = line.strip()
                heading_level = len(heading_match) - len(heading_match.lstrip('#'))
                heading_text = heading_match.lstrip('#').strip()

                if heading_text.lower() in normalized_titles:
                    current_section_level = heading_level
                    capturing = True
                    result_lines.append(line)

                    original_title = normalized_titles[heading_text.lower()]
                    if original_title not in found_sections:
                        found_sections.append(original_title)

                elif capturing and heading_level <= current_section_level:
                    capturing = False
                elif capturing:
                    result_lines.append(line)
            elif capturing:
                result_lines.append(line)

        for title in section_titles:
            if title.strip() not in found_sections:
                missing_sections.append(title.strip())

        if not found_sections:
            section_list = ', '.join(f'"{title}"' for title in section_titles)
            return f'**Alert**: No matching sections were found: {section_list}. Please use the read_documentation tool instead to get the full document content.'

        result_content = '\n'.join(result_lines)

        if missing_sections:
            missing_list = ', '.join(f'"{title}"' for title in missing_sections)
            result_content += (
                f'\n\n> **Note**: The following requested sections were not found: {missing_list}'
            )

        return result_content

    except Exception as e:
        return f'<e>Error extracting sections: {str(e)}</e>'


def parse_recommendation_results(data: Dict[str, Any]) -> List[RecommendationResult]:
    """Parse recommendation API response into RecommendationResult objects.

    Args:
        data: Raw API response data

    Returns:
        List of recommendation results
    """
    results = []

    # Process highly rated recommendations
    if 'highlyRated' in data and 'items' in data['highlyRated']:
        for item in data['highlyRated']['items']:
            context = item.get('abstract') if 'abstract' in item else None

            results.append(
                RecommendationResult(
                    url=item.get('url', ''), title=item.get('assetTitle', ''), context=context
                )
            )

    # Process journey recommendations (organized by intent)
    if 'journey' in data and 'items' in data['journey']:
        for intent_group in data['journey']['items']:
            intent = intent_group.get('intent', '')
            if 'urls' in intent_group:
                for url_item in intent_group['urls']:
                    # Add intent as part of the context
                    context = f'Intent: {intent}' if intent else None

                    results.append(
                        RecommendationResult(
                            url=url_item.get('url', ''),
                            title=url_item.get('assetTitle', ''),
                            context=context,
                        )
                    )

    # Process new content recommendations
    if 'new' in data and 'items' in data['new']:
        for item in data['new']['items']:
            # Add "New content" label to context
            date_created = item.get('dateCreated', '')
            context = f'New content added on {date_created}' if date_created else 'New content'

            results.append(
                RecommendationResult(
                    url=item.get('url', ''), title=item.get('assetTitle', ''), context=context
                )
            )

    # Process similar recommendations
    if 'similar' in data and 'items' in data['similar']:
        for item in data['similar']['items']:
            context = item.get('abstract') if 'abstract' in item else 'Similar content'

            results.append(
                RecommendationResult(
                    url=item.get('url', ''), title=item.get('assetTitle', ''), context=context
                )
            )

    return results
