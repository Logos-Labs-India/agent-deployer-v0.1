from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agent-deployer",
    version="0.1.0",
    author="Ninad",
    author_email="ninadsk.tuchemnitz@gmail.com",
    description="A tool to deploy Python APIs to servers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/agent-deployer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.6",
    install_requires=[
        "click>=7.0",
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "agent-deploy=agent_deployer.cli:main",
        ],
    },
)