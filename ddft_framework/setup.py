
from setuptools import setup, find_packages

setup(
    name="ddft_framework",
    version="1.0.0",
    description="A framework for the Drill-Down and Fabricate Test (DDFT).",
    author="Anonymous",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pandas",
        "numpy",
        "scipy",
        "scikit-learn",
        "requests",
    ],
    entry_points={
        'console_scripts': [
            'ddft = main:main',
            'moltbot-ddft = moltbot.cli:main',
        ],
    },
)
