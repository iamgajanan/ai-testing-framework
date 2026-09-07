from setuptools import find_packages, setup

setup(
    name="ai-testing-framework",
    version="0.4.0",
    description="Universal AI-powered web testing framework",
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=True,
    install_requires=[
        "playwright>=1.50,<2", "openai>=1.68,<2", "PyYAML>=6.0,<7",
        "beautifulsoup4>=4.12,<5", "openpyxl>=3.1,<4", "reportlab>=4.0,<5", "pypdf>=5.0,<7",
        "fastapi>=0.115,<1", "uvicorn[standard]>=0.30,<1", "httpx>=0.27,<1",
        "PyJWT[crypto]>=2.10,<3",
    ],
    entry_points={"console_scripts": [
        "ai-test=ai_testing_framework.cli:main",
        "ai-test-worker=ai_testing_framework.server.worker:main",
    ]},
    python_requires=">=3.10",
)
