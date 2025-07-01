import re
import json
import sys
import pandas as pd
from difflib import SequenceMatcher

def normalize_text(text):
    """Lowercase and remove special characters for comparison"""
    return re.sub(r'[^a-z0-9\s]', '', text.lower().strip())

def are_similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a, b).ratio() >= threshold

def load_skills_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def group_skills(skills):
    groups = []
    used = set()

    for i, skill in enumerate(skills):
        if skill in used:
            continue
        group = [skill]
        normalized_i = normalize_text(skill)
        used.add(skill)
        for j in range(i + 1, len(skills)):
            if skills[j] in used:
                continue
            normalized_j = normalize_text(skills[j])
            if are_similar(normalized_i, normalized_j):
                group.append(skills[j])
                used.add(skills[j])
        groups.append(group)

    grouped_skills = []
    for group in groups:
        grouped_skills.append({
            "category": normalize_text(group[0]).split()[0].upper(),
            "representative": group[0],
            "originals": group
        })

    return grouped_skills

def main():
    if len(sys.argv) < 3:
        print("Usage: python SkillNormalizer.py <skills_file.json> <output_file.json>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    skills = load_skills_from_file(input_path)
    grouped = group_skills(skills)

    # Save output to JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(grouped, f, indent=2)

    print(f"Normalized skills saved to {output_path}")

if __name__ == "__main__":
    main()
