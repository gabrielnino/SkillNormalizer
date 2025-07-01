import re
import json
import sys
from difflib import SequenceMatcher
from collections import defaultdict

# Configuration
MIN_GROUP_SIZE = 5  # Minimum skills per category
SIMILARITY_THRESHOLD = 0.8  # Text similarity threshold

# Main categories and their keywords
MAIN_CATEGORIES = {
    '.NET': ['c#', 'dotnet', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entity framework'],
    'CLOUD_AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb'],
    'CLOUD_AZURE': ['azure', 'functions', 'entra', 'sql database'],
    'CLOUD_GCP': ['gcp', 'google cloud'],
    'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'mssql'],
    'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb'],
    'FRONTEND': ['react', 'angular', 'vue', 'javascript', 'typescript'],
    'BACKEND': ['node', 'python', 'java', 'spring', 'ruby', 'php'],
    'DEVOPS': ['docker', 'kubernetes', 'terraform', 'ci/cd', 'jenkins'],
    'TESTING': ['test', 'tdd', 'qa', 'junit', 'selenium'],
    'NETWORKING': ['tcp/ip', 'dns', 'dhcp', 'network', 'wccp'],
    'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance']
}

# Non-technical categories
NON_TECH_CATEGORIES = {
    'BUSINESS': ['sales', 'negotiation', 'client', 'customer'],
    'OPERATIONS': ['warehouse', 'forklift', 'logistics'],
    'HEALTHCARE': ['patient', 'radiology', 'nursing', 'medical'],
    'EDUCATION': ['teaching', 'tutoring', 'curriculum']
}


def normalize_skill(skill_name):
    """Enhanced skill name normalization with more specific replacements"""
    if isinstance(skill_name, dict):
        skill_name = skill_name.get('Name', '')

    skill = str(skill_name).lower().strip()

    # Common replacements with more specific rules
    replacements = {
        r'\.net': 'dotnet',
        r'asp\.net': 'aspdotnet',
        r'\bc#\b': 'csharp',
        r'\bc\+\+\b': 'cpp',
        r'react\.?js\b': 'react',
        r'angular\.?js\b': 'angular',
        r'node\.?js\b': 'node',
        r'typescript': 'javascript',
        r'mssql|sql server': 'sqlserver',
        r'postgresql': 'postgres',
        r'nosql': 'mongodb',
        r'rest\s?api': 'api',
        r'web\s?api': 'api',
        r'aws\s.*': 'aws',  # Normalize all AWS services
        r'azure\s.*': 'azure'  # Normalize all Azure services
    }

    for pattern, replacement in replacements.items():
        skill = re.sub(pattern, replacement, skill)

    # Remove non-alphanumeric and normalize spaces
    skill = re.sub(r'[^a-z0-9]', ' ', skill)
    skill = re.sub(r'\s+', ' ', skill).strip()

    # Remove common stop words
    stop_words = {'development', 'programming', 'framework', 'language',
                  'experience', 'knowledge', 'using', 'with', 'and', 'or', 'skills'}
    words = [word for word in skill.split() if word not in stop_words and len(word) > 2]

    return ' '.join(words)


def is_technical(skill):
    """Determine if a skill is technical"""
    non_tech_keywords = {'sales', 'customer', 'teaching', 'medical', 'warehouse'}
    return not any(keyword in skill for keyword in non_tech_keywords)


def should_group_together(a, b):
    """Improved similarity detection with strict category checks"""
    a_norm = normalize_skill(a)
    b_norm = normalize_skill(b)

    # Direct containment
    if a_norm in b_norm or b_norm in a_norm:
        return True

    # Same root (first 4 letters)
    if len(a_norm) >= 4 and len(b_norm) >= 4 and a_norm[:4] == b_norm[:4]:
        return True

    # Similarity threshold
    return SequenceMatcher(None, a_norm, b_norm).ratio() > SIMILARITY_THRESHOLD


def extract_skills(jobs_data):
    """Extract unique skills from job data with validation"""
    unique_skills = set()
    for job in jobs_data:
        if 'KeySkillsRequired' in job and isinstance(job['KeySkillsRequired'], list):
            for skill in job['KeySkillsRequired']:
                if 'Name' in skill and skill['Name'].strip():
                    skill_name = skill['Name'].strip()
                    # Basic validation
                    if len(skill_name) >= 2 and not skill_name.isnumeric():
                        unique_skills.add(skill_name)
    return sorted(unique_skills)


def create_initial_groups(skills):
    """Create initial skill groups with category awareness"""
    groups = []
    used_skills = set()

    # Sort by length (longest first) to catch specific terms before general ones
    for skill in sorted(skills, key=len, reverse=True):
        if skill in used_skills:
            continue

        # Find matching group with category awareness
        matched_group = None
        for group in groups:
            if should_group_together(skill, group['representative']):
                # Additional check to prevent mixing categories
                current_cat = determine_primary_category(skill)
                group_cat = determine_primary_category(group['representative'])
                if current_cat == group_cat or current_cat.startswith('OTHER'):
                    matched_group = group
                    break

        if matched_group:
            matched_group['originals'].append(skill)
        else:
            # Create new group with preliminary category
            groups.append({
                'category': determine_primary_category(skill),
                'representative': skill,
                'originals': [skill]
            })
        used_skills.add(skill)

    return groups


def determine_primary_category(skill_name):
    """Determine the most specific category for a skill"""
    skill = normalize_skill(skill_name)

    # First check non-tech categories
    for category, terms in NON_TECH_CATEGORIES.items():
        if any(term in skill for term in terms):
            return category

    # Then check main categories
    for category, terms in MAIN_CATEGORIES.items():
        if any(term in skill for term in terms):
            return category

    return 'OTHER_TECH' if is_technical(skill) else 'OTHER_NON_TECH'


def consolidate_groups(groups):
    """Consolidate groups into final categories"""
    consolidated = defaultdict(lambda: {'representative': None, 'originals': []})

    for group in groups:
        category = group['category']

        # For small groups, try to merge them
        if len(group['originals']) < MIN_GROUP_SIZE:
            found = False
            for main_cat in consolidated:
                if should_group_together(group['representative'], consolidated[main_cat]['representative']):
                    consolidated[main_cat]['originals'].extend(group['originals'])
                    found = True
                    break
            if not found:
                category = 'OTHER_' + category.split('_')[-1]

        # Update consolidated group
        if consolidated[category]['representative'] is None or \
                len(group['originals']) > len(consolidated[category]['originals']):
            consolidated[category]['representative'] = group['representative']

        consolidated[category]['originals'].extend(group['originals'])

    # Convert to list format and clean duplicates
    final_groups = []
    for category, data in consolidated.items():
        unique_skills = list(set(data['originals']))  # Remove duplicates
        final_groups.append({
            'category': category,
            'representative': data['representative'],
            'originals': sorted(unique_skills)
        })

    # Sort by category then by group size
    final_groups.sort(key=lambda x: (x['category'], -len(x['originals'])))
    return final_groups


def post_process_categories(groups):
    """Final cleanup and validation of categories"""
    # Move clearly misfiled items
    for group in groups:
        if group['category'] == 'CLOUD_AWS':
            group['originals'] = [s for s in group['originals']
                                  if 'aws' in normalize_skill(s)]

    # Merge very similar categories
    merged_groups = []
    skip_indices = set()

    for i, group in enumerate(groups):
        if i in skip_indices:
            continue

        for j in range(i + 1, len(groups)):
            if j in skip_indices:
                continue

            if should_group_together(group['representative'], groups[j]['representative']):
                group['originals'].extend(groups[j]['originals'])
                skip_indices.add(j)

        merged_groups.append(group)

    return merged_groups


def process_jobs_data(jobs_data):
    """Main processing pipeline"""
    print("Extracting skills from jobs data...")
    skills = extract_skills(jobs_data)
    print(f"Found {len(skills)} unique skills after filtering")

    print("Creating initial groups...")
    groups = create_initial_groups(skills)
    print(f"Created {len(groups)} initial groups")

    print("Consolidating groups...")
    consolidated = consolidate_groups(groups)

    print("Post-processing categories...")
    final_groups = post_process_categories(consolidated)
    final_groups.sort(key=lambda x: -len(x['originals']))

    print(f"Final category count: {len(final_groups)}")
    return final_groups


def main():
    if len(sys.argv) < 3:
        print("Usage: python skill_normalizer.py <input_file.json> <output_file.json>")
        sys.exit(1)

    try:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)

        result = process_jobs_data(jobs_data)

        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Results saved to {sys.argv[2]}")
        print("\nCategory Summary:")
        for group in result:
            print(f"{group['category']}: {len(group['originals'])} skills")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()