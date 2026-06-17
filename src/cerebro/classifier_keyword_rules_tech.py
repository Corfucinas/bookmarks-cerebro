"""Keyword rules: AI, Quant, Blockchain, Systems, Security categories.

Pure data table — subset of KEYWORD_RULES. Combined by `classifier_rules.py`
into the full KEYWORD_RULES list.
"""

from __future__ import annotations

KEYWORD_RULES_TECH_SECURITY: list[tuple[list[str], list[str], float]] = [
    (
        [
            "machine learning",
            "deep learning",
            "neural network",
            "model",
            "training",
            "inference",
            "embedding",
            "vector",
        ],
        ["AI", "Deep-Learning"],
        0.85,
    ),
    (
        [
            "transformer",
            "llm",
            "gpt",
            "rag",
            "fine-tune",
            "prompt",
            "openai",
            "anthropic",
            "claude",
        ],
        ["AI", "LLMs"],
        0.90,
    ),
    (
        ["diffusion", "gan", "vae", "image generation", "synthetic", "generative"],
        ["AI", "Generative-AI"],
        0.90,
    ),
    (
        ["pytorch", "tensorflow", "jax", "huggingface", "onnx", "caffe"],
        ["AI", "Tools"],
        0.85,
    ),
    (
        [
            "computer vision",
            "opencv",
            "image recognition",
            "object detection",
            "segmentation",
            "ocr",
        ],
        ["AI", "Computer-Vision"],
        0.90,
    ),
    (
        [
            "reinforcement learning",
            "rl",
            "q-learning",
            "policy gradient",
            "agent",
            "multi-armed bandit",
        ],
        ["AI", "Reinforcement-Learning"],
        0.90,
    ),
    (
        ["nlp", "natural language processing", "sentiment", "ner", "tokenization", "bert"],
        ["AI", "NLP"],
        0.90,
    ),
    (
        ["mlops", "feature store", "model serving", "model monitoring", "experiment tracking"],
        ["AI", "MLOps"],
        0.85,
    ),
    (
        [
            "quantitative",
            "backtest",
            "algorithmic trading",
            "trading strategy",
            "sharpe",
            "alpha",
            "beta",
            "factor",
        ],
        ["Quant", "Strategies"],
        0.90,
    ),
    (
        ["portfolio", "asset allocation", "risk parity", "modern portfolio theory"],
        ["Quant", "Portfolio"],
        0.85,
    ),
    (
        ["derivatives", "options", "futures", "swap", "black-scholes", "greeks"],
        ["Quant", "Derivatives"],
        0.90,
    ),
    (
        ["execution", "market impact", "slippage", "order routing", "twap", "vwap"],
        ["Quant", "Execution"],
        0.85,
    ),
    (
        ["risk", "var", "cvar", "stress test", "drawdown", "scenario analysis"],
        ["Quant", "Risk"],
        0.85,
    ),
    (
        ["ethereum", "solidity", "evm", "ethers", "hardhat", "foundry"],
        ["Blockchain", "Ethereum"],
        0.90,
    ),
    (
        ["bitcoin", "lightning network", "taproot", "btc", "satoshi"],
        ["Blockchain", "Bitcoin"],
        0.90,
    ),
    (
        ["defi", "dex", "amm", "liquidity pool", "yield farming", "flash loan", "lending protocol"],
        ["Blockchain", "DeFi"],
        0.90,
    ),
    (
        ["nft", "erc-721", "erc-1155", "marketplace", "digital collectible"],
        ["Blockchain", "NFTs"],
        0.90,
    ),
    (
        ["dao", "governance", "treasury", "proposal", "snapshot", "token holder"],
        ["Blockchain", "DAOs"],
        0.85,
    ),
    (
        ["smart contract", "tokenomics", "whitepaper", "consensus", "layer 2", "rollup"],
        ["Blockchain", "Infrastructure"],
        0.80,
    ),
    (
        ["docker", "kubernetes", "k8s", "container", "helm", "pod", "microservice"],
        ["Systems", "Containers"],
        0.85,
    ),
    (
        [
            "aws",
            "gcp",
            "azure",
            "serverless",
            "lambda",
            "cloud",
            "s3",
            "ec2",
            "terraform",
            "pulumi",
        ],
        ["Systems", "Cloud"],
        0.85,
    ),
    (
        ["linux", "ubuntu", "debian", "arch", "gentoo", "kernel", "systemd", "bash", "shell"],
        ["Systems", "Linux"],
        0.85,
    ),
    (
        ["cryptography", "encryption", "cipher", "hash", "rsa", "aes", "ecdsa", "zk-snark"],
        ["Security", "Cryptography"],
        0.90,
    ),
    (
        ["tor", "vpn", "privacy", "anonymity", "signal", "pgp"],
        ["Security", "Privacy"],
        0.85,
    ),
    (
        ["pentest", "penetration test", "exploit", "cve", "vulnerability", "metasploit", "burp"],
        ["Security", "Red-Team"],
        0.85,
    ),
    (
        ["appsec", "owasp", "sast", "dast", "dependency scan", "secure coding"],
        ["Security", "AppSec"],
        0.85,
    ),
    (
        ["malware", "reverse engineering", "forensics", "yara", "sandbox"],
        ["Security", "Malware"],
        0.85,
    ),
    (
        ["blue team", "siem", "soar", "incident response", "threat hunting", "defense"],
        ["Security", "Blue-Team"],
        0.85,
    ),
    (
        [
            "css",
            "html",
            "javascript",
            "react",
            "vue",
            "svelte",
            "angular",
            "frontend",
            "ui",
            "ux",
            "responsive",
            "tailwind",
            "bootstrap",
            "sass",
        ],
        ["Web", "Frontend"],
        0.80,
    ),
    (
        [
            "backend",
            "api",
            "rest",
            "graphql",
            "grpc",
            "server",
            "microservice",
            "fastapi",
            "django",
            "flask",
            "nestjs",
        ],
        ["Web", "Backend"],
        0.80,
    ),
]
