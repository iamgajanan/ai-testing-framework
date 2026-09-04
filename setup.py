from setuptools import find_packages, setup

setup(
    name="ai-testing-framework",
    version="0.1.0",
    description="Universal AI-powered web testing framework",
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=True,
    install_requires=[
        "playwright>=1.50,<2",
        "openai>=1.68,<2",
        "PyYAML>=6.0,<7",
        "beautifulsoup4>=4.12,<5",
    ],
    entry_points={"console_scripts": ["ai-test=ai_testing_framework.cli:main"]},
    python_requires=">=3.9",
)
