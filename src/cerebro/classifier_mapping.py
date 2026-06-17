"""Raw browser folder path → taxonomy category mapping.

When domain rules, keyword rules, and ML fallback all fail to categorize a
bookmark, we fall back to a hint from the original browser folder structure.
The mapping table below translates known folder name fragments into
taxonomy category paths.

This module owns the mapping table and the normalization function; the
orchestration that invokes it lives in `classifier_core.py`.
"""

from __future__ import annotations

# Mapping of raw folder path fragment → taxonomy category breadcrumbs.
# Matched via case-insensitive substring containment.
RAW_FOLDER_MAPPINGS: dict[str, list[str]] = {
    "coding/python": ["Programming", "Languages"],
    "coding/rust": ["Programming", "Languages"],
    "coding/java": ["Programming", "Languages"],
    "coding/javascript": ["Programming", "Languages"],
    "coding/typescript": ["Programming", "Languages"],
    "coding/sql": ["Data", "Databases"],
    "coding/yaml": ["Programming", "DevEx"],
    "coding/frontend": ["Web", "Frontend"],
    "coding/mobile": ["Web", "Mobile"],
    "coding/dev tools": ["Programming", "DevEx"],
    "coding/github": ["Programming", "DevEx"],
    "coding/linux": ["Systems", "Linux"],
    "coding/linux/security": ["Security", "Blue-Team"],
    "coding/cryptography": ["Security", "Cryptography"],
    "coding/best practices": ["Programming", "Patterns"],
    "coding/machine learning": ["AI", "Deep-Learning"],
    "quantitative trading": ["Quant", "Strategies"],
    "cryptocurrency": ["Blockchain", "DeFi"],
    "hacking": ["Security", "Red-Team"],
    "steganography": ["Security", "Cryptography"],
    "osint": ["Security", "OSINT"],
    "guitar": ["Life", "Hobbies"],
    "study": ["Learning", "Courses"],
    "personal": ["Life", "Relationships"],
    "travel": ["Life", "Travel"],
    "games": ["Entertainment", "Games"],
    "bodybuilding": ["Life", "Health"],
    "plants": ["Life", "Hobbies"],
    "docker": ["Systems", "Containers"],
    "kubernetes": ["Systems", "Containers"],
    "microservices": ["Systems", "Containers"],
    "nginx": ["Systems", "Networking"],
    "cloud architecture": ["Systems", "Cloud"],
    "api": ["Web", "APIs"],
    "http": ["Web", "Web-Standards"],
    "asyncio": ["Programming", "Paradigms"],
    "webscrapping": ["Programming", "DevEx"],
    "interview": ["Career", "Interview"],
    "barclays": ["Quant", "Execution"],
    "banking": ["Quant", "Execution"],
    "consultant": ["Career", "Startups"],
    "freelancing": ["Career", "Freelancing"],
    "gentoo": ["Systems", "Linux"],
    "arch": ["Systems", "Linux"],
    "vim": ["Productivity", "Editors"],
    "tmux": ["Productivity", "Terminal"],
    "vscode": ["Programming", "DevEx"],
    "monitoring": ["Systems", "Observability"],
    "tracing": ["Systems", "Observability"],
    "analytics": ["Data", "Analytics"],
    "indicators": ["Quant", "Strategies"],
    "strategies": ["Quant", "Strategies"],
    "flash loans eth": ["Blockchain", "DeFi"],
    "dex": ["Blockchain", "DeFi"],
    "solidity": ["Blockchain", "Ethereum"],
    "arduino": ["Hardware", "Microcontrollers"],
    "microcontroller": ["Hardware", "Microcontrollers"],
    "opencv": ["AI", "Computer-Vision"],
    "react": ["Web", "Frontend"],
    "wikipedia": ["Reference", "Wikipedia"],
    "documentation": ["Learning", "Documentation"],
    "obsidian": ["Productivity", "PKM"],
    "fastapi": ["Web", "Backend"],
    "django": ["Web", "Backend"],
    "pandas": ["Data", "Data-Science"],
    "cython": ["Programming", "Languages"],
    "pysqlite": ["Data", "Databases"],
    "regexp": ["Programming", "Patterns"],
    "linting": ["Programming", "DevEx"],
    "pytest": ["Programming", "Testing"],
    "openai": ["AI", "LLMs"],
    "langchain": ["AI", "Tools"],
    "chemistry": ["Learning", "Science"],
    "mathematics": ["Learning", "Math"],
    "stadistics": ["Learning", "Math"],
    "harvard": ["Learning", "Courses"],
    "oxford": ["Learning", "Courses"],
    "memorization": ["Learning", "Tutorials"],
    "viewfin": ["Quant", "Research"],
    "raspberry pi": ["Hardware", "SBC"],
    "betterment": ["Life", "Personal-Finance"],
    "absolute array": ["Reference", "Utilities"],
    "other": ["Reference", "Utilities"],
}


def map_raw_folder(raw_path: str) -> list[str] | None:
    """Map old folder paths to new taxonomy.

    Performs case-insensitive substring matching against RAW_FOLDER_MAPPINGS.
    Returns the first matching category breadcrumbs, or None if no match.
    """
    raw_lower = raw_path.lower()
    for pattern, breadcrumbs in RAW_FOLDER_MAPPINGS.items():
        if pattern in raw_lower:
            return breadcrumbs
    return None
