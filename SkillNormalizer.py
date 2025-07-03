import json
import logging
import re
import sys
from collections import defaultdict
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

# Enhanced category definitions with more precise boundaries
CATEGORY_HIERARCHY = {
    'TECHNICAL': {
        'PROGRAMMING': {
            '.NET': ['dotnet', 'csharp', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entityframework'],
            'JAVA_ECOSYSTEM': ['java', 'spring', 'spring boot', 'hibernate', 'j2ee', 'jakarta ee'],
            'PYTHON_ECOSYSTEM': ['python', 'django', 'flask', 'fastapi', 'numpy', 'pandas'],
            'JAVASCRIPT_TYPESCRIPT': ['javascript', 'typescript', 'ecmascript', 'es6'],
            'GO': ['golang', 'go'],
            'RUST': ['rust'],
            'RUBY': ['ruby', 'rails', 'ruby on rails'],
            'PHP': ['php', 'laravel', 'symfony'],
            'C_CPP': ['c', 'c\+\+', 'cplusplus', 'cpp'],
            'MOBILE': ['android', 'ios', 'flutter', 'react native', 'swift', 'kotlin'],
        },
        'FRONTEND': {
            'FRAMEWORKS': ['react', 'angular', 'vue', 'svelte', 'ember'],
            'STYLING': ['css', 'sass', 'scss', 'less', 'bootstrap', 'tailwind'],
            'BUILD_TOOLS': ['webpack', 'vite', 'rollup', 'parcel'],
            'WEB_COMPONENTS': ['html', 'web components', 'shadow dom', 'custom elements'],
        },
        'BACKEND': {
            'APIS': ['rest', 'graphql', 'grpc', 'soap', 'openapi', 'swagger'],
            'SERVER': ['node', 'express', 'nestjs', 'koa', 'fastify'],
            'AUTH': ['oauth', 'jwt', 'openid connect', 'saml', 'ldap'],
            'MESSAGING': ['kafka', 'rabbitmq', 'nats', 'activemq'],
        },
        'DATA': {
            'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'postgresql', 'mssql', 'sql server', 'plsql'],
            'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb', 'dynamodb', 'firestore'],
            'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance', 'data warehouse'],
            'BIG_DATA': ['spark', 'hadoop', 'hive', 'hbase', 'bigquery'],
            'DATA_SCIENCE': ['pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn'],
        },
        'CLOUD': {
            'AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb', 'amazon web services', 'ec2', 'rds'],
            'AZURE': ['azure', 'functions', 'entra', 'sql database', 'microsoft azure', 'azure ad'],
            'GCP': ['gcp', 'google cloud', 'google cloud platform', 'bigtable', 'cloud functions'],
            'CLOUD_GENERAL': ['kubernetes', 'docker', 'serverless', 'paas', 'saas', 'iaas'],
        },
        'DEVOPS': {
            'CI_CD': ['ci/cd', 'jenkins', 'github actions', 'gitlab ci', 'circleci'],
            'INFRA_AS_CODE': ['terraform', 'pulumi', 'cloudformation', 'ansible'],
            'MONITORING': ['grafana', 'prometheus', 'datadog', 'new relic', 'splunk'],
            'VERSION_CONTROL': ['git', 'svn', 'mercurial', 'perforce'],
        },
        'TESTING': {
            'UNIT_TESTING': ['junit', 'nunit', 'pytest', 'mocha', 'jest'],
            'E2E_TESTING': ['selenium', 'cypress', 'playwright', 'testcafe'],
            'PERFORMANCE': ['jmeter', 'gatling', 'locust', 'k6'],
            'TEST_AUTOMATION': ['test automation', 'bdd', 'tdd', 'qa automation'],
        },
        'ML_AI': {
            'MACHINE_LEARNING': ['machine learning', 'ml', 'tensorflow', 'pytorch', 'scikit-learn'],
            'DEEP_LEARNING': ['deep learning', 'neural networks', 'cnn', 'rnn'],
            'NLP': ['nlp', 'natural language processing', 'transformers', 'bert'],
            'COMPUTER_VISION': ['computer vision', 'opencv', 'object detection', 'image processing'],
            'AI_GENERAL': ['ai', 'artificial intelligence', 'llm', 'generative ai', 'chatgpt'],
        },
        'SECURITY': {
            'APP_SECURITY': ['owasp', 'security', 'penetration testing', 'vulnerability'],
            'IDENTITY': ['iam', 'rbac', 'sso', 'oauth', 'openid connect'],
            'CRYPTO': ['encryption', 'tls', 'ssl', 'cryptography', 'hashing'],
            'NETWORK_SEC': ['firewall', 'vpn', 'waf', 'ids', 'ips'],
        },
        'GAME_DEV': {
            'ENGINES': ['unreal', 'unity', 'godot', 'cryengine'],
            'GAMEPLAY': ['gameplay', 'physics', 'animation', 'ai'],
            'GRAPHICS': ['opengl', 'directx', 'vulkan', 'shaders'],
        },
        'EMBEDDED': {
            'IOT': ['iot', 'arduino', 'raspberry pi', 'embedded linux'],
            'FIRMWARE': ['firmware', 'rtos', 'bare metal'],
            'DRIVERS': ['device drivers', 'kernel development'],
        },
    },
    'NON_TECHNICAL': {
        'BUSINESS': ['sales', 'negotiation', 'client', 'customer', 'business development', 'account management'],
        'PROJECT_MGMT': ['project management', 'agile', 'scrum', 'kanban', 'waterfall'],
        'ANALYTICS': ['business intelligence', 'power bi', 'tableau', 'data visualization', 'analytics'],
        'OPERATIONS': ['logistics', 'supply chain', 'inventory', 'warehouse', 'forklift'],
        'HEALTHCARE': ['patient care', 'nursing', 'medical', 'radiology', 'pharmacy'],
        'EDUCATION': ['teaching', 'tutoring', 'curriculum', 'instructional design'],
        'LANGUAGES': ['english', 'french', 'spanish', 'german', 'translation'],
        'CREATIVE': ['graphic design', 'ui/ux', 'photoshop', 'illustrator', 'figma'],
    },
    'SOFT_SKILLS': {
        'COMMUNICATION': ['communication', 'presentation', 'public speaking', 'writing'],
        'LEADERSHIP': ['leadership', 'mentoring', 'coaching', 'team building'],
        'COLLABORATION': ['teamwork', 'collaboration', 'interpersonal'],
        'PROBLEM_SOLVING': ['problem solving', 'critical thinking', 'analytical'],
        'ADAPTABILITY': ['adaptability', 'flexibility', 'learning agility'],
    }
}


# Flatten the category hierarchy for matching
def flatten_categories(hierarchy, prefix=""):
    flat_categories = {}
    for category, contents in hierarchy.items():
        if isinstance(contents, dict):
            flat_categories.update(flatten_categories(contents, f"{prefix}{category}_"))
        else:
            flat_categories[f"{prefix}{category}"] = contents
    return flat_categories


MAIN_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY['TECHNICAL'])
NON_TECH_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY['NON_TECHNICAL'], "NON_TECH_")
SOFT_SKILL_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY['SOFT_SKILLS'], "SOFT_")

# Combine all categories for easy access
ALL_CATEGORIES = {**MAIN_CATEGORIES, **NON_TECH_CATEGORIES, **SOFT_SKILL_CATEGORIES}

# Enhanced aliases with priority mapping
CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "ts": "typescript", "js": "javascript", "py": "python",
    "postgres": "postgresql", "mssql": "sql server", "ai": "machine learning",
    "ml": "machine learning", "bi": "business intelligence", "aws lambda": "lambda",
    "azure functions": "functions", "gcp cloud functions": "cloud functions",
    "reactjs": "react", "angularjs": "angular", "vuejs": "vue",
    "nodejs": "node", "expressjs": "express", "nest": "nestjs",
    "scikit": "scikit-learn", "tf": "tensorflow", "torch": "pytorch",
    "keras": "tensorflow", "opencv": "computer vision", "nlp": "natural language processing",
    "ci": "ci/cd", "cd": "ci/cd", "cicd": "ci/cd", "devsecops": "security",
    "iam": "identity", "rbac": "identity", "sso": "identity",
}

# Enhanced patterns for experience statements and other non-skill phrases
EXPERIENCE_PATTERNS = [
    r"\d+\+ years?", r"\d+ years?", r"\d+-\d+ years?", r"\d+ to \d+ years?",
    r"years of experience", r"years experience", r"minimum \d+ years?",
    r"at least \d+ years?", r"over \d+ years?", r"more than \d+ years?",
    r"\d+ yrs", r"\d+\+ yrs", r"\d+-\d+ yrs", r"\d+ to \d+ yrs",
    r"yrs of experience", r"yrs experience", r"minimum \d+ yrs",
    r"at least \d+ yrs", r"over \d+ yrs", r"more than \d+ yrs",
]

DISCARD_PHRASES = [
    "years of experience", "bachelor", "master", "degree", "diploma", "license", "licence",
    "required", "experience in", "familiarity with", "equivalent", "preferred", "valid driver",
    "ability to", "knowledge of", "understanding of", "exposure to", "background in", "familiar with",
    "working knowledge of", "proficiency in", "expertise in", "strong knowledge of", "demonstrated ability",
    "minimum", "maximum", "at least", "more than", "less than", "up to", "including but not limited to",
    "etc.", "e.g.", "i.e.", "such as", "for example", "including", "plus", "and/or", "willing to",
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
    skill = re.sub(r'^familiarity with\s*', '', skill)
    skill = re.sub(r'^ability to\s*', '', skill)

    # Remove trailing punctuation
    skill = re.sub(r'[.,;:]$', '', skill)

    # Remove "etc" and similar phrases
    skill = re.sub(r'\setc\.?$', '', skill)
    skill = re.sub(r'\sor similar$', '', skill)
    skill = re.sub(r'\sand more$', '', skill)

    return skill.strip()


def should_discard(skill_name: str) -> bool:
    """Determine if a skill should be discarded based on patterns"""
    # Check for empty or very short skills
    if len(skill_name.strip()) < 2:
        return True

    # Check for experience patterns
    for pattern in EXPERIENCE_PATTERNS:
        if re.search(pattern, skill_name, re.IGNORECASE):
            return True

    # Check for discard phrases
    lower_name = skill_name.lower()
    for phrase in DISCARD_PHRASES:
        if phrase in lower_name:
            return True

    # Check if it's too long to be a skill (probably a sentence)
    if len(skill_name.split()) > 6:
        return True

    return False


def normalize_skill(skill_name: str) -> str:
    """Normalize a skill name for comparison"""
    if not skill_name:
        return ""

    skill = skill_name.lower().strip()

    # Replace common variations with standard forms
    skill = skill.replace(".net", "dotnet").replace("c#", "csharp")
    skill = skill.replace("&", " and ").replace("/", " ").replace("-", " ")
    skill = re.sub(r"[^a-z0-9\s]+", "", skill)  # Remove special chars but keep spaces

    # Apply aliases - check multi-word aliases first
    for alias, standard in sorted(CATEGORY_ALIASES.items(), key=lambda x: -len(x[0].split())):
        alias_pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(alias_pattern, skill):
            skill = re.sub(alias_pattern, standard, skill)

    # Remove extra spaces
    skill = re.sub(r'\s+', ' ', skill).strip()

    return skill


def should_group_together(a: str, b: str) -> bool:
    norm_a, norm_b = normalize_skill(a), normalize_skill(b)

    # Exact match after normalization
    if norm_a == norm_b:
        return True

    # One is contained in the other (with word boundaries)
    if re.search(r'\b' + re.escape(norm_a) + r'\b', norm_b) or re.search(r'\b' + re.escape(norm_b) + r'\b', norm_a):
        return True

    # Same first 4 characters (for abbreviations)
    if norm_a[:4] == norm_b[:4] and len(norm_a) <= 5 and len(norm_b) <= 5:
        return True

    # High similarity ratio for longer phrases
    if len(norm_a) > 6 and len(norm_b) > 6:
        return SequenceMatcher(None, norm_a, norm_b).ratio() >= SIMILARITY_THRESHOLD

    return False


def determine_primary_category(skill_name: str) -> str:
    norm_skill = normalize_skill(skill_name)
    raw_skill = skill_name.lower()

    # First check technical categories with priority to more specific categories
    for category in [
        'ML_AI_MACHINE_LEARNING', 'ML_AI_DEEP_LEARNING', 'ML_AI_NLP', 'ML_AI_COMPUTER_VISION', 'ML_AI_AI_GENERAL',
        'GAME_DEV_ENGINES', 'GAME_DEV_GAMEPLAY', 'GAME_DEV_GRAPHICS',
        'DATA_DATA_SCIENCE', 'DATA_BIG_DATA', 'DATA_DATA_ENGINEERING', 'DATA_DATABASE_SQL', 'DATA_DATABASE_NOSQL',
        'CLOUD_AWS', 'CLOUD_AZURE', 'CLOUD_GCP', 'CLOUD_CLOUD_GENERAL',
        'SECURITY_APP_SECURITY', 'SECURITY_IDENTITY', 'SECURITY_CRYPTO', 'SECURITY_NETWORK_SEC',
        'DEVOPS_CI_CD', 'DEVOPS_INFRA_AS_CODE', 'DEVOPS_MONITORING', 'DEVOPS_VERSION_CONTROL',
        'TESTING_UNIT_TESTING', 'TESTING_E2E_TESTING', 'TESTING_PERFORMANCE', 'TESTING_TEST_AUTOMATION',
        'FRONTEND_FRAMEWORKS', 'FRONTEND_STYLING', 'FRONTEND_BUILD_TOOLS', 'FRONTEND_WEB_COMPONENTS',
        'BACKEND_APIS', 'BACKEND_SERVER', 'BACKEND_AUTH', 'BACKEND_MESSAGING',
        'PROGRAMMING_NET', 'PROGRAMMING_JAVA_ECOSYSTEM', 'PROGRAMMING_PYTHON_ECOSYSTEM',
        'PROGRAMMING_JAVASCRIPT_TYPESCRIPT', 'PROGRAMMING_GO', 'PROGRAMMING_RUST',
        'PROGRAMMING_RUBY', 'PROGRAMMING_PHP', 'PROGRAMMING_C_CPP', 'PROGRAMMING_MOBILE',
        'EMBEDDED_IOT', 'EMBEDDED_FIRMWARE', 'EMBEDDED_DRIVERS',
    ]:
        for kw in MAIN_CATEGORIES.get(category, []):
            if re.search(r'\b' + re.escape(kw) + r'\b', norm_skill):
                return category

    # Then check non-technical categories
    for category, keywords in NON_TECH_CATEGORIES.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', raw_skill):
                return category

    # Check for soft skills
    for category, keywords in SOFT_SKILL_CATEGORIES.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', raw_skill):
                return category

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

    # Post-processing to merge small categories
    merged_groups = {}
    small_categories = set()

    # First pass: identify small categories
    for category, skills in final_groups.items():
        if len(skills) < MIN_GROUP_SIZE:
            small_categories.add(category)

    # Second pass: merge small categories into parent categories
    for category, skills in final_groups.items():
        if category in small_categories:
            # Find parent category by removing the last part after underscore
            parent_category = "_".join(category.split("_")[:-1])
            if parent_category in ALL_CATEGORIES:
                merged_groups.setdefault(parent_category, []).extend(skills)
            else:
                merged_groups.setdefault("GENERAL_TECH", []).extend(skills)
        else:
            merged_groups.setdefault(category, []).extend(skills)

    return {k: sorted(set(v)) for k, v in merged_groups.items()}


def save_results(output_file: str, results: Dict[str, List[str]]) -> None:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def save_categories_summary(groups: Dict[str, List[str]], output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
        # Sort categories by hierarchy
        sorted_categories = sorted(groups.items(), key=lambda x: (
            not x[0].startswith('TECHNICAL_'),
            not x[0].startswith('NON_TECH_'),
            not x[0].startswith('SOFT_'),
            x[0]
        ))

        for category, skills in sorted_categories:
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
    logger.info(f"Created {len(initial_groups)} initial groups")

    # Consolidate small groups into categories
    consolidated = consolidate_groups(initial_groups)
    logger.info(f"Consolidated into {len(consolidated)} groups")

    # Final filtering and reclassification
    final_groups = filter_and_reclassify_groups(consolidated)
    logger.info(f"Final categories: {len(final_groups)}")

    # Save results
    save_results(output_file, final_groups)
    save_categories_summary(final_groups, summary_file)

    logger.info("=== Script completed successfully ===")


if __name__ == "__main__":
    main()