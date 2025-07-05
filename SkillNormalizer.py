import json
import logging
import re
from difflib import SequenceMatcher
from sys import stdout
from typing import Dict, List
from tqdm import tqdm

# --- Setup logging ---
try:
    stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('skill_normalization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Constants ---
MIN_GROUP_SIZE = 3
SIMILARITY_THRESHOLD = 0.8
DEFAULT_INPUT = "processed_parse_jobs.json"
DEFAULT_OUTPUT = "normalized_skills.json"
DEFAULT_SUMMARY = "output_categories.txt"
DEFAULT_CATEGORIES_FILE = "category_hierarchy.json"

CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "asp.net": "aspdotnet", "oop": "object oriented programming",
    "devops": "ci/cd", "cloud": "cloud computing", "db": "database"
}

EXPERIENCE_PATTERNS = [r"\d+\+?\s*years?"]
DISCARD_PHRASES = ["years of experience", "experience with", "knowledge of", "understanding of"]


# --- Helper Functions ---
def flatten_categories(hierarchy, prefix=""):
    flat = {}
    for cat, val in hierarchy.items():
        if isinstance(val, dict):
            flat.update(flatten_categories(val, f"{prefix}{cat}_"))
        else:
            flat[f"{prefix}{cat}"] = val
    return flat


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


# --- SkillNormalizer Class ---
class SkillNormalizer:
    def __init__(self, input_file: str, categories_file: str):
        self.input_file = input_file
        self.categories_file = categories_file
        self.output_file = input_file.replace(".json", "_normalized.json")
        self.summary_file = input_file.replace(".json", "_categories.txt")

        self.jobs_data = []
        self.skills = []
        self.category_hierarchy = self.load_category_hierarchy()
        self.main_categories = flatten_categories(self.category_hierarchy.get('TECHNICAL', {}))
        self.non_tech_categories = flatten_categories(self.category_hierarchy.get('NON_TECHNICAL', {}))
        self.all_categories = {**self.main_categories, **self.non_tech_categories}

    def load_category_hierarchy(self) -> Dict:
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading category hierarchy: {e}", exc_info=True)
            return {}

    def determine_primary_category(self, skill_name):
        norm_skill = normalize_skill(skill_name)

        for category, keywords in self.main_categories.items():
            if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
                return category

        for category, keywords in self.non_tech_categories.items():
            if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
                return category

        general_tech_cats = self.category_hierarchy.get('TECHNICAL', {}).get('GENERAL_TECH', {})
        for subcat, keywords in general_tech_cats.items():
            if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
                return f"GENERAL_TECH_{subcat}"

        return "GENERAL_TECH"

    def extract_skills(self) -> List[str]:
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                self.jobs_data = json.load(f)
            skills = set()
            for job in self.jobs_data:
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

    def group_skills(self, skills: List[str]) -> Dict[str, List[str]]:
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

    def consolidate_groups(self, groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
        consolidated = {}
        for group_name, skills in groups.items():
            category = self.determine_primary_category(group_name)
            if len(skills) < MIN_GROUP_SIZE:
                consolidated.setdefault(category, []).extend(skills)
            else:
                consolidated[group_name] = skills
        return {k: sorted(set(v)) for k, v in consolidated.items()}

    def reclassify_groups(self, groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
        final_groups = {}
        for category, skills in groups.items():
            for skill in skills:
                if should_discard(skill):
                    continue
                new_cat = self.determine_primary_category(skill)
                final_groups.setdefault(new_cat, []).append(skill)
        return {k: sorted(set(v)) for k, v in final_groups.items()}

    def save_results(self, results: Dict[str, List[str]]):
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    def save_summary(self, groups: Dict[str, List[str]]):
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            for category, skills in sorted(groups.items()):
                f.write(f"[{category}] - {len(skills)} skills\n")
                for skill in sorted(skills):
                    f.write(f"  - {skill}\n")
                f.write("\n")

    def save_augmented_jobs(self, final_groups: Dict[str, List[str]]):
        skill_to_category = {}
        for category, skills in final_groups.items():
            for skill in skills:
                skill_to_category[skill] = category

        for job in self.jobs_data:
            category_map = {}
            for skill in job.get('KeySkillsRequired', []):
                name = skill.get('Name')
                relevance = skill.get('RelevancePercentage', 0)
                if name:
                    cleaned = clean_skill_name(name)
                    if cleaned and not should_discard(cleaned):
                        category = skill_to_category.get(cleaned, "UNCATEGORIZED")
                        if category not in category_map:
                            category_map[category] = {"category": category, "relevance": relevance}
                        else:
                            category_map[category]["relevance"] += relevance

            job['Skills'] = sorted(
                [{"category": value["category"], "relevance": round(value["relevance"], 2)}
                 for value in category_map.values()],
                key=lambda x: x["relevance"],
                reverse=True
            )

        output_path = self.input_file.replace(".json", "_with_skills.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.jobs_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Augmented job file saved to {output_path}")

    def save_category_hierarchy(self):
        try:
            with open(self.categories_file, 'w', encoding='utf-8') as f:
                json.dump(self.category_hierarchy, f, indent=2, ensure_ascii=False)
            logger.info(f"Category hierarchy saved to {self.categories_file}")
        except Exception as e:
            logger.error(f"Error saving category hierarchy: {e}", exc_info=True)

    def run(self):
        logger.info("=== Normalization Started ===")
        self.skills = self.extract_skills()
        initial_groups = self.group_skills(self.skills)
        consolidated = self.consolidate_groups(initial_groups)
        final_groups = self.reclassify_groups(consolidated)
        self.save_results(final_groups)
        self.save_summary(final_groups)
        self.save_augmented_jobs(final_groups)
        self.save_category_hierarchy()
        logger.info("=== Normalization Completed ===")


# --- Entry point ---
if __name__ == "__main__":
    normalizer = SkillNormalizer(DEFAULT_INPUT, DEFAULT_CATEGORIES_FILE)
    normalizer.run()
