"""
Tel-Insights Setup Configuration

Setup script for the Tel-Insights Smart Telegram News Aggregator project.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="tel-insights",
    version="0.1.0",
    author="Tel-Insights Team",
    description="Smart Telegram News Aggregator with Advanced AI Analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/tel-insights",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-mock>=3.12.0",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
        ],
        "docs": [
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=1.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "tel-insights-aggregator=aggregator.main:run_aggregator",
            "tel-insights-ai-analysis=ai_analysis.main:run_ai_analysis",
            "tel-insights-smart-analysis=smart_analysis.main:run_smart_analysis",
            "tel-insights-alerting=alerting.main:run_alerting",
        ],
    },
    include_package_data=True,
    zip_safe=False,
) 