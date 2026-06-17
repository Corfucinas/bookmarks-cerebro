"""Keyword rules: Web, Design, Programming, Data, Career categories.

Pure data table — subset of KEYWORD_RULES. Combined by `classifier_rules.py`
into the full KEYWORD_RULES list.
"""

from __future__ import annotations

KEYWORD_RULES_WEB_DEV_DATA: list[tuple[list[str], list[str], float]] = [
    (
        ["next.js", "nuxt", "fullstack", "ssr", "ssg", "jamstack"],
        ["Web", "Fullstack"],
        0.80,
    ),
    (
        ["mobile", "ios", "android", "react native", "flutter", "swift", "kotlin"],
        ["Web", "Mobile"],
        0.80,
    ),
    (
        ["browser", "chrome", "firefox", "webkit", "v8", "extension", "pwa"],
        ["Web", "Browsers"],
        0.80,
    ),
    (
        ["figma", "sketch", "design system", "wireframe", "prototype"],
        ["Design", "UI-UX"],
        0.85,
    ),
    (
        ["adobe", "photoshop", "illustrator", "indesign", "creative suite", "graphic"],
        ["Design", "Graphic-Design"],
        0.85,
    ),
    (
        ["blender", "3d model", "render", "unreal", "unity", "cad", "maya"],
        ["Design", "3D"],
        0.85,
    ),
    (
        ["video edit", "premiere", "davinci", "after effects", "color grade", "compositing"],
        ["Design", "Photo-Video"],
        0.85,
    ),
    (
        ["music production", "daw", "ableton", "fl studio", "logic pro", "composition"],
        ["Design", "Music"],
        0.80,
    ),
    (
        ["python", "django", "fastapi", "flask", "pandas", "numpy", "scipy"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["rust", "cargo", "tokio", "actix", "axum", "serde"],
        ["Programming", "Languages"],
        0.85,
    ),
    (
        ["golang", "go lang", "gin", "echo"],
        ["Programming", "Languages"],
        0.85,
    ),
    (
        ["typescript", "node.js", "nodejs", "express", "nestjs", "bun"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["java", "spring", "jvm", "kotlin", "gradle", "maven"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["c++", "cpp", "cmake", "qt", "boost"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["haskell", "purescript", "elm", "functional programming", "monad"],
        ["Programming", "Paradigms"],
        0.85,
    ),
    (
        ["sql", "database", "postgres", "mysql", "sqlite", "orm", "query", "prisma", "sqlalchemy"],
        ["Data", "Databases"],
        0.80,
    ),
    (
        ["etl", "pipeline", "airflow", "dagster", "data warehouse", "lake"],
        ["Data", "Data-Engineering"],
        0.80,
    ),
    (
        ["analytics", "bi", "dashboard", "tableau", "looker", "metabase"],
        ["Data", "Analytics"],
        0.80,
    ),
    (
        ["visualization", "chart", "plot", "d3", "matplotlib", "plotly", "vega"],
        ["Data", "Visualization"],
        0.80,
    ),
    (
        ["big data", "spark", "hadoop", "kafka", "stream processing", "distributed"],
        ["Data", "Big-Data"],
        0.85,
    ),
    (
        ["time series", "forecasting", "arima", "prophet", "anomaly detection"],
        ["Data", "Time-Series"],
        0.85,
    ),
    (
        ["data science", "exploratory analysis", "feature engineering", "eda"],
        ["Data", "Data-Science"],
        0.80,
    ),
    (
        ["devops", "ci/cd", "jenkins", "github actions", "gitlab ci", "argo"],
        ["Programming", "DevEx"],
        0.80,
    ),
    (
        ["test", "testing", "pytest", "unittest", "mock", "tdd", "bdd", "fuzz"],
        ["Programming", "Testing"],
        0.75,
    ),
    (
        ["algorithm", "leetcode", "dynamic programming", "graph", "sorting", "complexity"],
        ["Programming", "Algorithms"],
        0.80,
    ),
    (
        ["design pattern", "refactor", "clean code", "solid", "dry", "kiss"],
        ["Programming", "Patterns"],
        0.75,
    ),
    (
        ["performance", "optimization", "profiling", "benchmark", "concurrency", "parallel"],
        ["Programming", "Performance"],
        0.80,
    ),
    (
        ["monitoring", "logging", "tracing", "prometheus", "grafana", "jaeger", "otel"],
        ["Systems", "Observability"],
        0.80,
    ),
    (
        ["interview", "leetcode", "system design", "coding interview", "behavioral"],
        ["Career", "Interview"],
        0.85,
    ),
    (
        ["resume", "cv", "portfolio", "linkedin", "personal brand"],
        ["Career", "Resume"],
        0.80,
    ),
]
