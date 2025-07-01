"""
Skill normalization module for grouping and categorizing skills based on semantic similarity.
Supports file input/output operations with JSON format from job postings.
"""

import json
import logging
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from tqdm import tqdm

# Constants
MIN_GROUP_SIZE = 3
SIMILARITY_THRESHOLD = 0.8
DEFAULT_INPUT = "processed_parse_jobs.json"
DEFAULT_OUTPUT = "normalized_skills.json"

# Categories
MAIN_CATEGORIES = {
    '.NET': ['c#', 'dotnet', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entity framework'],
    'CLOUD_AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb'],
    'CLOUD_AZURE': ['azure', 'functions', 'entra', 'sql database'],
    'CLOUD_GCP': ['gcp', 'google cloud'],
    'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'mssql'],
    'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb'],
    'FRONTEND': ['react', 'angular', 'vue', 'javascript', 'typescript', 'html', 'css'],
    'BACKEND': ['node', 'python', 'java', 'spring', 'ruby', 'php'],
    'DEVOPS': ['docker', 'kubernetes', 'terraform', 'ci/cd', 'jenkins', 'git'],
    'TESTING': ['test', 'tdd', 'qa', 'junit', 'selenium'],
    'NETWORKING': ['tcp/ip', 'dns', 'dhcp', 'network', 'wccp'],
    'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance']
}

NON_TECH_CATEGORIES = {
    'BUSINESS': ['sales', 'negotiation', 'client', 'customer'],
    'OPERATIONS': ['warehouse', 'forklift', 'logistics'],
    'HEALTHCARE': ['patient', 'radiology', 'nursing', 'medical'],
    'EDUCATION': ['teaching', 'tutoring', 'curriculum']
}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_all_skill_names_from_jobs(file_path: str) -> List[str]:
    """Extracts all unique skill names from various sections in job postings."""
    with open(file_path, 'r') as f:
        data = json.load(f)

    skills = set()

    for job in data:
        for key in ['KeySkillsRequired', 'EssentialQualifications',
                    'EssentialTechnicalSkillQualifications', 'OtherTechnicalSkillQualifications']:
            for skill in job.get(key, []):
                name = skill.get('Name')
                if name:
                    skills.add(name.strip())
    return list(skills)


def save_results(output_file: str, results: Dict[str, List[str]]) -> None:
    """Save normalized skills to JSON output file."""
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    except IOError as e:
        logger.error(f"Failed to write output file: {e}")
        sys.exit(1)


def normalize_skill(skill_name: str) -> str:
    """Normalizes skill name by standardizing format and removing noise."""
    skill = skill_name.lower().strip()
    skill = re.sub(r"[^a-z0-9]", "", skill)
    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    return skill


def is_technical(skill: str) -> bool:
    """Determines if a skill is technical based on category keywords."""
    norm_skill = normalize_skill(skill)
    tech_keywords = {kw for cat in MAIN_CATEGORIES.values() for kw in cat}
    return any(kw in norm_skill for kw in tech_keywords)


def should_group_together(a: str, b: str) -> bool:
    """Checks if two skills should be grouped based on similarity."""
    norm_a, norm_b = normalize_skill(a), normalize_skill(b)
    if norm_a in norm_b or norm_b in norm_a:
        return True
    if norm_a[:4] == norm_b[:4]:
        return True
    return SequenceMatcher(None, norm_a, norm_b).ratio() >= SIMILARITY_THRESHOLD


def determine_primary_category(skill_name: str) -> str:
    """Assigns the most relevant category for a given skill."""
    norm_skill = normalize_skill(skill_name)
    for category, keywords in NON_TECH_CATEGORIES.items():
        if any(kw in norm_skill for kw in keywords):
            return f"NON_TECH_{category.upper()}"
    for category, keywords in MAIN_CATEGORIES.items():
        if any(kw in norm_skill for kw in keywords):
            return category.upper()
    return "OTHER_TECH" if is_technical(skill_name) else "OTHER_NON_TECH"


def create_initial_groups(skills: List[str]) -> Dict[str, List[str]]:
    """Creates initial skill groups based on semantic similarity."""
    groups: Dict[str, List[str]] = {}
    skills_sorted = sorted(skills, key=len, reverse=True)

    for skill in tqdm(skills_sorted, desc="Grouping skills"):
        matched = False
        for group_name in groups:
            if should_group_together(skill, group_name):
                groups[group_name].append(skill)
                matched = True
                break
        if not matched:
            groups[skill] = [skill]
    return groups


def consolidate_groups(groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Merges small groups and selects representative skill names."""
    consolidated: Dict[str, List[str]] = {}

    for group_name, skills in groups.items():
        category = determine_primary_category(group_name)
        if len(skills) < MIN_GROUP_SIZE:
            if category not in consolidated:
                consolidated[category] = []
            consolidated[category].extend(skills)
        else:
            consolidated[group_name] = skills

    # Deduplicate and sort
    return {
        k: sorted(list(set(v)))
        for k, v in consolidated.items()
    }


def normalize_skills(input_file: str, output_file: str) -> None:
    """Main function to process skills from input file and save results."""
    logger.info(f"Extracting skills from {input_file}")
    skills = extract_all_skill_names_from_jobs(input_file)

    logger.info("Creating initial groups")
    groups = create_initial_groups(skills)

    logger.info("Consolidating groups")
    final_groups = consolidate_groups(groups)

    save_results(output_file, final_groups)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Skill Normalization Tool")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help=f"Input JSON file (default: {DEFAULT_INPUT})")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help=f"Output JSON file (default: {DEFAULT_OUTPUT})")

    args = parser.parse_args()

    normalize_skills(args.input, args.output)
