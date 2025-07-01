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
DEFAULT_SUMMARY = "output_categories.txt"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Main Categories
MAIN_CATEGORIES = {
    '.NET': ['dotnet', 'csharp', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entityframework'],
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

# Aliases for normalization
CATEGORY_ALIASES = {
    "aspnetmvc": "dotnet",
    "aspnetcore": "dotnet",
    "dotnetcore": "dotnet",
    "netcore": "dotnet",
    "net": "dotnet",
    "entityframework": "dotnet",
    "c#": "dotnet",
    "csharp": "dotnet",
    "ts": "typescript",
    "js": "javascript",
    "py": "python"
}


def extract_all_skill_names_from_jobs(file_path: str) -> List[str]:
    """Extracts all unique skill names from job postings."""
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


def normalize_skill(skill_name: str) -> str:
    """Normalizes skill name by standardizing format and removing noise."""
    skill = skill_name.lower().strip()

    # Filtrar frases que no son habilidades
    if any(kw in skill for kw in ["years of experience", "ability to", "demonstrated experience", "track record", "responsible for"]):
        return ""

    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    skill = re.sub(r"[^a-z0-9]+", "", skill)  # quitar caracteres no alfanuméricos

    # Aplicar alias si existe
    if skill in CATEGORY_ALIASES:
        skill = CATEGORY_ALIASES[skill]

    return skill


def is_valid_group_name(name: str) -> bool:
    """Returns False if name is a long sentence or irrelevant."""
    return len(name.split()) <= 5 and len(name.strip()) >= 3


def is_technical(skill: str) -> bool:
    """Determines if a skill is technical based on category keywords."""
    norm_skill = normalize_skill(skill)
    tech_keywords = {kw for cat in MAIN_CATEGORIES.values() for kw in cat}
    return any(kw in norm_skill for kw in tech_keywords)


def should_group_together(a: str, b: str) -> bool:
    """Checks if two skills should be grouped based on similarity."""
    norm_a, norm_b = normalize_skill(a), normalize_skill(b)
    if not norm_a or not norm_b:
        return False
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
        if not is_valid_group_name(skill):
            continue

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

    return {
        k: sorted(list(set(v)))
        for k, v in consolidated.items()
    }


def save_results(output_file: str, results: Dict[str, List[str]]) -> None:
    """Save normalized skills to JSON output file."""
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    except IOError as e:
        logger.error(f"Failed to write output file: {e}")
        sys.exit(1)


def save_categories_summary(final_groups: Dict[str, List[str]], output_path: str) -> None:
    """Save a human-readable summary of categories and their skills."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for category, skills in sorted(final_groups.items()):
                f.write(f"[{category}] - {len(skills)} skills\n")
                for skill in sorted(skills):
                    f.write(f"  - {skill}\n")
                f.write("\n")
        logger.info(f"Category summary saved to {output_path}")
    except IOError as e:
        logger.error(f"Failed to write category summary file: {e}")


def normalize_skills(input_file: str, output_file: str, summary_file: str) -> None:
    """Main function to process skills from input file and save results."""
    logger.info(f"Extracting skills from {input_file}")
    skills = extract_all_skill_names_from_jobs(input_file)

    logger.info("Creating initial groups")
    groups = create_initial_groups(skills)

    logger.info("Consolidating groups")
    final_groups = consolidate_groups(groups)

    save_results(output_file, final_groups)
    save_categories_summary(final_groups, summary_file)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Skill Normalization Tool")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT, help="Input JSON file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="Output grouped JSON file")
    parser.add_argument("-s", "--summary", default=DEFAULT_SUMMARY, help="Output readable summary file")

    args = parser.parse_args()

    normalize_skills(args.input, args.output, args.summary)
