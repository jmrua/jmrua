#!/usr/bin/env python3
"""
Update ORCID publications in README.md

This script fetches publications from ORCID API, filters them,
and updates the README.md file with formatted publication list.
"""

import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests


# ORCID configuration
ORCID_ID = "0000-0001-5115-8578"
ORCID_API_URL = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"

# README markers
PUBLICATIONS_START_MARKER = "<!-- ORCID-PUBLICATIONS:START -->"
PUBLICATIONS_END_MARKER = "<!-- ORCID-PUBLICATIONS:END -->"
SOFTWARE_START_MARKER = "<!-- ORCID-SOFTWARE:START -->"
SOFTWARE_END_MARKER = "<!-- ORCID-SOFTWARE:END -->"

# Work type categories
PUBLICATION_TYPES = {"journal-article", "conference-paper"}
SOFTWARE_TYPES = {"software", "research-tool"}
ACCEPTED_TYPES = PUBLICATION_TYPES | SOFTWARE_TYPES


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


def extract_publication_info(work: Dict) -> Optional[Dict[str, Any]]:
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


def format_publication(pub: Dict[str, Any]) -> str:
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


def filter_duplicate_publications(publications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter duplicate publications with the same title, keeping the most recent one.
    
    Args:
        publications: List of publication dictionaries
        
    Returns:
        List of publications with duplicates removed
    """
    # Use a dictionary to track publications by title
    # Keep the one with the most recent year
    unique_pubs = {}
    
    for pub in publications:
        title = pub.get("title")
        if not title:
            # Skip publications without a title
            continue
        
        if title not in unique_pubs:
            unique_pubs[title] = pub
        else:
            # Compare years - keep the most recent
            # Treat None as negative infinity (older than any year)
            existing_year = unique_pubs[title].get("year")
            current_year = pub.get("year")
            
            # If current has a year and existing doesn't, replace
            if current_year is not None and existing_year is None:
                unique_pubs[title] = pub
            # If both have years and current is more recent, replace
            elif current_year is not None and existing_year is not None and current_year > existing_year:
                unique_pubs[title] = pub
            # If neither has a year or existing is more recent, keep existing
    
    return list(unique_pubs.values())


def generate_publications_markdown(works_data: Dict) -> Tuple[str, str]:
    """
    Generate markdown content for publications and software sections.
    
    Args:
        works_data: Dictionary containing ORCID works data
        
    Returns:
        Tuple of (publications_markdown, software_markdown)
    """
    all_works = []
    
    # Extract all works
    work_groups = works_data.get("group", [])
    for group in work_groups:
        work_summaries = group.get("work-summary", [])
        for work in work_summaries:
            pub_info = extract_publication_info(work)
            if pub_info:
                all_works.append(pub_info)
    
    # Filter duplicates from all works
    all_works = filter_duplicate_publications(all_works)
    
    # Separate publications and software
    publications = [w for w in all_works if w.get("type") in PUBLICATION_TYPES]
    software = [w for w in all_works if w.get("type") in SOFTWARE_TYPES]
    
    # Sort by year (descending), handling None values
    publications.sort(key=lambda x: x.get("year") or 0, reverse=True)
    software.sort(key=lambda x: x.get("year") or 0, reverse=True)
    
    # Generate publications markdown
    pub_lines = ["📚 Publications", ""]
    if publications:
        for pub in publications:
            pub_lines.append(format_publication(pub))
    else:
        pub_lines.append("*No publications found*")
    
    # Generate software markdown
    soft_lines = ["💻 Software & Tools", ""]
    if software:
        for soft in software:
            soft_lines.append(format_publication(soft))
    else:
        soft_lines.append("*No software found*")
    
    return "\n".join(pub_lines), "\n".join(soft_lines)


def update_readme(publications_content: str, software_content: str, readme_path: str = "README.md") -> bool:
    """
    Update README.md with new publications and software content.
    
    Args:
        publications_content: New markdown content for publications section
        software_content: New markdown content for software section
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
    has_publications_markers = (PUBLICATIONS_START_MARKER in content and 
                                 PUBLICATIONS_END_MARKER in content)
    has_software_markers = (SOFTWARE_START_MARKER in content and 
                           SOFTWARE_END_MARKER in content)
    
    if not has_publications_markers or not has_software_markers:
        print(f"Error: Required markers not found in README", file=sys.stderr)
        print(f"  Publications markers: {has_publications_markers}", file=sys.stderr)
        print(f"  Software markers: {has_software_markers}", file=sys.stderr)
        return False
    
    # Replace publications section
    pub_section = f"{PUBLICATIONS_START_MARKER}\n{publications_content}\n{PUBLICATIONS_END_MARKER}"
    pub_pattern = re.compile(
        f"{re.escape(PUBLICATIONS_START_MARKER)}.*?{re.escape(PUBLICATIONS_END_MARKER)}",
        re.DOTALL
    )
    content = pub_pattern.sub(pub_section, content)
    
    # Replace software section
    soft_section = f"{SOFTWARE_START_MARKER}\n{software_content}\n{SOFTWARE_END_MARKER}"
    soft_pattern = re.compile(
        f"{re.escape(SOFTWARE_START_MARKER)}.*?{re.escape(SOFTWARE_END_MARKER)}",
        re.DOTALL
    )
    new_readme = soft_pattern.sub(soft_section, content)
    
    # Read original content again to check if anything changed
    with open(readme_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    
    # Check if content changed
    if new_readme == original_content:
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
        publications_content, software_content = generate_publications_markdown(works_data)
        
        print("Updating README...")
        updated = update_readme(publications_content, software_content)
        
        if updated:
            print("✅ README updated with latest publications and software")
            sys.exit(0)
        else:
            print("ℹ️ No changes needed")
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
