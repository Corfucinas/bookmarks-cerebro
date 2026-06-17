"""Keyword rules: Career, Hardware, Productivity, Life, Learning, Reference categories.

Pure data table — subset of KEYWORD_RULES. Combined by `classifier_rules.py`
into the full KEYWORD_RULES list.
"""

from __future__ import annotations

KEYWORD_RULES_HARDWARE_LIFE: list[tuple[list[str], list[str], float]] = [
    (
        ["freelance", "upwork", "fiverr", "contract", "client", "consulting"],
        ["Career", "Freelancing"],
        0.80,
    ),
    (
        ["startup", "business", "marketing", "seo", "growth", "product", "pitch"],
        ["Career", "Startups"],
        0.75,
    ),
    (
        ["leadership", "management", "delegate", "hiring", "1:1", "team"],
        ["Career", "Leadership"],
        0.75,
    ),
    (
        ["arduino", "esp32", "stm32", "avr", "pic", "firmware"],
        ["Hardware", "Microcontrollers"],
        0.85,
    ),
    (
        ["raspberry pi", "jetson", "coral", "embedded linux"],
        ["Hardware", "SBC"],
        0.85,
    ),
    (
        ["pcb", "circuit", "component", "solder", "oscilloscope", "multimeter"],
        ["Hardware", "Electronics"],
        0.80,
    ),
    (
        ["iot", "mqtt", "lora", "sensor", "smart home", "zigbee"],
        ["Hardware", "IoT"],
        0.85,
    ),
    (
        ["robotics", "ros", "actuator", "kinematics", "slam", "gazebo"],
        ["Hardware", "Robotics"],
        0.85,
    ),
    (
        ["3d print", "cnc", "laser cut", "fabrication", "maker"],
        ["Hardware", "Fabrication"],
        0.80,
    ),
    (
        ["obsidian", "zettelkasten", "pkm", "note-taking", "second brain"],
        ["Productivity", "PKM"],
        0.80,
    ),
    (
        ["vim", "neovim", "emacs", "vscode", "ide", "editor"],
        ["Productivity", "Editors"],
        0.80,
    ),
    (
        ["tmux", "zsh", "fish", "terminal", "shell", "cli", "dotfiles"],
        ["Productivity", "Terminal"],
        0.80,
    ),
    (
        ["script", "bot", "n8n", "make", "zapier", "cron", "workflow automation"],
        ["Productivity", "Automation"],
        0.75,
    ),
    (
        ["self-host", "homelab", "nas", "proxmox", "nextcloud", "pi-hole"],
        ["Productivity", "Self-Hosting"],
        0.85,
    ),
    (
        ["rss", "newsletter", "read-later", "pocket", "instapaper", "annotation"],
        ["Productivity", "Reading"],
        0.75,
    ),
    (
        ["guitar", "tab", "chord", "song", "sheet music"],
        ["Life", "Hobbies"],
        0.80,
    ),
    (
        ["game", "gaming", "steam", "speedrun", "mod", "esports"],
        ["Entertainment", "Games"],
        0.80,
    ),
    (
        ["movie", "tv", "anime", "documentary", "netflix", "streaming"],
        ["Entertainment", "Streaming"],
        0.75,
    ),
    (
        ["travel", "destination", "hotel", "flight", "trip", "vacation", "hiking"],
        ["Life", "Travel"],
        0.80,
    ),
    (
        ["recipe", "cooking", "food", "restaurant", "cuisine", "baking"],
        ["Life", "Food"],
        0.80,
    ),
    (
        ["fitness", "workout", "gym", "nutrition", "health", "diet", "sleep"],
        ["Life", "Health"],
        0.80,
    ),
    (
        ["paper", "arxiv", "journal", "academic", "scientific", "publication", "conference"],
        ["Learning", "Papers"],
        0.85,
    ),
    (
        ["course", "tutorial", "learn", "mooc", "class", "lesson", "bootcamp", "udemy"],
        ["Learning", "Courses"],
        0.75,
    ),
    (
        ["book", "novel", "literature", "reading", "author", "goodreads"],
        ["Learning", "Books"],
        0.75,
    ),
    (
        ["cheatsheet", "reference", "docs", "documentation", "manual", "guide", "wiki"],
        ["Learning", "Documentation"],
        0.75,
    ),
    (
        ["wikipedia", "encyclopedia"],
        ["Reference", "Wikipedia"],
        0.90,
    ),
    (
        ["osint", "intelligence", "reconnaissance", "investigation", "shodan", "maltego"],
        ["Security", "OSINT"],
        0.85,
    ),
    (
        ["network", "protocol", "tcp/ip", "http", "dns", "firewall", "router", "bgp", "cdn"],
        ["Systems", "Networking"],
        0.80,
    ),
    (
        ["compliance", "soc2", "iso27001", "gdpr", "hipaa", "audit", "pci"],
        ["Security", "Compliance"],
        0.80,
    ),
]
