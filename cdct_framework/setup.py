from setuptools import setup, find_packages

setup(
    name="cdct_framework",
    version="1.0.0",
    description="A framework for the Constraint-Decay Comprehension Test (CDCT)",
    author="Anonymous",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "openai",
        "anthropic",
        "pandas",
        "numpy",
        "scipy",
        "scikit-learn"
    ],
)
