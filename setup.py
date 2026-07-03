#!/usr/bin/env python3
"""
Setup configuration for fraud_anomaly_detection package.
Enables installation and distribution of the fraud detection module as a standalone package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README and requirements
readme_path = Path(__file__).parent / "README.md"
requirements_path = Path(__file__).parent / "requirements.txt"

readme_content = ""
if readme_path.exists():
    with open(readme_path, encoding="utf-8") as f:
        readme_content = f.read()

requirements = []
if requirements_path.exists():
    with open(requirements_path, encoding="utf-8") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="mpesa-fraud-anomaly-detection",
    version="1.0.0",
    description="M-Pesa Fraud Detection & Anomaly Monitoring System",
    long_description=readme_content,
    long_description_content_type="text/markdown",
    author="Victor Kipruto",
    author_email="victor@example.com",
    url="https://github.com/Victor-Kipruto-Rop/victor-kipruto-rop-portfolio",
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "isort>=5.12.0",
            "pytest>=7.4.2",
            "pytest-cov>=4.1.0",
        ],
        "ml": [
            "xgboost>=2.0.0",
            "imbalanced-learn>=0.11.0",
            "shap>=0.42.0",
            "onnx>=1.14.0",
            "onnxruntime>=1.16.0",
            "skl2onnx>=1.14.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "fraud-detector=fraud_anomaly_detection.cli:main",
            "train-fraud-model=fraud_anomaly_detection.ml.train_model:main",
            "evaluate-fraud-model=fraud_anomaly_detection.ml.evaluate_model:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security",
        "Topic :: Communications",
    ],
    keywords="fraud detection machine learning anomaly monitoring mpesa",
    include_package_data=True,
)
