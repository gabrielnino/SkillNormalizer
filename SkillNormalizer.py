import json
import logging
import re
import sys
from difflib import SequenceMatcher
from typing import Dict, List
from tqdm import tqdm

# Configuración
MIN_GROUP_SIZE = 3
SIMILARITY_THRESHOLD = 0.8
DEFAULT_INPUT = "processed_parse_jobs.json"
DEFAULT_OUTPUT = "normalized_skills.json"
DEFAULT_SUMMARY = "output_categories.txt"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Categorías técnicas ampliadas
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
    'LANGUAGES': ['c', 'c++', 'csharp', 'python', 'go', 'golang', 'java', 'kotlin', 'typescript', 'javascript'],
    'DEV_TOOLS': ['vscode', 'visual studio', 'copilot', 'grafana', 'kibana', 'figma', 'notion']
}

NON_TECH_CATEGORIES = {
    'BUSINESS': ['sales', 'negotiation', 'client', 'customer'],
    'OPERATIONS': ['warehouse', 'forklift', 'logistics'],
    'HEALTHCARE': ['patient', 'radiology', 'nursing', 'medical'],
    'EDUCATION': ['teaching', 'tutoring', 'curriculum']
}

CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "ts": "typescript", "js": "javascript", "py": "python"
}

SOFT_KEYWORDS = [
    "communication", "leadership", "teamwork", "organized", "motivation", "creativity", "problem solving",
    "growth mindset", "analytical", "critical thinking", "collaboration", "attention to detail",
    "willing to learn", "eager", "customer service", "passion", "enthusiasm", "smiling", "curious"
]

DISCARD_PHRASES = [
    "years of experience", "bachelor", "master", "degree", "diploma", "license", "licence",
    "required", "experience in", "familiarity with", "equivalent", "preferred", "valid driver"
]


def extract_all_skill_names_from_jobs(file_path: str) -> List[str]:
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
    skill = skill_name.lower().strip()
    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    skill = re.sub(r"[^a-z0-9]+", "", skill)

    if skill in CATEGORY_ALIASES:
        skill = CATEGORY_ALIASES[skill]

    return skill


def is_valid_group_name(name: str) -> bool:
    return len(name.split()) <= 5 and len(name.strip()) >= 3


def is_technical(skill: str) -> bool:
    norm = normalize_skill(skill)
    if not norm:
        return False
    tech_keywords = {kw for cat in MAIN_CATEGORIES.values() for kw in cat}
    return any(kw in norm for kw in tech_keywords)


def should_group_together(a: str, b: str) -> bool:
    norm_a, norm_b = normalize_skill(a), normalize_skill(b)
    if not norm_a or not norm_b:
        return False
    if norm_a in norm_b or norm_b in norm_a:
        return True
    if norm_a[:4] == norm_b[:4]:
        return True
    return SequenceMatcher(None, norm_a, norm_b).ratio() >= SIMILARITY_THRESHOLD


def determine_primary_category(skill_name: str) -> str:
    norm_skill = normalize_skill(skill_name)
    for category, keywords in MAIN_CATEGORIES.items():
        if any(kw in norm_skill for kw in keywords):
            return category.upper()
    for category, keywords in NON_TECH_CATEGORIES.items():
        if any(kw in norm_skill for kw in keywords):
            return f"NON_TECH_{category.upper()}"
    return "OTHER_TECH" if is_technical(skill_name) else "OTHER_NON_TECH"


def create_initial_groups(skills: List[str]) -> Dict[str, List[str]]:
    groups = {}
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
    consolidated = {}
    for group_name, skills in groups.items():
        category = determine_primary_category(group_name)
        if len(skills) < MIN_GROUP_SIZE:
            if category not in consolidated:
                consolidated[category] = []
            consolidated[category].extend(skills)
        else:
            consolidated[group_name] = skills
    return {k: sorted(list(set(v))) for k, v in consolidated.items()}


def filter_and_reclassify_groups(groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
    final_groups = {}
    for category, skills in groups.items():
        for skill in skills:
            skill_lower = skill.lower()
            if any(p in skill_lower for p in DISCARD_PHRASES):
                continue
            if any(kw in skill_lower for kw in SOFT_KEYWORDS):
                target = "SOFT_SKILLS"
            else:
                target = determine_primary_category(skill)
            if target not in final_groups:
                final_groups[target] = []
            final_groups[target].append(skill)
    return {cat: sorted(set(vals)) for cat, vals in final_groups.items()}


def save_results(output_file: str, results: Dict[str, List[str]]) -> None:
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved results to {output_file}")
    except IOError as e:
        logger.error(f"Error writing output file: {e}")
        sys.exit(1)


def save_categories_summary(final_groups: Dict[str, List[str]], output_path: str) -> None:
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for category, skills in sorted(final_groups.items()):
                f.write(f"[{category}] - {len(skills)} skills\n")
                for skill in sorted(skills):
                    f.write(f"  - {skill}\n")
                f.write("\n")
        logger.info(f"Saved summary to {output_path}")
    except IOError as e:
        logger.error(f"Error writing summary file: {e}")


def normalize_skills(input_file: str, output_file: str, summary_file: str) -> None:
    logger.info(f"Processing file: {input_file}")
    skills = extract_all_skill_names_from_jobs(input_file)

    logger.info("Grouping skills...")
    groups = create_initial_groups(skills)

    logger.info("Consolidating groups...")
    consolidated = consolidate_groups(groups)

    logger.info("Filtering and reclassifying...")
    refined = filter_and_reclassify_groups(consolidated)

    save_results(output_file, refined)
    save_categories_summary(refined, summary_file)

    print(f"\n✅ Total categories: {len(refined)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Advanced Skill Normalization Tool")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT, help="Input JSON file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="Output JSON grouped file")
    parser.add_argument("-s", "--summary", default=DEFAULT_SUMMARY, help="Human-readable category summary")

    args = parser.parse_args()
    normalize_skills(args.input, args.output, args.summary)
