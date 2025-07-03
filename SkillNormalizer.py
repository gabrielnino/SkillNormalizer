import json
import logging
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, List
from tqdm import tqdm

# Ensure stdout uses UTF-8
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('skill_normalization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

# Flatten categories

def flatten_categories(hierarchy, prefix=""):
    flat = {}
    for cat, val in hierarchy.items():
        if isinstance(val, dict):
            flat.update(flatten_categories(val, f"{prefix}{cat}_"))
        else:
            flat[f"{prefix}{cat}"] = val
    return flat

MAIN_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY['TECHNICAL'])
ALL_CATEGORIES = {**MAIN_CATEGORIES}

CATEGORY_ALIASES = {
    "aspnet": "dotnet", "dotnetcore": "dotnet", "netcore": "dotnet",
    "c#": "csharp", "asp.net": "aspdotnet",
}

EXPERIENCE_PATTERNS = [r"\d+\+?\s*years?"]
DISCARD_PHRASES = ["years of experience", "experience with"]

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
    for category, keywords in MAIN_CATEGORIES.items():
        if any(re.search(rf'\b{re.escape(kw)}\b', norm_skill) for kw in keywords):
            return category
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

def main(input_file=DEFAULT_INPUT, output_file=DEFAULT_OUTPUT, summary_file=DEFAULT_SUMMARY):
    logger.info("=== Script started ===")
    logger.info(f"Command line arguments: input={input_file}, output={output_file}, summary={summary_file}")

    skills = extract_all_skill_names_from_jobs(input_file)
    initial_groups = create_initial_groups(skills)
    logger.info(f"Created {len(initial_groups)} initial groups")

    consolidated = consolidate_groups(initial_groups)
    logger.info(f"Consolidated into {len(consolidated)} groups")

    final_groups = filter_and_reclassify_groups(consolidated)
    logger.info(f"Final categories: {len(final_groups)}")

    save_results(output_file, final_groups)
    save_categories_summary(final_groups, summary_file)

    logger.info("=== Script completed successfully ===")

if __name__ == "__main__":
    main()
