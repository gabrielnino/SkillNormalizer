import json
import logging
import re
import sys
from difflib import SequenceMatcher
from typing import Dict, List
from tqdm import tqdm

# Ensure stdout uses UTF-8 (especially helpful on Windows)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Configuration
MIN_GROUP_SIZE = 3
SIMILARITY_THRESHOLD = 0.8
DEFAULT_INPUT = "processed_parse_jobs.json"
DEFAULT_OUTPUT = "normalized_skills.json"
DEFAULT_SUMMARY = "output_categories.txt"

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('skill_normalization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Main technical categories
MAIN_CATEGORIES = {
    '.NET': ['dotnet', 'csharp', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entityframework'],
    'CLOUD_AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb'],
    'CLOUD_AZURE': ['azure', 'functions', 'entra', 'sql database'],
    'CLOUD_GCP': ['gcp', 'google cloud'],
    'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'mssql'],
    'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb'],
    'FRONTEND': ['react', 'angular', 'vue', 'javascript', 'typescript', 'html', 'css', 'bootstrap'],
    'BACKEND': ['node', 'python', 'java', 'spring', 'ruby', 'php', 'golang', 'go', 'c++', 'c', 'kotlin'],
    'DEVOPS': ['docker', 'kubernetes', 'terraform', 'ci/cd', 'jenkins', 'git'],
    'TESTING': ['test', 'tdd', 'qa', 'junit', 'selenium', 'mocha', 'jest'],
    'NETWORKING': ['tcp/ip', 'dns', 'dhcp', 'network', 'firewall'],
    'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance', 'spark', 'hadoop'],
    'SECURITY': ['oauth2', 'openid', 'iam', 'rbac', 'sso', 'encryption'],
    'ML_AI': ['ai', 'ml', 'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit', 'vision'],
    'LANGUAGES': ['french', 'english', 'spanish', 'german'],
    'DEV_TOOLS': ['vscode', 'visual studio', 'copilot', 'grafana', 'kibana', 'figma', 'notion']
}

# Non-technical categories
NON_TECH_CATEGORIES = {
    'BUSINESS': ['sales', 'negotiation', 'client', 'customer', 'cold calling'],
    'OPERATIONS': ['warehouse', 'forklift', 'logistics', 'kitchen', 'inventory'],
    'HEALTHCARE': ['patient', 'radiology', 'nursing', 'medical', 'emergency care'],
    'EDUCATION': ['teaching', 'tutoring', 'curriculum', 'interactive teaching'],
    'LANGUAGES': ['fluency', 'language proficiency']
}

CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "ts": "typescript", "js": "javascript", "py": "python"
}

SOFT_KEYWORDS = [
    "communication", "leadership", "teamwork", "organized", "motivation", "creativity", "problem solving",
    "growth mindset", "analytical", "critical thinking", "collaboration", "attention to detail",
    "willing to learn", "eager", "customer service", "passion", "enthusiasm", "smiling", "curious",
    "mentorship", "coaching", "people skills"
]

DISCARD_PHRASES = [
    "years of experience", "bachelor", "master", "degree", "diploma", "license", "licence",
    "required", "experience in", "familiarity with", "equivalent", "preferred", "valid driver"
]


def extract_all_skill_names_from_jobs(file_path: str) -> List[str]:
    try:
        logger.info(f"Starting to extract skills from {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        skills = set()
        for job in data:
            for key in ['KeySkillsRequired', 'EssentialQualifications',
                        'EssentialTechnicalSkillQualifications', 'OtherTechnicalSkillQualifications']:
                for skill in job.get(key, []):
                    name = skill.get('Name')
                    if name:
                        skills.add(name.strip())

        logger.info(f"Extracted {len(skills)} unique skills")
        return list(skills)

    except Exception as e:
        logger.error(f"Error extracting skills: {e}", exc_info=True)
        return []


def normalize_skill(skill_name: str) -> str:
    if not skill_name:
        return ""
    skill = skill_name.lower().strip()
    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    skill = re.sub(r"[^a-z0-9]+", "", skill)
    return CATEGORY_ALIASES.get(skill, skill)


def should_group_together(a: str, b: str) -> bool:
    norm_a, norm_b = normalize_skill(a), normalize_skill(b)
    if norm_a in norm_b or norm_b in norm_a:
        return True
    if norm_a[:4] == norm_b[:4]:
        return True
    return SequenceMatcher(None, norm_a, norm_b).ratio() >= SIMILARITY_THRESHOLD


def determine_primary_category(skill_name: str) -> str:
    norm_skill = normalize_skill(skill_name)
    raw_skill = skill_name.lower()

    for category in MAIN_CATEGORIES:
        for kw in MAIN_CATEGORIES[category]:
            if kw in norm_skill:
                return category

    for category, keywords in NON_TECH_CATEGORIES.items():
        for kw in keywords:
            if kw in raw_skill:
                return f"NON_TECH_{category.upper()}"

    for kw in SOFT_KEYWORDS:
        if kw in raw_skill:
            return "SOFT_SKILLS"

    for kw in MAIN_CATEGORIES['BACKEND']:
        if kw in norm_skill:
            for other_cat in ['DEVOPS', 'ML_AI', 'SECURITY', 'DATA_ENGINEERING']:
                for other_kw in MAIN_CATEGORIES[other_cat]:
                    if other_kw in norm_skill:
                        return "GENERAL_TECH"
            return "BACKEND"

    return "GENERAL_TECH"


def create_initial_groups(skills: List[str]) -> Dict[str, List[str]]:
    groups = {}
    for skill in tqdm(skills, desc="Grouping skills"):
        matched = False
        for group in groups:
            if should_group_together(skill, group):
                groups[group].append(skill)
                matched = True
                break
        if not matched:
            groups[skill] = [skill]
    return groups


def consolidate_groups(groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
    consolidated = {}
    for group_name, skills in groups.items():
        category = determine_primary_category(group_name)
        if len(skills) < MIN_GROUP_SIZE:
            consolidated.setdefault(category, []).extend(skills)
        else:
            consolidated[group_name] = skills
    return {k: sorted(set(v)) for k, v in consolidated.items()}


def filter_and_reclassify_groups(groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
    final_groups = {}
    for category, skills in groups.items():
        for skill in skills:
            if any(p in skill.lower() for p in DISCARD_PHRASES):
                continue
            new_cat = determine_primary_category(skill)
            final_groups.setdefault(new_cat, []).append(skill)
    return {k: sorted(set(v)) for k, v in final_groups.items()}


def save_results(output_file: str, results: Dict[str, List[str]]) -> None:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def save_categories_summary(groups: Dict[str, List[str]], output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
        for category, skills in sorted(groups.items()):
            f.write(f"[{category}] - {len(skills)} skills\n")
            for skill in sorted(skills):
                f.write(f"  - {skill}\n")
            f.write("\n")


def main(input_file=DEFAULT_INPUT, output_file=DEFAULT_OUTPUT, summary_file=DEFAULT_SUMMARY):
    logger.info("=== Script started ===")
    logger.info(f"Command line arguments: input={input_file}, output={output_file}, summary={summary_file}")
    skills = extract_all_skill_names_from_jobs(input_file)
    initial_groups = create_initial_groups(skills)
    consolidated = consolidate_groups(initial_groups)
    final_groups = filter_and_reclassify_groups(consolidated)
    save_results(output_file, final_groups)
    save_categories_summary(final_groups, summary_file)
    logger.info("=== Script completed successfully ===")


if __name__ == "__main__":
    main()
