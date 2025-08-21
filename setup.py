from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gen3-metadata-templates",
    version="0.1.0",
    description="Create Gen3 Metadata Submission Templates from a Gen3 JSON Schema",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="JoshuaHarris391",
    author_email="harjo391@gmail.com",
    license="Apache 2.0",
    url="https://github.com/AustralianBioCommons/gen3-metadata-templates",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9.5",
    install_requires=[
        "gen3-validator>=1.0.4,<2.0.0",
        "pytest>=8.4.1,<9.0.0",
        "logging>=0.4.9.6,<0.5.0.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
)