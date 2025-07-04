import json
import logging
import re
from difflib import SequenceMatcher
from sys import stdout
from typing import Dict, List
from tqdm import tqdm

try:
    stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Configuration
MIN_GROUP_SIZE = 3
SIMILARITY_THRESHOLD = 0.8
DEFAULT_INPUT = "processed_parse_jobs.json"
DEFAULT_OUTPUT = "normalized_skills.json"
DEFAULT_SUMMARY = "output_categories.txt"
DEFAULT_CATEGORIES_FILE = "category_hierarchy.json"  # New output file for categories

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('skill_normalization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_category_hierarchy(file_path: str) -> Dict:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading category hierarchy: {e}", exc_info=True)
        return {}

# Flatten categories
def flatten_categories(hierarchy, prefix=""):
    flat = {}
    for cat, val in hierarchy.items():
        if isinstance(val, dict):
            flat.update(flatten_categories(val, f"{prefix}{cat}_"))
        else:
            flat[f"{prefix}{cat}"] = val
    return flat


CATEGORY_HIERARCHY = load_category_hierarchy(DEFAULT_CATEGORIES_FILE)
MAIN_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY.get('TECHNICAL', {}))
NON_TECH_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY.get('NON_TECHNICAL', {}))
ALL_CATEGORIES = {**MAIN_CATEGORIES, **NON_TECH_CATEGORIES}

CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "asp.net": "aspdotnet", "oop": "object oriented programming",
    "devops": "ci/cd", "cloud": "cloud computing", "db": "database"
}

EXPERIENCE_PATTERNS = [r"\d+\+?\s*years?"]
DISCARD_PHRASES = ["years of experience", "experience with", "knowledge of", "understanding of"]


def clean_skill_name(skill_name):
    if not skill_name:
        return ""
    skill = skill_name.lower().strip()
    skill = re.sub(r'\([^)]*\)', '', skill)
    skill = re.sub(r'\[[^\]]*\]', '', skill)
    skill = re.sub(r'^proficiency in\s*', '', skill)
    skill = re.sub(r'[.,;:]$', '', skill)
    return skill.strip()


def should_discard(skill_name):
    if len(skill_name.strip()) < 2 or len(skill_name.split()) > 6:
        return True
    if any(re.search(p, skill_name, re.IGNORECASE) for p in EXPERIENCE_PATTERNS):
        return True
    return any(p in skill_name.lower() for p in DISCARD_PHRASES)


def normalize_skill(skill_name):
    if not skill_name:
        return ""
    skill = skill_name.lower().strip()
    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    skill = skill.replace("&", " and ").replace("/", " ").replace("-", " ")
    skill = re.sub(r"[^a-z0-9\s]+", "", skill)
    for alias, std in CATEGORY_ALIASES.items():
        skill = re.sub(rf'\b{re.escape(alias)}\b', std, skill)
    return re.sub(r'\s+', ' ', skill).strip()


def should_group_together(a, b):
    na, nb = normalize_skill(a), normalize_skill(b)
    if na == nb or re.search(rf'\b{re.escape(na)}\b', nb) or re.search(rf'\b{re.escape(nb)}\b', na):
        return True
    if na[:4] == nb[:4] and len(na) <= 5 and len(nb) <= 5:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= SIMILARITY_THRESHOLD


def determine_primary_category(skill_name):
    norm_skill = normalize_skill(skill_name)

    # First check technical categories
    for category, keywords in MAIN_CATEGORIES.items():
        if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
            return category

    # Then check non-technical categories
    for category, keywords in NON_TECH_CATEGORIES.items():
        if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
            return category

    # Fallback to GENERAL_TECH subcategories
    general_tech_cats = CATEGORY_HIERARCHY['TECHNICAL']['GENERAL_TECH']
    for subcat, keywords in general_tech_cats.items():
        if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
            return f"GENERAL_TECH_{subcat}"

    return "GENERAL_TECH"


def extract_all_skill_names_from_jobs(file_path: str) -> List[str]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        skills = set()
        for job in data:
            for key in ['KeySkillsRequired', 'EssentialQualifications',
                        'EssentialTechnicalSkillQualifications', 'OtherTechnicalSkillQualifications']:
                for skill in job.get(key, []):
                    name = skill.get('Name')
                    if name:
                        cleaned = clean_skill_name(name)
                        if cleaned and not should_discard(cleaned):
                            skills.add(cleaned)
        logger.info(f"Extracted {len(skills)} unique skills")
        return list(skills)
    except Exception as e:
        logger.error(f"Error extracting skills: {e}", exc_info=True)
        return []


def create_initial_groups(skills: List[str]) -> Dict[str, List[str]]:
    groups = {}
    for skill in tqdm(skills, desc="Grouping skills"):
        matched = False
        for group in list(groups):
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
            if should_discard(skill):
                continue
            new_cat = determine_primary_category(skill)
            final_groups.setdefault(new_cat, []).append(skill)
    return {k: sorted(set(v)) for k, v in final_groups.items()}


def save_results(output_file: str, results: Dict[str, List[str]]):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def save_categories_summary(groups: Dict[str, List[str]], output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        for category, skills in sorted(groups.items()):
            f.write(f"[{category}] - {len(skills)} skills\n")
            for skill in sorted(skills):
                f.write(f"  - {skill}\n")
            f.write("\n")

def save_augmented_jobs_with_skills(input_file: str, final_groups: Dict[str, List[str]], array_name: str):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            jobs = json.load(f)

        skill_to_category = {}
        for category, skills in final_groups.items():
            for skill in skills:
                skill_to_category[skill] = category

        for job in jobs:
            category_map = {}

            for skill in job.get(array_name, []):
                name = skill.get('Name')
                relevance = skill.get('RelevancePercentage', 0)

                if name:
                    cleaned = clean_skill_name(name)
                    if cleaned and not should_discard(cleaned):
                        category = skill_to_category.get(cleaned, "UNCATEGORIZED")
                        if category not in category_map:
                            category_map[category] = {
                                "category": category,
                                "relevance": relevance
                            }
                        else:
                            category_map[category]["relevance"] += relevance

            job['Skills'] = sorted(
                [
                    {"category": value["category"], "relevance": round(value["relevance"], 2)}
                    for value in category_map.values()
                ],
                key=lambda x: x["relevance"],
                reverse=True
            )

        output_path = input_file.replace(".json", "_with_skills.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

        logger.info(f"Augmented job file saved to {output_path}")
    except Exception as e:
        logger.error(f"Error saving augmented job file: {e}", exc_info=True)


def save_category_hierarchy(output_file: str):
    """Save the CATEGORY_HIERARCHY dictionary to a JSON file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(CATEGORY_HIERARCHY, f, indent=2, ensure_ascii=False)
        logger.info(f"Category hierarchy saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving category hierarchy: {e}", exc_info=True)

def main(input_file=DEFAULT_INPUT, output_file=DEFAULT_OUTPUT, summary_file=DEFAULT_SUMMARY):
    logger.info("=== Script started ===")
    logger.info(f"Command line arguments: input={input_file}, output={output_file}, summary={summary_file}")

    # Step 1: Extract skills
    skills = extract_all_skill_names_from_jobs(input_file)
    initial_groups = create_initial_groups(skills)
    logger.info(f"Created {len(initial_groups)} initial groups")

    # Step 2: Consolidate skill groups
    consolidated = consolidate_groups(initial_groups)
    logger.info(f"Consolidated into {len(consolidated)} groups")

    # Step 3: Final filtering and reclassification
    final_groups = filter_and_reclassify_groups(consolidated)
    logger.info(f"Final categories: {len(final_groups)}")

    # Step 4: Save results
    save_results(output_file, final_groups)
    save_categories_summary(final_groups, summary_file)
    save_augmented_jobs_with_skills(input_file, final_groups, 'KeySkillsRequired')

    # Step 5: Save category hierarchy at the end (in case it was edited or enriched)
    save_category_hierarchy(DEFAULT_CATEGORIES_FILE)

    logger.info("=== Script completed successfully ===")


if __name__ == "__main__":
    main()