
import re
import json
import sys
from difflib import SequenceMatcher
from collections import defaultdict

# Configuration
MIN_GROUP_SIZE = 5
SIMILARITY_THRESHOLD = 0.8

# Main categories and keywords
MAIN_CATEGORIES = {
    '.NET': ['c#', 'dotnet', 'aspdotnet', 'vbnet', 'wpf', 'winforms', 'entity framework'],
    'CLOUD_AWS': ['aws', 'lambda', 's3', 'cloudfront', 'dynamodb'],
    'CLOUD_AZURE': ['azure', 'functions', 'entra', 'sql database'],
    'CLOUD_GCP': ['gcp', 'google cloud'],
    'DATABASE_SQL': ['sql', 'oracle', 'mysql', 'postgres', 'mssql'],
    'DATABASE_NOSQL': ['mongodb', 'cassandra', 'cosmosdb'],
    'FRONTEND': ['react', 'angular', 'vue', 'javascript', 'typescript', 'html', 'css'],
    'BACKEND': ['node', 'python', 'java', 'spring', 'ruby', 'php'],
    'DEVOPS': ['docker', 'kubernetes', 'terraform', 'ci/cd', 'jenkins', 'git'],
    'TESTING': ['test', 'tdd', 'qa', 'junit', 'selenium'],
    'NETWORKING': ['tcp/ip', 'dns', 'dhcp', 'network', 'wccp'],
    'DATA_ENGINEERING': ['etl', 'data pipeline', 'data modeling', 'data governance']
}

NON_TECH_CATEGORIES = {
    'BUSINESS': ['sales', 'negotiation', 'client', 'customer'],
    'OPERATIONS': ['warehouse', 'forklift', 'logistics'],
    'HEALTHCARE': ['patient', 'radiology', 'nursing', 'medical'],
    'EDUCATION': ['teaching', 'tutoring', 'curriculum']
}

def normalize_skill(skill_name):
    skill = str(skill_name).lower().strip()
    replacements = {
        r'\.net': 'dotnet', r'asp\.net': 'aspdotnet', r'\bc#\b': 'csharp',
        r'\bc\+\+\b': 'cpp', r'react\.?js\b': 'react', r'angular\.?js\b': 'angular',
        r'node\.?js\b': 'node', r'typescript': 'javascript',
        r'mssql|sql server': 'sqlserver', r'postgresql': 'postgres',
        r'nosql': 'mongodb', r'rest\s?api': 'api', r'web\s?api': 'api',
        r'aws\s.*': 'aws', r'azure\s.*': 'azure'
    }
    for pattern, replacement in replacements.items():
        skill = re.sub(pattern, replacement, skill)
    skill = re.sub(r'[^a-z0-9]', ' ', skill)
    skill = re.sub(r'\s+', ' ', skill).strip()
    stop_words = {'development', 'programming', 'framework', 'language',
                  'experience', 'knowledge', 'using', 'with', 'and', 'or', 'skills'}
    words = [word for word in skill.split() if word not in stop_words and len(word) > 2]
    return ' '.join(words)

def is_technical(skill):
    non_tech_keywords = {'sales', 'customer', 'teaching', 'medical', 'warehouse'}
    return not any(keyword in skill for keyword in non_tech_keywords)

def should_group_together(a, b):
    a_norm = normalize_skill(a)
    b_norm = normalize_skill(b)
    if a_norm in b_norm or b_norm in a_norm:
        return True
    if len(a_norm) >= 4 and len(b_norm) >= 4 and a_norm[:4] == b_norm[:4]:
        return True
    return SequenceMatcher(None, a_norm, b_norm).ratio() > SIMILARITY_THRESHOLD

def determine_primary_category(skill_name):
    skill = normalize_skill(skill_name)
    for category, terms in NON_TECH_CATEGORIES.items():
        if any(term in skill for term in terms):
            return category
    for category, terms in MAIN_CATEGORIES.items():
        if any(term in skill for term in terms):
            return category
    return 'OTHER_TECH' if is_technical(skill) else 'OTHER_NON_TECH'

def create_initial_groups(skills):
    groups = []
    used_skills = set()
    for skill in sorted(skills, key=len, reverse=True):
        if skill in used_skills:
            continue
        matched_group = None
        for group in groups:
            if should_group_together(skill, group['representative']):
                current_cat = determine_primary_category(skill)
                group_cat = determine_primary_category(group['representative'])
                if current_cat == group_cat or current_cat.startswith('OTHER'):
                    matched_group = group
                    break
        if matched_group:
            matched_group['originals'].append(skill)
        else:
            groups.append({
                'category': determine_primary_category(skill),
                'representative': skill,
                'originals': [skill]
            })
        used_skills.add(skill)
    return groups

def consolidate_groups(groups):
    consolidated = defaultdict(lambda: {'representative': None, 'originals': []})
    for group in groups:
        category = group['category']
        if len(group['originals']) < MIN_GROUP_SIZE:
            found = False
            for main_cat in consolidated:
                if should_group_together(group['representative'], consolidated[main_cat]['representative']):
                    consolidated[main_cat]['originals'].extend(group['originals'])
                    found = True
                    break
            if not found:
                category = 'OTHER_' + category.split('_')[-1]
        if consolidated[category]['representative'] is None or len(group['originals']) > len(consolidated[category]['originals']):
            consolidated[category]['representative'] = group['representative']
        consolidated[category]['originals'].extend(group['originals'])
    final_groups = []
    for category, data in consolidated.items():
        unique_skills = list(set(data['originals']))
        final_groups.append({
            'category': category,
            'representative': data['representative'],
            'originals': sorted(unique_skills)
        })
    final_groups.sort(key=lambda x: (x['category'], -len(x['originals'])))
    return final_groups
