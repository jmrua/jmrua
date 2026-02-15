#!/usr/bin/env python3
"""
Update ORCID publications in README.md

This script fetches publications from ORCID API, filters them,
and updates the README.md file with formatted publication list.
"""

import re
import sys
from typing import List, Dict, Optional

import requests


# ORCID configuration
ORCID_ID = "0000-0001-5115-8578"
ORCID_API_URL = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"

# README markers
START_MARKER = "<!-- ORCID:START -->"
END_MARKER = "<!-- ORCID:END -->"

# Accepted work types
ACCEPTED_TYPES = {"journal-article", "conference-paper"}


def fetch_orcid_works() -> Dict:
    """
    Fetch works from ORCID API.
    
    Returns:
        Dict containing the API response
        
    Raises:
        requests.exceptions.RequestException: If API request fails
    """
    headers = {
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(ORCID_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ORCID data: {e}", file=sys.stderr)
        raise


def extract_publication_info(work: Dict) -> Optional[Dict[str, any]]:
    """
    Extract relevant information from a work item.
    
    Args:
        work: Dictionary containing work data from ORCID API
        
    Returns:
        Dictionary with extracted info or None if required fields are missing
    """
    try:
        # Get work type
        work_type = work.get("type")
        if not work_type or work_type.lower() not in ACCEPTED_TYPES:
            return None
        
        # Get title
        title_obj = work.get("title")
        if not title_obj or not title_obj.get("title"):
            return None
        title = title_obj["title"].get("value", "").strip()
        if not title:
            return None
        
        # Get publication year
        pub_date = work.get("publication-date")
        year = None
        if pub_date and pub_date.get("year"):
            year_value = pub_date["year"].get("value")
            if year_value:
                try:
                    year = int(year_value)
                except (ValueError, TypeError):
                    pass
        
        # Get DOI
        doi = None
        external_ids = work.get("external-ids", {}).get("external-id", [])
        for ext_id in external_ids:
            if ext_id.get("external-id-type") == "doi":
                doi = ext_id.get("external-id-value")
                if doi:
                    break
        
        return {
            "title": title,
            "year": year,
            "doi": doi,
            "type": work_type
        }
    except (KeyError, TypeError, AttributeError) as e:
        print(f"Warning: Error extracting publication info: {e}", file=sys.stderr)
        return None


def format_publication(pub: Dict[str, any]) -> str:
    """
    Format a publication as a Markdown list item.
    
    Args:
        pub: Dictionary with publication information
        
    Returns:
        Formatted markdown string
    """
    year = pub.get("year", "N/A")
    title = pub["title"]
    doi = pub.get("doi")
    
    if doi:
        # Create DOI link
        return f"- **{year}** – [{title}](https://doi.org/{doi})"
    else:
        # No DOI available
        return f"- **{year}** – {title}"


def generate_publications_markdown(works_data: Dict) -> str:
    """
    Generate markdown content for publications section.
    
    Args:
        works_data: Dictionary containing ORCID works data
        
    Returns:
        Formatted markdown string
    """
    publications = []
    
    # Extract and filter publications
    work_groups = works_data.get("group", [])
    for group in work_groups:
        work_summaries = group.get("work-summary", [])
        for work in work_summaries:
            pub_info = extract_publication_info(work)
            if pub_info:
                publications.append(pub_info)
    
    # Sort by year (descending), handling None values
    publications.sort(key=lambda x: x.get("year") or 0, reverse=True)
    
    # Generate markdown
    markdown_lines = ["📚 Publications (from ORCID)", ""]
    
    if publications:
        for pub in publications:
            markdown_lines.append(format_publication(pub))
    else:
        markdown_lines.append("*No publications found*")
    
    return "\n".join(markdown_lines)


def update_readme(new_content: str, readme_path: str = "README.md") -> bool:
    """
    Update README.md with new publications content.
    
    Args:
        new_content: New markdown content to insert
        readme_path: Path to README file
        
    Returns:
        True if file was modified, False otherwise
    """
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: {readme_path} not found", file=sys.stderr)
        return False
    
    # Check if markers exist
    if START_MARKER not in content or END_MARKER not in content:
        print(f"Error: Markers {START_MARKER} and {END_MARKER} not found in README",
              file=sys.stderr)
        return False
    
    # Create new content between markers
    new_section = f"{START_MARKER}\n{new_content}\n{END_MARKER}"
    
    # Replace content between markers
    pattern = re.compile(
        f"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        re.DOTALL
    )
    new_readme = pattern.sub(new_section, content)
    
    # Check if content changed
    if new_readme == content:
        print("No changes to README")
        return False
    
    # Write updated content
    try:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_readme)
        print("README updated successfully")
        return True
    except IOError as e:
        print(f"Error writing to {readme_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main execution function."""
    try:
        print("Fetching ORCID publications...")
        works_data = fetch_orcid_works()
        
        print("Generating markdown content...")
        markdown_content = generate_publications_markdown(works_data)
        
        print("Updating README...")
        updated = update_readme(markdown_content)
        
        if updated:
            print("✅ README updated with latest publications")
            sys.exit(0)
        else:
            print("ℹ️ No changes needed")
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
