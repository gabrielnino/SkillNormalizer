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
    'CLOUD': ['aws', 'azure', 'gcp', 'lambda', 's3', 'cloud', 'devops'],
    'DATABASE': ['sql', 'oracle', 'mysql', 'postgres', 'mongodb', 'database', 'nosql'],
    'FRONTEND': ['react', 'angular', 'vue', 'javascript', 'typescript', 'html', 'css'],
    'BACKEND': ['node', 'python', 'java', 'spring', 'ruby', 'php'],
    'DEVOPS': ['docker', 'kubernetes', 'terraform', 'ci/cd', 'jenkins', 'ansible'],
    'TESTING': ['test', 'tdd', 'qa', 'junit', 'selenium']
}


def normalize_skill(skill_name):
    """Enhanced skill name normalization"""
    if isinstance(skill_name, dict):
        skill_name = skill_name.get('Name', '')

    skill = str(skill_name).lower().strip()

    # Common replacements
    replacements = {
        '.net': 'dotnet',
        'asp.net': 'aspdotnet',
        'c#': 'csharp',
        'c++': 'cpp',
        'react.js': 'react',
        'angular.js': 'angular',
        'node.js': 'node',
        'typescript': 'javascript',
        'mssql': 'sql',
        'postgresql': 'postgres',
        'nosql': 'mongodb',
        'restapi': 'api',
        'webapi': 'api'
    }

    for term, replacement in replacements.items():
        skill = skill.replace(term, replacement)

    # Remove non-alphanumeric
    skill = re.sub(r'[^a-z0-9]', ' ', skill)

    # Remove common stop words
    stop_words = {'development', 'programming', 'framework', 'language',
                  'experience', 'knowledge', 'using', 'with', 'and', 'or'}
    words = [word for word in skill.split() if word not in stop_words]

    return ' '.join(words)


def should_group_together(a, b):
    """Improved similarity detection"""
    a_norm = normalize_skill(a)
    b_norm = normalize_skill(b)

    # Direct containment
    if a_norm in b_norm or b_norm in a_norm:
        return True

    # Same root (first 4 letters)
    if a_norm[:4] == b_norm[:4]:
        return True

    # Similarity threshold
    return SequenceMatcher(None, a_norm, b_norm).ratio() > SIMILARITY_THRESHOLD


def extract_skills(jobs_data):
    """Extract unique skills from job data"""
    unique_skills = set()
    for job in jobs_data:
        if 'KeySkillsRequired' in job and isinstance(job['KeySkillsRequired'], list):
            for skill in job['KeySkillsRequired']:
                if 'Name' in skill and skill['Name'].strip():
                    unique_skills.add(skill['Name'].strip())
    return sorted(unique_skills)


def create_initial_groups(skills):
    """Create initial skill groups"""
    groups = []
    used_skills = set()

    for skill in sorted(skills, key=len, reverse=True):
        if skill in used_skills:
            continue

        # Find matching group
        matched_group = None
        for group in groups:
            if should_group_together(skill, group['representative']):
                matched_group = group
                break

        if matched_group:
            matched_group['originals'].append(skill)
        else:
            # Create new group
            groups.append({
                'category': 'TEMP',
                'representative': skill,
                'originals': [skill]
            })
        used_skills.add(skill)

    return groups


def assign_categories(groups):
    """Assign proper categories to groups"""
    for group in groups:
        norm_rep = normalize_skill(group['representative'])
        category = 'OTHER'

        for main_cat, keywords in MAIN_CATEGORIES.items():
            if any(keyword in norm_rep for keyword in keywords):
                category = main_cat
                break

        group['category'] = category

    return groups


def consolidate_groups(groups):
    """Consolidate groups into main categories"""
    consolidated = defaultdict(lambda: {'representative': None, 'originals': []})

    for group in groups:
        category = group['category']
        if category not in MAIN_CATEGORIES and len(group['originals']) < MIN_GROUP_SIZE:
            category = 'OTHER'

        if consolidated[category]['representative'] is None or \
                len(group['originals']) > len(consolidated[category]['originals']):
            consolidated[category]['representative'] = group['representative']

        consolidated[category]['originals'].extend(group['originals'])

    # Convert to list format
    return [{'category': k, 'representative': v['representative'], 'originals': v['originals']}
            for k, v in consolidated.items()]


def process_jobs_data(jobs_data):
    """Main processing pipeline"""
    print("Extracting skills from jobs data...")
    skills = extract_skills(jobs_data)
    print(f"Found {len(skills)} unique skills")

    print("Creating initial groups...")
    groups = create_initial_groups(skills)
    print(f"Created {len(groups)} initial groups")

    print("Assigning categories...")
    categorized = assign_categories(groups)

    print("Consolidating groups...")
    final_groups = consolidate_groups(categorized)
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

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()