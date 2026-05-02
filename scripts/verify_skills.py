#!/usr/bin/env python
"""Verify that the web-search and web-scraper skills are properly installed."""

import os
import sys
from pathlib import Path

# Add the openharness source to Python path
project_root = Path(__file__).parent.parent
openharness_src = project_root / "openharness" / "src"
sys.path.insert(0, str(openharness_src))

from openharness.skills.loader import load_skills_from_dirs

def main():
    print("=" * 70)
    print("Verifying Web Search & Web Scraper Skills")
    print("=" * 70)
    print()

    # Check skill directories
    claude_skills_dir = project_root / "openharness" / ".claude" / "skills"
    agents_skills_dir = project_root / "openharness" / ".agents" / "skills"

    skill_names = ["web-search", "web-scraper"]
    all_good = True

    for skill_name in skill_names:
        print(f"Checking '{skill_name}' skill...")

        # Check .claude directory
        claude_path = claude_skills_dir / skill_name / "SKILL.md"
        if claude_path.exists():
            print(f"  ✓ .claude/skills: {claude_path}")
        else:
            print(f"  ✗ .claude/skills: NOT FOUND")
            all_good = False

        # Check .agents directory
        agents_path = agents_skills_dir / skill_name / "SKILL.md"
        if agents_path.exists():
            print(f"  ✓ .agents/skills: {agents_path}")
        else:
            print(f"  ✗ .agents/skills: NOT FOUND")
            all_good = False

        print()

    print("Testing OpenHarness Skill loading...")
    try:
        # Try loading skills from .claude directory
        skills_from_claude = load_skills_from_dirs([claude_skills_dir], source="local")
        found_claude = {s.name for s in skills_from_claude}

        # Try loading skills from .agents directory
        skills_from_agents = load_skills_from_dirs([agents_skills_dir], source="local")
        found_agents = {s.name for s in skills_from_agents}

        print()
        print("Skills loaded from .claude/skills:")
        for skill in skills_from_claude:
            print(f"  • {skill.name}")
            print(f"    {skill.description[:80]}...")

        print()
        print("Skills loaded from .agents/skills:")
        for skill in skills_from_agents:
            print(f"  • {skill.name}")
            print(f"    {skill.description[:80]}...")

        # Check if our skills are there
        for skill_name in skill_names:
            if skill_name in found_claude:
                print(f"\n✓ {skill_name} available in .claude/skills")
            else:
                print(f"\n✗ {skill_name} NOT in .claude/skills")
                all_good = False

            if skill_name in found_agents:
                print(f"✓ {skill_name} available in .agents/skills")
            else:
                print(f"✗ {skill_name} NOT in .agents/skills")
                all_good = False

    except Exception as e:
        print(f"Error loading skills: {e}")
        import traceback
        traceback.print_exc()
        all_good = False

    # Check scraper script
    print()
    print("Checking scraper script...")
    scraper_path = project_root / "scripts" / "advanced_scraper.py"
    if scraper_path.exists():
        print(f"✓ {scraper_path} exists")
    else:
        print(f"✗ {scraper_path} missing")
        all_good = False

    print()
    print("=" * 70)
    if all_good:
        print("✓ All skills installed successfully!")
        print()
        print("You can now use these skills in OpenHarness:")
        print("- 'web-search' for internet searches")
        print("- 'web-scraper' for web scraping and crawling")
    else:
        print("✗ Some issues found - please check above.")
    print("=" * 70)
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
