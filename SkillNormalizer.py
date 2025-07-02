import json
import logging
import re
import sys
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple
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

# Main technical categories with enhanced keyword matching
MAIN_CATEGORIES = {
    '.NET': ['dotnet', 'csharp', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entityframework'],
    'CLOUD_AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb', 'amazon web services'],
    'CLOUD_AZURE': ['azure', 'functions', 'entra', 'sql database', 'microsoft azure'],
    'CLOUD_GCP': ['gcp', 'google cloud', 'google cloud platform'],
    'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'mssql', 'sql server', 'postgresql', 'plsql'],
    'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb', 'nosql', 'documentdb'],
    'FRONTEND': ['react', 'angular', 'vue', 'javascript', 'typescript', 'html', 'css', 'bootstrap', 'sass', 'less',
                 'frontend', 'front end'],
    'BACKEND': ['node', 'python', 'java', 'spring', 'ruby', 'php', 'golang', 'go', 'c\+\+', 'c\#', 'kotlin', 'backend',
                'back end'],
    'DEVOPS': ['docker', 'kubernetes', 'terraform', 'ci/cd', 'jenkins', 'git', 'ansible', 'puppet', 'devops'],
    'TESTING': ['test', 'tdd', 'qa', 'junit', 'selenium', 'mocha', 'jest', 'playwright', 'cypress', 'testing'],
    'NETWORKING': ['tcp/ip', 'dns', 'dhcp', 'network', 'firewall', 'networking', 'vpn', 'wifi'],
    'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance', 'spark', 'hadoop',
                         'data engineering', 'data lake'],
    'SECURITY': ['oauth2', 'openid', 'iam', 'rbac', 'sso', 'encryption', 'security', 'cybersecurity'],
    'ML_AI': ['ai', 'ml', 'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit', 'vision', 'llm',
              'generative ai'],
    'LANGUAGES': ['french', 'english', 'spanish', 'german', 'language', 'bilingual'],
    'DEV_TOOLS': ['vscode', 'visual studio', 'copilot', 'grafana', 'kibana', 'figma', 'notion', 'ide'],
    'GAME_DEV': ['unreal', 'unity', 'game development', 'gamedev', 'game engine'],
    'BUSINESS_INTEL': ['power bi', 'tableau', 'business intelligence', 'bi', 'data visualization']
}

# Non-technical categories with enhanced matching
NON_TECH_CATEGORIES = {
    'BUSINESS': ['sales', 'negotiation', 'client', 'customer', 'cold calling', 'business', 'marketing'],
    'OPERATIONS': ['warehouse', 'forklift', 'logistics', 'kitchen', 'inventory', 'operations', 'supply chain'],
    'HEALTHCARE': ['patient', 'radiology', 'nursing', 'medical', 'emergency care', 'healthcare', 'hospital'],
    'EDUCATION': ['teaching', 'tutoring', 'curriculum', 'interactive teaching', 'education', 'teacher'],
    'LANGUAGES': ['fluency', 'language proficiency', 'translation', 'linguistics']
}

CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "ts": "typescript", "js": "javascript", "py": "python",
    "postgres": "postgresql", "mssql": "sql server", "ai": "machine learning",
    "ml": "machine learning", "bi": "business intelligence"
}

SOFT_KEYWORDS = [
    "communication", "leadership", "teamwork", "organized", "motivation", "creativity", "problem solving",
    "growth mindset", "analytical", "critical thinking", "collaboration", "attention to detail",
    "willing to learn", "eager", "customer service", "passion", "enthusiasm", "smiling", "curious",
    "mentorship", "coaching", "people skills", "adaptability", "time management", "decision making",
    "emotional intelligence", "conflict resolution", "negotiation", "presentation", "public speaking"
]

# Enhanced patterns for experience statements and other non-skill phrases
EXPERIENCE_PATTERNS = [
    r"\d+\+ years", r"\d+ years", r"\d+-\d+ years", r"\d+ to \d+ years",
    r"years of experience", r"years experience", r"minimum \d+ years",
    r"at least \d+ years", r"over \d+ years", r"more than \d+ years"
]

DISCARD_PHRASES = [
    "years of experience", "bachelor", "master", "degree", "diploma", "license", "licence",
    "required", "experience in", "familiarity with", "equivalent", "preferred", "valid driver",
    "ability to", "knowledge of", "understanding of", "exposure to", "background in", "familiar with"
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
                        # Initial cleaning of skill names
                        cleaned = clean_skill_name(name)
                        if cleaned and not should_discard(cleaned):
                            skills.add(cleaned)

        logger.info(f"Extracted {len(skills)} unique skills")
        return list(skills)

    except Exception as e:
        logger.error(f"Error extracting skills: {e}", exc_info=True)
        return []


def clean_skill_name(skill_name: str) -> str:
    """Clean and normalize a skill name before processing"""
    if not skill_name:
        return ""

    # Convert to lowercase and strip whitespace
    skill = skill_name.lower().strip()

    # Remove content in parentheses/brackets that often contains experience levels
    skill = re.sub(r'\([^)]*\)', '', skill)
    skill = re.sub(r'\[[^\]]*\]', '', skill)

    # Remove common prefixes/suffixes
    skill = re.sub(r'^proficiency in\s*', '', skill)
    skill = re.sub(r'^experience with\s*', '', skill)
    skill = re.sub(r'^knowledge of\s*', '', skill)
    skill = re.sub(r'^strong\s*', '', skill)
    skill = re.sub(r'^expertise in\s*', '', skill)

    # Remove trailing punctuation
    skill = re.sub(r'[.,;:]$', '', skill)

    return skill.strip()


def should_discard(skill_name: str) -> bool:
    """Determine if a skill should be discarded based on patterns"""
    # Check for experience patterns
    for pattern in EXPERIENCE_PATTERNS:
        if re.search(pattern, skill_name):
            return True

    # Check for discard phrases
    for phrase in DISCARD_PHRASES:
        if phrase in skill_name:
            return True

    # Check if it's too short to be meaningful
    if len(skill_name.split()) > 6:  # Too long probably not a skill
        return True

    return False


def normalize_skill(skill_name: str) -> str:
    """Normalize a skill name for comparison"""
    if not skill_name:
        return ""

    skill = skill_name.lower().strip()

    # Replace common variations with standard forms
    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    skill = skill.replace("&", "and").replace("/", " ")
    skill = re.sub(r"[^a-z0-9\s]+", "", skill)  # Remove special chars but keep spaces

    # Apply aliases
    for alias, standard in CATEGORY_ALIASES.items():
        if alias in skill:
            skill = skill.replace(alias, standard)

    return skill


def should_group_together(a: str, b: str) -> bool:
    norm_a, norm_b = normalize_skill(a), normalize_skill(b)

    # Exact match after normalization
    if norm_a == norm_b:
        return True

    # One is contained in the other
    if norm_a in norm_b or norm_b in norm_a:
        return True

    # Same first 4 characters (for abbreviations)
    if norm_a[:4] == norm_b[:4]:
        return True

    # High similarity ratio
    return SequenceMatcher(None, norm_a, norm_b).ratio() >= SIMILARITY_THRESHOLD


def determine_primary_category(skill_name: str) -> str:
    norm_skill = normalize_skill(skill_name)
    raw_skill = skill_name.lower()

    # First check technical categories
    for category, keywords in MAIN_CATEGORIES.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', norm_skill):
                return category

    # Then check non-technical categories
    for category, keywords in NON_TECH_CATEGORIES.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', raw_skill):
                return f"NON_TECH_{category.upper()}"

    # Check for soft skills
    for kw in SOFT_KEYWORDS:
        if kw in raw_skill:
            return "SOFT_SKILLS"

    # Special handling for backend technologies that might overlap with other categories
    backend_keywords = MAIN_CATEGORIES['BACKEND']
    for kw in backend_keywords:
        if kw in norm_skill:
            # Check if it might belong to a more specific category
            for other_cat in ['DEVOPS', 'ML_AI', 'SECURITY', 'DATA_ENGINEERING']:
                for other_kw in MAIN_CATEGORIES[other_cat]:
                    if other_kw in norm_skill:
                        return other_cat
            return "BACKEND"

    return "GENERAL_TECH"


def create_initial_groups(skills: List[str]) -> Dict[str, List[str]]:
    groups = {}
    for skill in tqdm(skills, desc="Grouping skills"):
        matched = False
        for group in list(groups.keys()):  # Create a copy of keys to iterate over
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

    # Extract and clean skills
    skills = extract_all_skill_names_from_jobs(input_file)

    # Group similar skills
    initial_groups = create_initial_groups(skills)

    # Consolidate small groups into categories
    consolidated = consolidate_groups(initial_groups)

    # Final filtering and reclassification
    final_groups = filter_and_reclassify_groups(consolidated)

    # Save results
    save_results(output_file, final_groups)
    save_categories_summary(final_groups, summary_file)

    logger.info("=== Script completed successfully ===")


if __name__ == "__main__":
    main()