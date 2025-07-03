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
            'CONCEPTS': ['algorithms', 'data structures', 'design patterns', 'oop',
                         'object-oriented', 'solid principles', 'object oriented programming',
                         'object-oriented programming', 'object-oriented design']
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
            'CLOUD_GENERAL': ['kubernetes', 'docker', 'serverless', 'paas', 'saas', 'iaas', 'cloud computing'],
        },
        'DEVOPS': {
            'CI_CD': ['ci/cd', 'jenkins', 'github actions', 'gitlab ci', 'circleci', 'continuous integration'],
            'INFRA_AS_CODE': ['terraform', 'pulumi', 'cloudformation', 'ansible'],
            'MONITORING': ['grafana', 'prometheus', 'datadog', 'new relic', 'splunk'],
            'VERSION_CONTROL': ['git', 'svn', 'mercurial', 'perforce'],
            'DEVOPS_GENERAL': ['git', 'svn', 'mercurial', 'perforce', 'devops', 'build pipelines', 'infrastructure as code'],
        },
        'TESTING': {
            'UNIT_TESTING': ['junit', 'nunit', 'pytest', 'mocha', 'jest'],
            'E2E_TESTING': ['selenium', 'cypress', 'playwright', 'testcafe'],
            'PERFORMANCE': ['jmeter', 'gatling', 'locust', 'k6'],
            'TEST_AUTOMATION': ['test automation', 'bdd', 'tdd', 'qa automation', 'automated testing'],
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
        'SYSTEM': {
            'DESIGN': ['system design', 'distributed systems', 'microservices',
                       'scalable architectures', 'event-driven architecture'],
            'TOOLS': ['powershell', 'visual studio', 'linux', 'cli', 'cmake'],
            'CONCEPTS': ['operating system', 'networking', 'file systems', 'multi-threaded']
        },
        'GENERAL_TECH': {
            'SOFTWARE_DEVELOPMENT': [
                'ability to refactor complex, monolithic systems',
                'developed high-quality, testable software',
                'solid background in data processing',
                'performance and memory optimization techniques',
                'performance optimization',
                'strong development background',
                'high-performance, memory efficient, multithreaded code',
                'high-performance, memory-efficient, multithreaded code',
                'multi-threaded software',
                'multithreaded code',
                'object-oriented design',
                'object-oriented design concepts',
                'object-oriented languages',
                'object-relational mapping',
                'oo design',
                'code quality and standards adherence',
                'code reviews',
                'coding standards and code reviews',
                'debugging',
                'debugging and optimization',
                'debugging and performance optimization',
                'debugging memory corruptions',
                'debugging tools',
                'algorithm optimization',
                'experience across the entire development lifecycle',
                'full software development life cycle experience',
                'use of software development tools',
                'well-designed code and solid programming skills'
            ],
            'WEB_DEVELOPMENT': [
                'back-end development',
                'back-end development with some front-end experience',
                'background in full stack development',
                'building web applications at scale',
                'experience building web applications',
                'front-end design',
                'front-end frameworks',
                'frontend technologies',
                'full-stack development',
                'full-stack web development',
                'modern frontend frameworks',
                'web application development',
                'web applications',
                'web development',
                'web frameworks',
                'web technologies',
                'html5',
                'html5+',
                'html5/css3',
                'css3+',
                'mvc',
                'ui frameworks',
                'ux design'
            ],
            'DATABASES': [
                'advanced experience in relational databases',
                'data capture',
                'data deduplication',
                'data storage',
                'database design and query optimization',
                'database development',
                'database management',
                'database optimization',
                'database optimization experience',
                'database software',
                'document databases',
                'experience working with databases',
                'experience working with relational databases',
                'has executed large scale data migrations',
                'proficiency with database operations and queries',
                'relational databases',
                'strong experience in relational databases',
                'understands large datasets and data mapping'
            ],
            'CLOUD_DEVOPS': [
                'bicep/arm templates',
                'ci/cd',
                'ci/cd methodologies',
                'ci/cd pipelines',
                'ci/cd tools',
                'containers',
                'continuous deployment',
                'designing ci/cd pipelines and build',
                'experience in ci/cd',
                'experience working with containers',
                'familiarity with ci/cd pipeline',
                'familiarity with containerization and orchestration',
                'proficient with ci/cd concepts and tooling',
                'build processes and testing',
                'build processes, testing, and operations experience',
                'build systems',
                'logging and telemetry',
                'monitoring tools',
                'source control',
                'source control management',
                'experience using source control software',
                'version control',
                'high availability systems',
                'high performing transaction systems',
                'scalability',
                'scalable frameworks',
                'system performance',
                'systems design',
                'systems design skills'
            ],
            'TESTING_QA': [
                'automated tests',
                'experience in fast-paced, test-driven, collaborative environments',
                'familiarity with test-driven development',
                'software testing and test-driven development',
                'test driven development',
                'test driven development techniques',
                'test framework design',
                'test framework design and development',
                'test frameworks',
                'test-driven development',
                'testing',
                'testing and debugging applications',
                'unit and integration testing',
                'unit testing',
                'unit testing, dependency injection, ci/cd',
                'unit/integration testing'
            ],
            'TOOLS_PLATFORMS': [
                'adobe experience manager',
                'adobe photoshop',
                'autocad/revit',
                'blender',
                'computer-aided design',
                'cad development',
                'copilot studio',
                'dynamics 365 business central/nav',
                'dynamics 365 f&o',
                'dynamics 365 finance & operations',
                'dynamics 365 finance and operations',
                'dynamics 365 sdk',
                'dynamics 365/crm',
                'gis systems',
                'experience using gis systems',
                'google analytics experience',
                'microsoft dataverse',
                'microsoft dynamics 365 ce',
                'next.js',
                'node.js',
                'nodejs',
                'opentext teamsite/livesite',
                'power apps',
                'power automate',
                'power pages',
                'power platform',
                'power platform experience',
                'react.js',
                'react.js/vue.js/angular.js',
                'reactive native technology',
                'salesforce',
                'salesforce data models',
                'sharepoint',
                'sharepoint online development experience',
                'shopify',
                'sketchup',
                'springboot',
                'ssrs',
                'ssrs, ssas, ssis',
                'starlims data model',
                'starlims qm v12',
                'vb.net',
                'vb.net experience',
                'visualforce',
                'vue.js',
                'wordpress',
                'x++',
                'x++ development'
            ],
            'SOFT_SKILLS': [
                'ability to build trusted relationships',
                'ability to coach and mentor',
                'ability to conduct remote sessions',
                'ability to empathize with users',
                'ability to manage multiple projects simultaneously',
                'ability to mentor and collaborate',
                'ability to multi-task',
                'ability to organize and prioritize work',
                'ability to work cross-functionally',
                'accountability',
                'attention to detail',
                'attention to detail and punctual',
                'collaborating with infrastructure team',
                'collaboration',
                'collaboration with cross-functional teams',
                'collaboration with global teams',
                'collaborative and dynamic skills',
                'collaborative and eager to contribute ideas',
                'collaborative and team-oriented',
                'collaborative team environment',
                'collaborative team environment experience',
                'collaborative team player',
                'collaborative teamwork',
                'conflict resolution and consensus building',
                'continuous improvement',
                'continuous learning and adaptability',
                'creativity',
                'critical thinker and problem solver',
                'curious, always learning',
                'demonstrated ability to communicate',
                'eager & willing to learn',
                'energy and passion',
                'english, both written and verbal',
                'enjoy working with diverse groups',
                'entrepreneurial mindset',
                'entrepreneurial spirit',
                'excellent organizational and time management skills',
                'excellent organizational skills',
                'excellent troubleshooting skills',
                'flexible scheduling',
                'growth mindset',
                'growth-oriented perspective',
                'initiative and results-driven',
                'initiative to manage your own workload',
                'influencing and reasoning skills',
                'organized',
                'organized with strong prioritization skills',
                'passion for learning and sharing knowledge',
                'passion for technology and code',
                'problem solver',
                'self-driven',
                'self-motivated and competent to work independently',
                'self-motivated and great organizational skills',
                'self-motivated and independent',
                'self-motivated and passionate about ui systems',
                'self-motivated and works with minimal supervision',
                'self-motivated, responsible, and a fast learner',
                'self-starter and key contributor',
                'smiling and making others smile',
                'strong sense of responsibility',
                'strong written and verbal communicator',
                'strong written and verbal english skills',
                'team player',
                'team work',
                'teamwork',
                'thrive in a collaborative environment',
                'user-focused, passionate, solutions-focused, and innovative',
                'working under pressure'
            ],
            'INDUSTRY_SPECIFIC': [
                '3d metrology',
                'adjustment to manufacturer\'s specifications',
                'ax',
                'big data analytics',
                'business and systems analysis',
                'business statistics',
                'business statistics knowledge',
                'care coordination',
                'care for people and user experience',
                'chemistry',
                'civil engineering',
                'cold calling',
                'cold calling and lead generation',
                'com',
                'comfort with technology',
                'community outreach',
                'demonstrated ability in cpr techniques',
                'demonstrated ability to operate related equipment',
                'demonstrated ndt skill, knowledge or experience',
                'demonstrated success in leading development teams',
                'desktop application development',
                'diagnostic and repair skills',
                'diagnostic radiographic/fluoroscopic procedures',
                'distributed applications',
                'ebpf',
                'emergency care',
                'erp development experience',
                'erp integration',
                'erp integration experience',
                'event marketing',
                'event set up and tear down',
                'expertise in chemistry',
                'expertise in windows development',
                'familiarity of modern cpu/gpu hardware architectures',
                'familiarity with cache stores',
                'familiarity with nginx',
                'familiarity with restful api design principles',
                'familiarity with ui development',
                'firewalls',
                'food preparation',
                'forklift operation',
                'foxpro',
                'game development',
                'game industry experience',
                'gdscript',
                'googletest',
                'grade 12 diploma or equivalent',
                'groovy',
                'hand-eye coordination',
                'high school diploma or ged',
                'high school diploma/ged',
                'identity and access management',
                'inspection and testing of mechanical units',
                'intermediate math skills',
                'kernel-level development',
                'kernel-mode drivers',
                'knowledge and experience applying disa stigs',
                'kql',
                'kvm hypervisor',
                'lead generation',
                'legally able to work in canada',
                'lighting and imaging understanding',
                'linkedin for recruiting',
                'low-level graphics apis',
                'macos/windows development',
                'malware analysis',
                'manual dexterity',
                'map-reduce',
                'marine engineering',
                'mdm frameworks',
                'mechanical aptitude',
                'mechanical knowledge',
                'meeting preparation and consultant engagement',
                'mentor and coach junior team members',
                'metadata-driven definitional development experience',
                'micro-services',
                'minimum of five years industry experience',
                'ndt methods expertise',
                'net development experience',
                'network programming',
                'network programming and kernel-level experience',
                'network protocols',
                'network protocols/socket programming',
                'networked game principles',
                'nursing interventions',
                'oncology nursing',
                'one or more scripting languages',
                'open source development',
                'open source experience and involvement',
                'open source frameworks',
                'operating radiographic and computerized imaging equipment',
                'operating systems concepts',
                'operational excellence',
                'operations experience',
                'patient assessment',
                'patient care and safety monitoring',
                'payments or financial systems experience',
                'payments or risk experience',
                'physical demands compliance',
                'physical stamina',
                'posix apis',
                'previous game design/development experience',
                'private connectivity',
                'process builders',
                'product demonstrations',
                'product knowledge',
                'professional appearance and conduct',
                'proficient with graphics debugging tools',
                'quality and process improvement',
                'radiation protection practices',
                'radiology information system',
                'real-time rendering',
                'recent experience using knockout.js',
                'recruiting',
                'redis',
                'relevant software programs',
                'research support',
                'routers, network switch development',
                'ror',
                'safety compliance',
                'scala',
                'scheduled maintenance',
                'secure coding practices',
                'secure software development',
                'service oriented architecture',
                'service-oriented architecture',
                'shell',
                'sidekiq',
                'soc architecture',
                'software architecture',
                'software system operation',
                'solution design',
                'strategic thinker and deadline-driven',
                'strong business partnership skills',
                'strong grasp of sockets',
                'strong low-level os internals in windows',
                'strong performance analysis',
                'structural engineering',
                'tcp/ip',
                'tcp/udp/ip',
                'technical support for existing applications',
                'threat modelling',
                'three years recent related oncology experience',
                'triggers',
                'unix o/s',
                'using kitchen tools',
                'valid driver\'s licence',
                'valid driver\'s license and insurability',
                'valid passport with no travel restrictions',
                'vnc, remote desktop protocol development',
                'vpc endpoints',
                'web api',
                'web api 2',
                'web services',
                'web services/web apis',
                'websocket',
                'windows api/win32/com',
                'windows internals',
                'windows kernel programming/driver development',
                'windows os development',
                'windows os kernel and driver development',
                'windows server engineering',
                'xml',
                'xslt'
            ],
            'LANGUAGE_LOCALIZATION': [
                'bilingual',
                'bilingualism in french and english',
                'fluency in french',
                'french language proficiency'
            ],
            'API_DEVELOPMENT': [
                'api and service-level validation',
                'api design',
                'api development',
                'apis',
                'event-driven architecture',
                'experience building restful apis',
                'expertise in developing apis',
                'familiarity with restful api design principles',
                'restful api',
                'restful api design',
                'restful api design principles',
                'restful apis',
                'experience in web services',
                'web services',
                'web services/web apis'
            ],
            'NETWORKING': [
                'dns',
                'firewalls',
                'http',
                'http protocol',
                'hypervisor technologies',
                'ip and network connectivity',
                'internet protocols',
                'private connectivity',
                'tcp/ip',
                'tcp/udp/ip',
                'vpc endpoints'
            ],
            'DOCUMENTATION_PORTFOLIO': [
                'a portfolio of past projects',
                'a portfolio of successful projects',
                'balance perfect vs getting it done'
            ]
        }
    },
    'NON_TECHNICAL': {
        'BUSINESS': ['sales', 'negotiation', 'client', 'customer', 'business development', 'account management'],
        'PROJECT_MGMT': ['project management', 'agile', 'scrum', 'kanban', 'waterfall'],
        'ANALYTICS': ['business intelligence', 'power bi', 'tableau', 'data visualization'],
        'OPERATIONS': ['logistics', 'supply chain', 'inventory', 'warehouse'],
        'EDUCATION': {
            'CERTIFICATION': ['degree', 'certification', 'bachelor', 'master', 'education'],
            'TEACHING': ['teaching', 'tutoring', 'mentoring', 'instruction']
        },
        'COMMUNICATION': ['communication', 'presentation', 'writing', 'documentation'],
        'LEADERSHIP': ['leadership', 'team building', 'mentoring', 'coaching'],
        'PROBLEM_SOLVING': ['problem solving', 'critical thinking', 'analytical']
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
NON_TECH_CATEGORIES = flatten_categories(CATEGORY_HIERARCHY['NON_TECHNICAL'])
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
    save_augmented_jobs_with_skills(input_file, final_groups, 'KeySkillsRequired')

    logger.info("=== Script completed successfully ===")


if __name__ == "__main__":
    main()